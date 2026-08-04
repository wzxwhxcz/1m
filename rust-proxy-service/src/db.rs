use sqlx::{postgres::PgPoolOptions, PgPool};
use std::time::Duration;
use crate::error::Result;

pub type DbPool = PgPool;

pub async fn create_pool(database_url: &str, max_connections: u32, min_connections: u32) -> Result<DbPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_connections)
        .min_connections(min_connections)
        .acquire_timeout(Duration::from_secs(5))
        .idle_timeout(Duration::from_secs(600))
        .max_lifetime(Duration::from_secs(1800))
        .connect(database_url)
        .await?;

    Ok(pool)
}

// 数据库初始化脚本
pub async fn initialize_schema(pool: &DbPool) -> Result<()> {
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            service_key VARCHAR(64) UNIQUE NOT NULL,
            email VARCHAR(255),
            plan VARCHAR(32) DEFAULT 'free',
            quota_daily INTEGER DEFAULT 100,
            quota_used_today INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS request_logs (
            id BIGSERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            upstream_url VARCHAR(512),
            input_tokens INTEGER,
            output_tokens INTEGER,
            recall_triggered BOOLEAN DEFAULT false,
            recall_latency_ms INTEGER,
            total_latency_ms INTEGER,
            status VARCHAR(32),
            error_message TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_user_key ON users(service_key);
        CREATE INDEX IF NOT EXISTS idx_logs_user_time ON request_logs(user_id, created_at);
        "#
    )
    .execute(pool)
    .await?;

    Ok(())
}
