use axum::{
    extract::{Extension, State, Path},
    http::{StatusCode, HeaderMap},
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;
use std::sync::Arc;
use std::time::Instant;
use urlencoding::decode;

use crate::{
    models::{ChatRequest, User, Message},
    services::{RecallService, ProxyService},
    error::{ProxyError, Result},
    DbPool,
};

pub mod admin;

pub use admin::*;

#[derive(Clone)]
pub struct AppState {
    pub db: DbPool,
    pub recall_service: Arc<RecallService>,
    pub proxy_service: Arc<ProxyService>,
}

const CONTEXT_THRESHOLD: usize = 1000000; // 1M tokens
const RECALL_TARGET: usize = 400000; // 400K tokens

pub async fn chat_completions_handler(
    State(state): State<AppState>,
    Extension(user): Extension<User>,
    Json(mut request): Json<ChatRequest>,
) -> Result<Response> {
    let start = Instant::now();
    
    crate::metrics::REQUESTS_TOTAL.inc();

    // Count input tokens (simplified)
    let input_tokens = estimate_tokens(&request.messages);

    // Check if recall is needed
    let needs_recall = input_tokens > CONTEXT_THRESHOLD;

    if needs_recall {
        crate::metrics::RECALL_TRIGGERED.inc();
        
        // Extract query from last message
        let query = request.messages
            .last()
            .map(|m| m.content.clone())
            .unwrap_or_default();

        // Calculate k based on target
        let k = (RECALL_TARGET / 100).min(request.messages.len());

        // Call recall service
        let recall_response = state.recall_service
            .recall(request.messages.clone(), query, k)
            .await?;

        // Replace messages with recalled messages
        request.messages = recall_response.recalled_messages;
    }

    // Increment user quota
    user.increment_quota(&state.db).await?;

    // Proxy to upstream API
    let upstream_url = std::env::var("UPSTREAM_API_URL")
        .unwrap_or_else(|_| "https://api.openai.com/v1/chat/completions".to_string());
    
    let api_key = std::env::var("UPSTREAM_API_KEY")
        .expect("UPSTREAM_API_KEY must be set");

    let response_body = if request.stream {
        // Streaming response
        let stream = state.proxy_service
            .proxy_request(&upstream_url, &api_key, request)
            .await?;

        return Ok((
            StatusCode::OK,
            [("Content-Type", "text/event-stream")],
            axum::body::Body::from_stream(stream),
        ).into_response());
    } else {
        // Non-streaming response
        state.proxy_service
            .proxy_non_stream(&upstream_url, &api_key, request)
            .await?
    };

    // Record metrics
    let total_latency = start.elapsed().as_millis() as i32;
    crate::metrics::REQUEST_DURATION.observe(start.elapsed().as_secs_f64());

    // Log request (fire-and-forget)
    let db = state.db.clone();
    let user_id = user.id;
    tokio::spawn(async move {
        let _ = sqlx::query(
            r#"
            INSERT INTO request_logs 
            (user_id, upstream_url, input_tokens, recall_triggered, total_latency_ms, status, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            "#
        )
        .bind(user_id)
        .bind(upstream_url)
        .bind(input_tokens as i32)
        .bind(needs_recall)
        .bind(total_latency)
        .bind("success")
        .execute(&db)
        .await;
    });

    Ok((
        StatusCode::OK,
        [("Content-Type", "application/json")],
        response_body,
    ).into_response())
}

pub async fn health_handler(State(state): State<AppState>) -> impl IntoResponse {
    // Check database
    let db_ok = sqlx::query("SELECT 1")
        .execute(&state.db)
        .await
        .is_ok();

    // Check recall service
    let recall_ok = state.recall_service.health_check().await;

    let status = if db_ok && recall_ok {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    (
        status,
        Json(json!({
            "status": if db_ok && recall_ok { "healthy" } else { "unhealthy" },
            "database": db_ok,
            "recall_service": recall_ok,
        }))
    )
}

pub async fn metrics_handler() -> impl IntoResponse {
    let metrics = crate::metrics::gather_metrics();
    (
        StatusCode::OK,
        [("Content-Type", "text/plain; version=0.0.4")],
        metrics,
    )
}

// Simplified token estimation (1 token ≈ 4 characters)
fn estimate_tokens(messages: &[Message]) -> usize {
    messages.iter()
        .map(|m| m.content.len() / 4)
        .sum()
}

/// Dynamic proxy handler: /{service_key}/{upstream_encoded}/v1/chat/completions
/// This matches the Go version's routing format
pub async fn dynamic_chat_completions_handler(
    State(state): State<AppState>,
    Path((service_key, upstream_encoded)): Path<(String, String)>,
    headers: HeaderMap,
    Json(mut request): Json<ChatRequest>,
) -> Result<Response> {
    let start = Instant::now();
    
    crate::metrics::REQUESTS_TOTAL.inc();

    // 1. Decode upstream URL
    let upstream_base = decode(&upstream_encoded)
        .map_err(|_| ProxyError::BadRequest("Invalid upstream URL encoding".into()))?
        .into_owned();
    
    let upstream_url = format!("{}/v1/chat/completions", upstream_base);

    // 2. Get API key from Authorization header
    let api_key = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .ok_or_else(|| ProxyError::Unauthorized("Missing Authorization header".into()))?;

    tracing::info!(
        service_key = %service_key,
        upstream = %upstream_base,
        messages = request.messages.len(),
        "Dynamic proxy request"
    );

    // 3. Count input tokens
    let input_tokens = estimate_tokens(&request.messages);

    // 4. Check if recall is needed (>400K tokens)
    let needs_recall = input_tokens > CONTEXT_THRESHOLD;

    if needs_recall {
        crate::metrics::RECALL_TRIGGERED.inc();
        
        // Extract query from last message
        let query = request.messages.last()
            .map(|m| m.content.as_str())
            .unwrap_or("");

        // Call recall service
        let recall_start = Instant::now();
        let recalled_messages = state.recall_service
            .recall_messages(&request.messages, query, 50, "car", 10)
            .await?;
        
        let recall_duration = recall_start.elapsed();
        crate::metrics::RECALL_LATENCY.observe(recall_duration.as_secs_f64());

        tracing::info!(
            original_count = request.messages.len(),
            recalled_count = recalled_messages.len(),
            duration_ms = recall_duration.as_millis(),
            "Context recall completed"
        );

        // Replace messages with recalled ones
        request.messages = recalled_messages;
    }

    // 5. Forward to upstream
    let response = state.proxy_service
        .forward_request(&upstream_url, &request, api_key)
        .await?;

    let duration = start.elapsed();
    crate::metrics::REQUEST_DURATION.observe(duration.as_secs_f64());

    if response.status().is_success() {
        crate::metrics::REQUESTS_SUCCESS.inc();
    } else {
        crate::metrics::REQUESTS_FAILED.inc();
    }

    Ok(response)
}
