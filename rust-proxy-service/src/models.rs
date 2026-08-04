use serde::{Deserialize, Serialize};
use chrono::{DateTime, Utc};

// User model
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct User {
    pub id: i32,
    pub service_key: String,
    pub email: Option<String>,
    pub plan: String,
    pub quota_daily: i32,
    pub quota_used_today: i32,
    pub is_active: bool,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl User {
    pub async fn find_by_service_key(pool: &crate::DbPool, service_key: &str) -> crate::Result<Option<Self>> {
        let user = sqlx::query_as::<_, User>(
            "SELECT * FROM users WHERE service_key = $1 AND is_active = true"
        )
        .bind(service_key)
        .fetch_optional(pool)
        .await?;

        Ok(user)
    }

    pub async fn increment_quota(&self, pool: &crate::DbPool) -> crate::Result<()> {
        sqlx::query(
            "UPDATE users SET quota_used_today = quota_used_today + 1, updated_at = NOW() WHERE id = $1"
        )
        .bind(self.id)
        .execute(pool)
        .await?;

        Ok(())
    }

    pub async fn increment_tokens(&self, pool: &crate::DbPool, input_tokens: i32, output_tokens: i32) -> crate::Result<()> {
        sqlx::query(
            "UPDATE users SET quota_used_today = quota_used_today + 1, updated_at = NOW() WHERE id = $1"
        )
        .bind(self.id)
        .execute(pool)
        .await?;

        Ok(())
    }

    pub fn has_quota(&self) -> bool {
        self.is_active && self.quota_used_today < self.quota_daily
    }

    pub fn remaining_quota(&self) -> i32 {
        (self.quota_daily - self.quota_used_today).max(0)
    }

    pub async fn reset_daily_quota(pool: &crate::DbPool) -> crate::Result<u64> {
        let result = sqlx::query(
            "UPDATE users SET quota_used_today = 0, updated_at = NOW() WHERE DATE(updated_at) < CURRENT_DATE"
        )
        .execute(pool)
        .await?;

        Ok(result.rows_affected())
    }
}

// Admin model
#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct Admin {
    pub id: i32,
    pub username: String,
    pub password_hash: String,
    pub created_at: DateTime<Utc>,
}

// Admin API requests/responses
#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub username: String,
    pub password: String,
}

#[derive(Debug, Serialize)]
pub struct LoginResponse {
    pub token: String,
    pub username: String,
}

#[derive(Debug, Deserialize)]
pub struct CreateUserRequest {
    pub email: Option<String>,
    pub plan: String,
    pub quota_daily: i32,
}

#[derive(Debug, Deserialize)]
pub struct UpdateUserRequest {
    pub email: Option<String>,
    pub plan: Option<String>,
    pub quota_daily: Option<i32>,
    pub is_active: Option<bool>,
}

// Request log model
#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct RequestLog {
    pub id: i64,
    pub user_id: i32,
    pub upstream_url: String,
    pub input_tokens: i32,
    pub output_tokens: Option<i32>,
    pub recall_triggered: bool,
    pub recall_latency_ms: Option<i32>,
    pub total_latency_ms: i32,
    pub status: String,
    pub error_message: Option<String>,
    pub created_at: DateTime<Utc>,
}

// Chat API models
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatRequest {
    pub model: String,
    pub messages: Vec<Message>,
    #[serde(default)]
    pub stream: bool,
    #[serde(default)]
    pub temperature: Option<f32>,
    #[serde(default)]
    pub max_tokens: Option<u32>,
}

// Recall service models
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallRequest {
    pub messages: Vec<Message>,
    pub query: String,
    pub k: usize,
    #[serde(default = "default_algorithm")]
    pub algorithm: String,
}

fn default_algorithm() -> String {
    "car".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallResponse {
    pub recalled_messages: Vec<Message>,
    pub original_count: usize,
    pub recalled_count: usize,
    pub latency_ms: u64,
}
