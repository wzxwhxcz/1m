use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use serde::{Deserialize, Serialize};
use sqlx::{PgPool, Row};
use chrono::{DateTime, Utc};
use jsonwebtoken::{encode, EncodingKey, Header};
use bcrypt::verify;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

use crate::{
    config::RuntimeConfig,
    handlers::AppState,
    models::{get_system_config_all, set_system_config},
};

// 登录暴力破解防护：按 IP 限制，5 次/5 分钟
const LOGIN_MAX_ATTEMPTS: u32 = 5;
const LOGIN_WINDOW: Duration = Duration::from_secs(300);
static LOGIN_ATTEMPTS: OnceLock<Mutex<HashMap<String, (u32, Instant)>>> = OnceLock::new();

fn login_attempts() -> &'static Mutex<HashMap<String, (u32, Instant)>> {
    LOGIN_ATTEMPTS.get_or_init(|| Mutex::new(HashMap::new()))
}

fn client_ip(headers: &axum::http::HeaderMap) -> String {
    headers
        .get("x-forwarded-for")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.split(',').next())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown".to_string())
}

fn check_login_rate_limit(ip: &str) -> Result<(), (StatusCode, String)> {
    let mut map = login_attempts().lock().map_err(|_| (StatusCode::INTERNAL_SERVER_ERROR, "lock poisoned".into()))?;
    let now = Instant::now();
    if let Some((count, start)) = map.get(ip) {
        if *start.elapsed() >= LOGIN_WINDOW {
            map.remove(ip);
        } else if *count >= LOGIN_MAX_ATTEMPTS {
            return Err((StatusCode::TOO_MANY_REQUESTS, "Too many login attempts, try again later".into()));
        }
    }
    Ok(())
}

fn record_login_failure(ip: &str) {
    if let Ok(mut map) = login_attempts().lock() {
        let now = Instant::now();
        let entry = map.entry(ip.to_string()).or_insert((0, now));
        if entry.1.elapsed() >= LOGIN_WINDOW {
            *entry = (1, now);
        } else {
            entry.0 += 1;
        }
    }
}

fn clear_login_failures(ip: &str) {
    if let Ok(mut map) = login_attempts().lock() {
        map.remove(ip);
    }
}

// JWT Claims
#[derive(Debug, Serialize, Deserialize)]
struct Claims {
    sub: i32,
    username: String,
    exp: i64,
}

// Request/Response types
#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    username: String,
    password: String,
}

#[derive(Debug, Serialize)]
pub struct LoginResponse {
    token: String,
    user: UserInfo,
}

#[derive(Debug, Serialize)]
pub struct UserInfo {
    id: i32,
    username: String,
}

#[derive(Debug, Serialize)]
pub struct User {
    id: i32,
    service_key: String,
    email: Option<String>,
    plan: String,
    quota_daily: i32,
    quota_used_today: i32,
    is_active: bool,
    created_at: DateTime<Utc>,
    updated_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct CreateUserRequest {
    email: Option<String>,
    plan: String,
    quota_daily: i32,
}

#[derive(Debug, Deserialize)]
pub struct UpdateUserRequest {
    email: Option<String>,
    plan: Option<String>,
    quota_daily: Option<i32>,
    is_active: Option<bool>,
}

#[derive(Debug, Deserialize)]
pub struct PaginationQuery {
    page: Option<i32>,
    page_size: Option<i32>,
}

#[derive(Debug, Serialize)]
pub struct UserListResponse {
    users: Vec<User>,
    total: i64,
}

#[derive(Debug, Serialize)]
pub struct DashboardStats {
    today_requests: i64,
    success_rate: f64,
    recall_rate: f64,
    p99_latency: Option<i64>,
}

#[derive(Debug, Serialize)]
pub struct QPSDataPoint {
    time: i64,
    qps: i64,
}

#[derive(Debug, Serialize)]
pub struct TrendDataPoint {
    date: String,
    total: i64,
    success: i64,
}

#[derive(Debug, Serialize)]
pub struct RequestLog {
    id: i64,
    user_id: Option<i32>,
    upstream_url: String,
    input_tokens: i32,
    output_tokens: Option<i32>,
    recall_triggered: bool,
    recall_latency_ms: Option<i32>,
    total_latency_ms: i32,
    status: String,
    error_message: Option<String>,
    created_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct LogListResponse {
    logs: Vec<RequestLog>,
    total: i64,
}

// Handlers
pub async fn login_handler(
    State(state): State<AppState>,
    headers: axum::http::HeaderMap,
    Json(req): Json<LoginRequest>,
) -> Result<Json<LoginResponse>, (StatusCode, String)> {
    // 暴力破解防护：按 IP 限流
    let ip = client_ip(&headers);
    check_login_rate_limit(&ip)?;

    // Query admin from database
    let admin = sqlx::query_as::<_, (i32, String, String)>(
        r#"SELECT id, username, password_hash FROM admins WHERE username = $1"#
    )
    .bind(&req.username)
    .fetch_optional(&state.db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .ok_or_else(|| {
        record_login_failure(&ip);
        (StatusCode::UNAUTHORIZED, "用户名或密码错误".to_string())
    })?;

    // Verify password
    let valid = verify(&req.password, &admin.2)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    if !valid {
        record_login_failure(&ip);
        return Err((StatusCode::UNAUTHORIZED, "用户名或密码错误".to_string()));
    }

    clear_login_failures(&ip);

    // Generate JWT
    let exp = (chrono::Utc::now() + chrono::Duration::hours(24)).timestamp();
    let claims = Claims {
        sub: admin.0,
        username: admin.1.clone(),
        exp,
    };

    let token = encode(
        &Header::default(),
        &claims,
        &EncodingKey::from_secret(&state.jwt_secret),
    )
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(LoginResponse {
        token,
        user: UserInfo {
            id: admin.0,
            username: admin.1,
        },
    }))
}

pub async fn list_users_handler(
    State(db): State<PgPool>,
    Query(params): Query<PaginationQuery>,
) -> Result<Json<UserListResponse>, (StatusCode, String)> {
    let page = params.page.unwrap_or(1).max(1);
    let page_size = params.page_size.unwrap_or(20).clamp(1, 100);
    let offset = (page - 1) * page_size;

    let rows = sqlx::query(
        r#"
        SELECT id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
        FROM users
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
        "#
    )
    .bind(page_size as i64)
    .bind(offset as i64)
    .fetch_all(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let users: Vec<User> = rows.iter().map(|row| User {
        id: row.get("id"),
        service_key: row.get("service_key"),
        email: row.get("email"),
        plan: row.get("plan"),
        quota_daily: row.get("quota_daily"),
        quota_used_today: row.get("quota_used_today"),
        is_active: row.get("is_active"),
        created_at: row.get("created_at"),
        updated_at: row.get("updated_at"),
    }).collect();

    let total: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM users")
        .fetch_one(&db)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(UserListResponse {
        users,
        total: total.0,
    }))
}

pub async fn get_user_handler(
    State(db): State<PgPool>,
    Path(id): Path<i32>,
) -> Result<Json<User>, (StatusCode, String)> {
    let row = sqlx::query(
        r#"
        SELECT id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
        FROM users
        WHERE id = $1
        "#
    )
    .bind(id)
    .fetch_optional(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .ok_or((StatusCode::NOT_FOUND, "User not found".to_string()))?;

    let user = User {
        id: row.get("id"),
        service_key: row.get("service_key"),
        email: row.get("email"),
        plan: row.get("plan"),
        quota_daily: row.get("quota_daily"),
        quota_used_today: row.get("quota_used_today"),
        is_active: row.get("is_active"),
        created_at: row.get("created_at"),
        updated_at: row.get("updated_at"),
    };

    Ok(Json(user))
}

pub async fn create_user_handler(
    State(db): State<PgPool>,
    Json(req): Json<CreateUserRequest>,
) -> Result<Json<User>, (StatusCode, String)> {
    // Generate service key
    let service_key = format!("sk-{}", uuid::Uuid::new_v4().simple());

    let row = sqlx::query(
        r#"
        INSERT INTO users (service_key, email, plan, quota_daily)
        VALUES ($1, $2, $3, $4)
        RETURNING id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
        "#
    )
    .bind(&service_key)
    .bind(&req.email)
    .bind(&req.plan)
    .bind(req.quota_daily)
    .fetch_one(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let user = User {
        id: row.get("id"),
        service_key: row.get("service_key"),
        email: row.get("email"),
        plan: row.get("plan"),
        quota_daily: row.get("quota_daily"),
        quota_used_today: row.get("quota_used_today"),
        is_active: row.get("is_active"),
        created_at: row.get("created_at"),
        updated_at: row.get("updated_at"),
    };

    Ok(Json(user))
}

pub async fn update_user_handler(
    State(db): State<PgPool>,
    Path(id): Path<i32>,
    Json(req): Json<UpdateUserRequest>,
) -> Result<Json<User>, (StatusCode, String)> {
    let row = sqlx::query(
        r#"
        UPDATE users
        SET email = COALESCE($2, email),
            plan = COALESCE($3, plan),
            quota_daily = COALESCE($4, quota_daily),
            is_active = COALESCE($5, is_active),
            updated_at = NOW()
        WHERE id = $1
        RETURNING id, service_key, email, plan, quota_daily, quota_used_today, is_active, created_at, updated_at
        "#
    )
    .bind(id)
    .bind(req.email.as_deref())
    .bind(req.plan.as_deref())
    .bind(req.quota_daily)
    .bind(req.is_active)
    .fetch_optional(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
    .ok_or((StatusCode::NOT_FOUND, "User not found".to_string()))?;

    let user = User {
        id: row.get("id"),
        service_key: row.get("service_key"),
        email: row.get("email"),
        plan: row.get("plan"),
        quota_daily: row.get("quota_daily"),
        quota_used_today: row.get("quota_used_today"),
        is_active: row.get("is_active"),
        created_at: row.get("created_at"),
        updated_at: row.get("updated_at"),
    };

    Ok(Json(user))
}

pub async fn delete_user_handler(
    State(db): State<PgPool>,
    Path(id): Path<i32>,
) -> Result<StatusCode, (StatusCode, String)> {
    let result = sqlx::query("DELETE FROM users WHERE id = $1")
        .bind(id)
        .execute(&db)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    if result.rows_affected() == 0 {
        return Err((StatusCode::NOT_FOUND, "User not found".to_string()));
    }

    Ok(StatusCode::OK)
}

pub async fn dashboard_stats_handler(
    State(db): State<PgPool>,
) -> Result<Json<DashboardStats>, (StatusCode, String)> {
    let stats = sqlx::query_as::<_, (i64, i64, i64)>(
        r#"
        SELECT 
            COUNT(*) as "total",
            COUNT(CASE WHEN status = 'success' THEN 1 END) as "success",
            COUNT(CASE WHEN recall_triggered = true THEN 1 END) as "recall"
        FROM request_logs
        WHERE DATE(created_at) = CURRENT_DATE
        "#
    )
    .fetch_one(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let success_rate = if stats.0 > 0 {
        (stats.1 as f64 / stats.0 as f64) * 100.0
    } else {
        0.0
    };

    let recall_rate = if stats.0 > 0 {
        (stats.2 as f64 / stats.0 as f64) * 100.0
    } else {
        0.0
    };

    let p99 = sqlx::query_scalar::<_, Option<f64>>(
        r#"
        SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY total_latency_ms)
        FROM request_logs
        WHERE created_at >= NOW() - INTERVAL '1 hour'
        "#
    )
    .fetch_one(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(DashboardStats {
        today_requests: stats.0,
        success_rate,
        recall_rate,
        p99_latency: p99.map(|v| v as i64),
    }))
}

pub async fn qps_data_handler(
    State(db): State<PgPool>,
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<Json<Vec<QPSDataPoint>>, (StatusCode, String)> {
    let minutes: i32 = params
        .get("minutes")
        .and_then(|s| s.parse().ok())
        .unwrap_or(60)
        .clamp(1, 1440);

    let data = sqlx::query_as::<_, (i64, i64)>(
        r#"
        SELECT 
            EXTRACT(EPOCH FROM DATE_TRUNC('minute', created_at))::bigint as "minute",
            COUNT(*) as "qps"
        FROM request_logs
        WHERE created_at >= NOW() - INTERVAL '1 minute' * $1
        GROUP BY minute
        ORDER BY minute
        "#
    )
    .bind(minutes)
    .fetch_all(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let result = data
        .into_iter()
        .map(|row| QPSDataPoint {
            time: row.0,
            qps: row.1,
        })
        .collect();

    Ok(Json(result))
}

pub async fn trend_data_handler(
    State(db): State<PgPool>,
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<Json<Vec<TrendDataPoint>>, (StatusCode, String)> {
    let days: i32 = params
        .get("days")
        .and_then(|s| s.parse().ok())
        .unwrap_or(7)
        .clamp(1, 90);

    let data = sqlx::query_as::<_, (chrono::NaiveDate, i64, i64)>(
        r#"
        SELECT 
            DATE(created_at) as "day",
            COUNT(*) as "total",
            COUNT(CASE WHEN status = 'success' THEN 1 END) as "success"
        FROM request_logs
        WHERE created_at >= CURRENT_DATE - INTERVAL '1 day' * $1
        GROUP BY day
        ORDER BY day
        "#
    )
    .bind(days)
    .fetch_all(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let result = data
        .into_iter()
        .map(|row| TrendDataPoint {
            date: row.0.format("%Y-%m-%d").to_string(),
            total: row.1,
            success: row.2,
        })
        .collect();

    Ok(Json(result))
}

pub async fn list_logs_handler(
    State(db): State<PgPool>,
    Query(params): Query<std::collections::HashMap<String, String>>,
) -> Result<Json<LogListResponse>, (StatusCode, String)> {
    let page: i32 = params
        .get("page")
        .and_then(|s| s.parse().ok())
        .unwrap_or(1)
        .max(1);
    let page_size: i32 = params
        .get("page_size")
        .and_then(|s| s.parse().ok())
        .unwrap_or(50)
        .clamp(1, 100);
    let user_id: Option<i32> = params.get("user_id").and_then(|s| s.parse().ok());
    let offset = (page - 1) * page_size;

    let rows = if let Some(uid) = user_id {
        sqlx::query(
            r#"
            SELECT id, user_id, upstream_url, input_tokens, output_tokens,
                   recall_triggered, recall_latency_ms, total_latency_ms, status, error_message, created_at
            FROM request_logs
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
            "#
        )
        .bind(uid)
        .bind(page_size as i64)
        .bind(offset as i64)
        .fetch_all(&db)
        .await
    } else {
        sqlx::query(
            r#"
            SELECT id, user_id, upstream_url, input_tokens, output_tokens,
                   recall_triggered, recall_latency_ms, total_latency_ms, status, error_message, created_at
            FROM request_logs
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            "#
        )
        .bind(page_size as i64)
        .bind(offset as i64)
        .fetch_all(&db)
        .await
    }
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let logs: Vec<RequestLog> = rows.iter().map(|row| RequestLog {
        id: row.get("id"),
        user_id: row.get("user_id"),
        upstream_url: row.get("upstream_url"),
        input_tokens: row.get("input_tokens"),
        output_tokens: row.get("output_tokens"),
        recall_triggered: row.get("recall_triggered"),
        recall_latency_ms: row.get("recall_latency_ms"),
        total_latency_ms: row.get("total_latency_ms"),
        status: row.get("status"),
        error_message: row.get("error_message"),
        created_at: row.get("created_at"),
    }).collect();

    let total: (i64,) = if let Some(uid) = user_id {
        sqlx::query_as("SELECT COUNT(*) FROM request_logs WHERE user_id = $1")
            .bind(uid)
            .fetch_one(&db)
            .await
    } else {
        sqlx::query_as("SELECT COUNT(*) FROM request_logs")
            .fetch_one(&db)
            .await
    }
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    Ok(Json(LogListResponse {
        logs,
        total: total.0,
    }))
}

// 系统配置相关（持久化到 system_config 表，实时生效）
#[derive(Debug, Serialize)]
pub struct SystemConfig {
    recall_service_urls: Vec<String>,
    recall_threshold: usize,
    recall_target: usize,
    rate_limit_per_minute: u32,
    max_context_length: usize,
    upstream_timeout_secs: u64,
}

#[derive(Debug, Deserialize)]
pub struct UpdateSystemConfigRequest {
    recall_service_urls: Option<Vec<String>>,
    recall_threshold: Option<usize>,
    recall_target: Option<usize>,
    rate_limit_per_minute: Option<u32>,
    max_context_length: Option<usize>,
    upstream_timeout_secs: Option<u64>,
    // 兼容前端 { key, value } 单字段更新模式
    key: Option<String>,
    value: Option<String>,
}

fn to_system_config(cfg: &RuntimeConfig) -> SystemConfig {
    SystemConfig {
        recall_service_urls: vec![
            "http://localhost:8001".to_string(),
            "http://localhost:8002".to_string(),
        ],
        recall_threshold: cfg.recall_threshold,
        recall_target: cfg.recall_target,
        rate_limit_per_minute: cfg.rate_limit_per_minute,
        max_context_length: cfg.max_context_length,
        upstream_timeout_secs: cfg.upstream_timeout_secs,
    }
}

pub async fn get_system_config_handler(
    State(state): State<AppState>,
) -> Result<Json<SystemConfig>, (StatusCode, String)> {
    let map = get_system_config_all(&state.db)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let cfg = RuntimeConfig::from_map(&map);
    Ok(Json(to_system_config(&cfg)))
}

pub async fn update_system_config_handler(
    State(state): State<AppState>,
    Json(req): Json<UpdateSystemConfigRequest>,
) -> Result<Json<SystemConfig>, (StatusCode, String)> {
    // 单字段 { key, value } 模式（前端表单逐项保存）
    if let (Some(k), Some(v)) = (req.key.as_deref(), req.value.as_deref()) {
        set_system_config(&state.db, k, v)
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    } else {
        // 多字段模式
        let updates: Vec<(&str, String)> = [
            ("recall_threshold", req.recall_threshold.map(|v| v.to_string())),
            ("recall_target", req.recall_target.map(|v| v.to_string())),
            ("rate_limit_per_minute", req.rate_limit_per_minute.map(|v| v.to_string())),
            ("max_context_length", req.max_context_length.map(|v| v.to_string())),
            ("upstream_timeout_secs", req.upstream_timeout_secs.map(|v| v.to_string())),
        ].into_iter().filter_map(|(k, v)| v.map(|v| (k, v))).collect();
        for (k, v) in updates {
            set_system_config(&state.db, k, &v)
                .await
                .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
        }
    }

    // 重载运行时配置（无需重启，立即生效）
    let map = get_system_config_all(&state.db)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let cfg = RuntimeConfig::from_map(&map);
    *state.config.write().map_err(|_| (StatusCode::INTERNAL_SERVER_ERROR, "config lock poisoned".into()))? = cfg.clone();

    Ok(Json(to_system_config(&cfg)))
}

// 增强的统计端点
#[derive(Debug, Serialize)]
pub struct DetailedStats {
    total_users: i64,
    active_users: i64,
    total_requests_today: i64,
    total_requests_all_time: i64,
    avg_latency_ms: f64,
    recall_triggered_today: i64,
    error_rate_today: f64,
}

pub async fn detailed_stats_handler(
    State(db): State<PgPool>,
) -> Result<Json<DetailedStats>, (StatusCode, String)> {
    let user_stats = sqlx::query_as::<_, (i64, i64)>(
        r#"
        SELECT 
            COUNT(*) as "total",
            COUNT(CASE WHEN is_active = true THEN 1 END) as "active"
        FROM users
        "#
    )
    .fetch_one(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let request_stats = sqlx::query_as::<_, (i64, i64, Option<f64>, i64)>(
        r#"
        SELECT 
            COUNT(*) as "total_today",
            COUNT(CASE WHEN recall_triggered = true THEN 1 END) as "recall_today",
            AVG(total_latency_ms) as "avg_latency",
            COUNT(CASE WHEN status != 'success' THEN 1 END) as "errors_today"
        FROM request_logs
        WHERE DATE(created_at) = CURRENT_DATE
        "#
    )
    .fetch_one(&db)
    .await
    .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let total_all_time: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM request_logs")
        .fetch_one(&db)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

    let error_rate = if request_stats.0 > 0 {
        (request_stats.3 as f64 / request_stats.0 as f64) * 100.0
    } else {
        0.0
    };

    Ok(Json(DetailedStats {
        total_users: user_stats.0,
        active_users: user_stats.1,
        total_requests_today: request_stats.0,
        total_requests_all_time: total_all_time.0,
        avg_latency_ms: request_stats.2.unwrap_or(0.0),
        recall_triggered_today: request_stats.1,
        error_rate_today: error_rate,
    }))
}
