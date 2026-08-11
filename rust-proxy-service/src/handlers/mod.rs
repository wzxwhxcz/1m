use axum::{
    extract::{Extension, State, Path},
    http::{StatusCode, HeaderMap},
    response::{IntoResponse, Response},
    body::Body,
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

/// 基于 token 预算动态计算召回条数 k：
/// k ≈ RECALL_TARGET(400K) / 平均每条消息的 tokens，
/// 使召回后的上下文尽量贴近 400K 目标（而非固定条数）。
/// 例如 1M tokens / 5000 条消息 → 平均 200 tokens/条 → k = 400000/200 = 2000 条
/// 例如 1M tokens / 200 条长消息 → 平均 5000 tokens/条 → k = 400000/5000 = 80 条
fn compute_dynamic_k(input_tokens: usize, message_count: usize) -> usize {
    let avg_tokens_per_msg = (input_tokens / message_count.max(1)).max(1);
    (RECALL_TARGET / avg_tokens_per_msg).clamp(1, message_count.max(1))
}

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

        // Calculate k based on token budget (dynamic)
        let k = compute_dynamic_k(input_tokens, request.messages.len());

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
            .proxy_request(&upstream_url, &api_key, request, None)
            .await?;

        return Ok((
            StatusCode::OK,
            [("Content-Type", "text/event-stream")],
            axum::body::Body::from_stream(stream),
        ).into_response());
    } else {
        // Non-streaming response
        state.proxy_service
            .proxy_non_stream(&upstream_url, &api_key, request, None)
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

    // 2b. Validate service_key and load user (quota & logging 依赖)
    let user = User::find_by_service_key(&state.db, &service_key)
        .await?
        .ok_or(ProxyError::InvalidServiceKey)?;

    if !user.has_quota() {
        return Err(ProxyError::RateLimitExceeded);
    }

    tracing::info!(
        service_key = %service_key,
        user_id = user.id,
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

        // Call recall service with dynamic k (token-budget aware)
        let recall_start = Instant::now();
        let k = compute_dynamic_k(input_tokens, request.messages.len());
        let recalled_messages = state.recall_service
            .recall_messages(&request.messages, query.to_string(), k, "car", 10)
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
    let response_body = state.proxy_service
        .forward_request(&upstream_url, &request, api_key.to_string())
        .await?;

    let duration = start.elapsed();
    crate::metrics::REQUEST_DURATION.observe(duration.as_secs_f64());

    // 6. Increment user quota
    user.increment_quota(&state.db).await?;

    // 7. Log request (fire-and-forget)
    let db = state.db.clone();
    let user_id = user.id;
    let input_tokens_i32 = input_tokens as i32;
    let needs_recall_bool = needs_recall;
    let total_latency = duration.as_millis() as i32;
    let upstream_url_log = upstream_url.clone();
    tokio::spawn(async move {
        let _ = sqlx::query(
            "INSERT INTO request_logs (user_id, upstream_url, input_tokens, recall_triggered, total_latency_ms, status, created_at) VALUES ($1, $2, $3, $4, $5, $6, NOW())"
        )
        .bind(user_id)
        .bind(upstream_url_log)
        .bind(input_tokens_i32)
        .bind(needs_recall_bool)
        .bind(total_latency)
        .bind("success")
        .execute(&db)
        .await;
    });

    // Convert String to Response
    Ok(Response::builder()
        .status(200)
        .header("Content-Type", "application/json")
        .body(Body::from(response_body))
        .unwrap())
}
