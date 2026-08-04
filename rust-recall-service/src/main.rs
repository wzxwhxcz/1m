use axum::{
    extract::State,
    http::StatusCode,
    response::{IntoResponse, Response},
    routing::{get, post},
    Json, Router,
};
use std::sync::Arc;
use tower_http::cors::CorsLayer;
use tracing::{info, error};
use serde::{Deserialize, Serialize};

mod cache;
mod embedding;
mod recall;
mod metrics;
mod error;

use cache::CacheManager;
use embedding::RemoteEmbeddingClient;
use recall::{RecallService, RecallRequest, RecallResponse};

#[derive(Clone)]
struct AppState {
    recall_service: Arc<RecallService>,
    cache_manager: Arc<CacheManager>,
}

#[derive(Serialize)]
struct HealthResponse {
    status: String,
    version: String,
}

#[derive(Serialize)]
struct ErrorResponse {
    error: String,
}

impl IntoResponse for error::RecallError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            error::RecallError::InvalidInput(msg) => (StatusCode::BAD_REQUEST, msg),
            error::RecallError::Cache(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            error::RecallError::Embedding(msg) => (StatusCode::INTERNAL_SERVER_ERROR, msg),
            error::RecallError::Http(e) => (StatusCode::BAD_GATEWAY, e.to_string()),
            _ => (StatusCode::INTERNAL_SERVER_ERROR, self.to_string()),
        };

        let body = Json(ErrorResponse { error: message });
        (status, body).into_response()
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // 初始化日志
    tracing_subscriber::fmt()
        .with_env_filter("info,rust_recall_service=debug")
        .init();

    // 初始化 Prometheus 指标
    metrics::init_metrics();

    info!("🚀 Starting Rust Recall Service");

    // 从环境变量读取配置
    let redis_url = std::env::var("REDIS_URL")
        .unwrap_or_else(|_| "redis://127.0.0.1:6379".to_string());
    
    let api_base = std::env::var("EMBEDDING_API_BASE")
        .unwrap_or_else(|_| "http://router.tumuer.me".to_string());
    
    let api_key = std::env::var("EMBEDDING_API_KEY")
        .expect("EMBEDDING_API_KEY must be set");
    
    let model = std::env::var("EMBEDDING_MODEL")
        .unwrap_or_else(|_| "Qwen/Qwen3-Embedding-4B".to_string());
    
    let port = std::env::var("PORT")
        .unwrap_or_else(|_| "8000".to_string())
        .parse::<u16>()?;

    info!("📦 Initializing cache manager...");
    let cache_manager = Arc::new(CacheManager::new(&redis_url).await?);

    info!("🧠 Initializing embedding client...");
    let embedding_client = Arc::new(
        RemoteEmbeddingClient::new(api_base, api_key, model, cache_manager.clone()).await?
    );

    info!("🎯 Initializing recall service...");
    let recall_service = Arc::new(RecallService::new(embedding_client));

    let state = AppState {
        recall_service,
        cache_manager,
    };

    // 构建路由
    let app = Router::new()
        .route("/health", get(health))
        .route("/metrics", get(metrics_handler))
        .route("/api/v1/recall", post(recall))
        .route("/api/v1/cache/stats", get(cache_stats))
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    info!("✅ Server listening on {}", addr);
    info!("");
    info!("Endpoints:");
    info!("  GET  http://localhost:{}/health", port);
    info!("  GET  http://localhost:{}/metrics", port);
    info!("  POST http://localhost:{}/api/v1/recall", port);
    info!("  GET  http://localhost:{}/api/v1/cache/stats", port);
    info!("");

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "healthy".to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
    })
}

async fn metrics_handler() -> impl IntoResponse {
    let metrics = metrics::gather_metrics();
    (StatusCode::OK, metrics)
}

async fn recall(
    State(state): State<AppState>,
    Json(request): Json<RecallRequest>,
) -> Result<Json<RecallResponse>, error::RecallError> {
    let _timer = metrics::RECALL_LATENCY.start_timer();
    metrics::RECALL_REQUESTS_TOTAL.inc();

    info!(
        "Recall request: {} messages, k={}, algorithm={:?}",
        request.messages.len(),
        request.k,
        request.algorithm
    );

    // 验证输入
    if request.messages.is_empty() {
        return Err(error::RecallError::InvalidInput(
            "messages cannot be empty".to_string()
        ));
    }

    if request.k == 0 {
        return Err(error::RecallError::InvalidInput(
            "k must be greater than 0".to_string()
        ));
    }

    if request.query.trim().is_empty() {
        return Err(error::RecallError::InvalidInput(
            "query cannot be empty".to_string()
        ));
    }

    match state.recall_service.recall(request).await {
        Ok(response) => {
            info!(
                "Recall completed: {} -> {} messages in {}ms",
                response.original_count,
                response.recalled_count,
                response.latency_ms
            );
            Ok(Json(response))
        }
        Err(e) => {
            error!("Recall failed: {}", e);
            metrics::RECALL_ERRORS_TOTAL.inc();
            Err(e)
        }
    }
}

#[derive(Serialize)]
struct CacheStatsResponse {
    hit_rate: f64,
    total_hits: u64,
    total_misses: u64,
}

async fn cache_stats(
    State(state): State<AppState>,
) -> Json<CacheStatsResponse> {
    let stats = state.cache_manager.get_stats();
    
    Json(CacheStatsResponse {
        hit_rate: stats.hit_rate,
        total_hits: stats.total_hits,
        total_misses: stats.total_misses,
    })
}
