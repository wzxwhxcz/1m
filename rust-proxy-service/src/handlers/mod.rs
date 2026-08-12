use axum::{
    extract::{Extension, FromRef, State, Path},
    http::{StatusCode, HeaderMap},
    response::{IntoResponse, Response},
    body::Body,
    Json,
};
use serde_json::json;
use std::sync::{Arc, RwLock};
use std::time::Instant;
use urlencoding::decode;

use crate::{
    config::RuntimeConfig,
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
    /// 运行时配置（管理后台可动态修改，RwLock 保护）
    pub config: Arc<RwLock<RuntimeConfig>>,
    /// JWT 签名密钥（启动时从 JWT_SECRET 或随机生成）
    pub jwt_secret: Vec<u8>,
}

// 允许 admin 子路由的 State<PgPool> 处理器从 AppState 提取 db
impl FromRef<AppState> for DbPool {
    fn from_ref(s: &AppState) -> DbPool {
        s.db.clone()
    }
}

/// 结构感知切分（LLMLingua budget-controller 思路）：
/// - `system` 消息：全保留（指令/系统提示压缩率最低，保持语义完整）
/// - `history`：中间历史，交给 recall 按 query 相关性挑选（压缩主体）
/// - `tail`：query 前最后 2 条，作为最近上下文锚点全保留（StreamingLLM/注意力汇 思路）
/// - `query`：最后一条用户消息全保留（question 几乎不压缩）
fn split_context(messages: &[Message]) -> (Vec<Message>, Vec<Message>, Vec<Message>, Message) {
    let n = messages.len();
    let query_idx = n.saturating_sub(1);
    let tail_start = n.saturating_sub(3).min(query_idx);

    let mut system = Vec::new();
    let mut history = Vec::new();
    let mut tail = Vec::new();
    for (i, m) in messages.iter().enumerate() {
        if m.role == "system" {
            system.push(m.clone());
        } else if i < query_idx && i >= tail_start {
            tail.push(m.clone());
        } else if i < query_idx {
            history.push(m.clone());
        }
    }

    let query = messages[query_idx].clone();
    (system, history, tail, query)
}

/// 基于「历史消息」的实际 token 数和给定预算反推 k：
/// k = budget / 历史平均每条 tokens，保证召回后 ≈ 预算
fn k_from_budget(budget_tokens: usize, history: &[Message]) -> usize {
    let hist_tokens: usize = history.iter().map(|m| m.content.len() / 4).sum();
    let avg = (hist_tokens / history.len().max(1)).max(1);
    (budget_tokens / avg).clamp(1, history.len().max(1))
}

/// 统一压缩管线（LongLLMLingua 问题感知 + lost-in-the-middle 缓解）：
/// 系统/指令全保留 + 头部/尾部锚点 + 中间历史按 query 相关性召回 + 最近上下文，
/// 组装后整体 token 估算不超过 cfg.recall_target。
async fn compress_context(
    recall: &RecallService,
    cfg: &RuntimeConfig,
    messages: &[Message],
) -> crate::Result<Vec<Message>> {
    let (system, history, tail, query) = split_context(messages);

    if history.is_empty() {
        let mut out = system;
        out.extend(tail);
        out.push(query);
        return Ok(out);
    }

    // 预算分配：recall_target 减去已保留部分（system + tail + query），剩余全给历史召回
    let preserved_tokens = estimate_tokens(&system) + estimate_tokens(&tail) + estimate_tokens(&[query.clone()]);
    let budget = cfg.recall_target.saturating_sub(preserved_tokens).max(1);
    let k = k_from_budget(budget, &history);

    tracing::info!(
        system_msgs = system.len(),
        history_msgs = history.len(),
        tail_msgs = tail.len(),
        budget_tokens = budget,
        recall_k = k,
        "Context compression plan"
    );

    let recalled = recall
        .recall_messages(&history, query.content.clone(), k, "car", 10)
        .await?;

    // 组装：系统/指令 + 召回中间历史 + 尾部最近上下文 + query
    let mut out = system;
    out.extend(recalled);
    out.extend(tail);
    out.push(query);
    Ok(out)
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

    // 运行时配置（后台可调）
    let cfg = state.config.read().map_err(|_| ProxyError::Internal("config lock poisoned".into()))?.clone();

    // 超限保护：超过 max_context_length 直接拒绝
    if input_tokens > cfg.max_context_length {
        return Err(ProxyError::BadRequest(format!(
            "Input exceeds max_context_length ({})", cfg.max_context_length
        )));
    }

    // Check if recall is needed（阈值可配置）
    let needs_recall = input_tokens > cfg.recall_threshold;

    if needs_recall {
        crate::metrics::RECALL_TRIGGERED.inc();

        // 统一压缩管线：结构感知 + 问题感知 + token 预算保证
        request.messages = compress_context(&state.recall_service, &cfg, &request.messages).await?;
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

    // 3b. 运行时配置（后台可调）+ 超限保护
    let cfg = state.config.read().map_err(|_| ProxyError::Internal("config lock poisoned".into()))?.clone();
    if input_tokens > cfg.max_context_length {
        return Err(ProxyError::BadRequest(format!(
            "Input exceeds max_context_length ({})", cfg.max_context_length
        )));
    }

    // 4. Check if recall is needed（阈值可配置）
    let needs_recall = input_tokens > cfg.recall_threshold;

    if needs_recall {
        crate::metrics::RECALL_TRIGGERED.inc();

        let recall_start = Instant::now();
        let compressed = compress_context(&state.recall_service, &cfg, &request.messages).await?;
        let recall_duration = recall_start.elapsed();
        crate::metrics::RECALL_LATENCY.observe(recall_duration.as_secs_f64());

        tracing::info!(
            original_count = request.messages.len(),
            compressed_count = compressed.len(),
            compressed_tokens = estimate_tokens(&compressed),
            duration_ms = recall_duration.as_millis(),
            "Context compression completed"
        );

        request.messages = compressed;
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
