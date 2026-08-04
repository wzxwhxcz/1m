use axum::{
    routing::{get, post, put, delete},
    Router,
    middleware,
};
use std::sync::Arc;
use tower_http::{
    cors::CorsLayer,
    trace::TraceLayer,
    timeout::TimeoutLayer,
};
use std::time::Duration;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

use rust_proxy_service::{
    config::Config,
    db::{create_pool, initialize_schema},
    handlers::{
        AppState, 
        chat_completions_handler,
        dynamic_chat_completions_handler,
        health_handler, 
        metrics_handler,
    },
    services::{RecallService, ProxyService},
    middleware::{auth::auth_middleware, jwt::jwt_auth_middleware},
};

// Import admin handlers separately
use rust_proxy_service::handlers::admin::{
    login_handler,
    list_users_handler,
    get_user_handler,
    create_user_handler,
    update_user_handler,
    delete_user_handler,
    dashboard_stats_handler,
    qps_data_handler,
    trend_data_handler,
    list_logs_handler,
    get_system_config_handler,
    update_system_config_handler,
    detailed_stats_handler,
};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "rust_proxy_service=info,tower_http=info".into()),
        )
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    // Load configuration
    let config = Config::from_env();
    tracing::info!("Configuration loaded: {:?}", config);

    // Initialize metrics
    rust_proxy_service::metrics::init_metrics();
    tracing::info!("Metrics initialized");

    // Create database pool
    let db_pool = create_pool(
        &config.database.url,
        config.database.max_connections,
        config.database.min_connections,
    )
    .await?;
    tracing::info!("Database pool created");

    // Initialize database schema
    initialize_schema(&db_pool).await?;
    tracing::info!("Database schema initialized");

    // Create services
    let recall_service = Arc::new(RecallService::new(
        config.recall.urls.clone(),
        config.recall.timeout_secs,
    ));
    tracing::info!("Recall service created with {} instances", config.recall.urls.len());

    let proxy_service = Arc::new(ProxyService::new(60));
    tracing::info!("Proxy service created");

    // Create application state
    let state = AppState {
        db: db_pool.clone(),
        recall_service,
        proxy_service,
    };

    // Build router
    let app = Router::new()
        // Public routes
        .route("/health", get(health_handler))
        .route("/metrics", get(metrics_handler))
        
        // Dynamic proxy route: /{service_key}/{upstream_encoded}/v1/chat/completions
        // This matches the Go version's format
        .route(
            "/:service_key/:upstream_encoded/v1/chat/completions",
            post(dynamic_chat_completions_handler)
        )
        
        // Legacy chat completions route (protected by service key auth)
        .route(
            "/v1/chat/completions",
            post(chat_completions_handler)
                .route_layer(middleware::from_fn_with_state(
                    db_pool.clone(),
                    auth_middleware,
                ))
        )
        .with_state(state.clone())
        
        // Admin API - Login (public, uses PgPool state)
        .route("/api/admin/login", post(login_handler).with_state(db_pool.clone()))
        
        // Admin API - Protected routes (with JWT, uses PgPool state)
        .nest("/api/admin", Router::new()
            .route("/users", get(list_users_handler).post(create_user_handler))
            .route("/users/:id", get(get_user_handler).put(update_user_handler).delete(delete_user_handler))
            .route("/stats/dashboard", get(dashboard_stats_handler))
            .route("/stats/detailed", get(detailed_stats_handler))
            .route("/stats/qps", get(qps_data_handler))
            .route("/stats/trend", get(trend_data_handler))
            .route("/logs", get(list_logs_handler))
            .route("/config", get(get_system_config_handler).put(update_system_config_handler))
            .layer(middleware::from_fn(jwt_auth_middleware))
            .with_state(db_pool.clone())
        )
        
        // Middleware
        .layer(CorsLayer::permissive())
        .layer(TraceLayer::new_for_http())
        .layer(TimeoutLayer::new(Duration::from_secs(300)));

    // Start server
    let addr = format!("{}:{}", config.server.host, config.server.port);
    let listener = tokio::net::TcpListener::bind(&addr).await?;
    
    tracing::info!("🚀 Rust Proxy Server listening on {}", addr);
    tracing::info!("📊 Metrics available at http://{}/metrics", addr);
    tracing::info!("❤️  Health check at http://{}/health", addr);

    axum::serve(listener, app)
        .await?;

    Ok(())
}
