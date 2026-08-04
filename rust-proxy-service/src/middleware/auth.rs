use axum::{
    extract::{Request, State},
    http::HeaderMap,
    middleware::Next,
    response::Response,
};
use crate::{error::ProxyError, models::User, DbPool};

#[derive(Clone)]
pub struct AuthMiddleware {
    pub pool: DbPool,
}

impl AuthMiddleware {
    pub fn new(pool: DbPool) -> Self {
        Self { pool }
    }
}

pub async fn auth_middleware(
    State(pool): State<DbPool>,
    headers: HeaderMap,
    mut request: Request,
    next: Next,
) -> Result<Response, ProxyError> {
    // 尝试从多个来源提取 service_key
    let service_key = extract_service_key(&headers, &request)?;

    // Validate service key
    let user = User::find_by_service_key(&pool, &service_key)
        .await?
        .ok_or_else(|| {
            crate::metrics::AUTH_FAILURES.inc();
            ProxyError::InvalidServiceKey
        })?;

    // Check quota
    if !user.has_quota() {
        crate::metrics::RATE_LIMIT_EXCEEDED.inc();
        return Err(ProxyError::RateLimitExceeded);
    }

    // Store user in request extensions
    request.extensions_mut().insert(user);

    Ok(next.run(request).await)
}

fn extract_service_key(headers: &HeaderMap, request: &Request) -> Result<String, ProxyError> {
    // 1. 尝试从路径提取 (/:service_key/...)
    let path = request.uri().path();
    let path_segments: Vec<&str> = path.split('/').filter(|s| !s.is_empty()).collect();
    
    if !path_segments.is_empty() {
        let first_segment = path_segments[0];
        // 检查是否是 service_key 格式 (sk-xxx)
        if first_segment.starts_with("sk-") {
            return Ok(first_segment.to_string());
        }
    }

    // 2. 尝试从 X-Service-Key header
    if let Some(key) = headers.get("x-service-key") {
        if let Ok(key_str) = key.to_str() {
            return Ok(key_str.to_string());
        }
    }

    // 3. 尝试从 Authorization header
    if let Some(auth) = headers.get("authorization") {
        if let Ok(auth_str) = auth.to_str() {
            let key = if auth_str.starts_with("Bearer ") {
                &auth_str[7..]
            } else {
                auth_str
            };
            return Ok(key.to_string());
        }
    }

    Err(ProxyError::InvalidServiceKey)
}
