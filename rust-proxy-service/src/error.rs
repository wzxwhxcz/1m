use thiserror::Error;
use axum::{
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde_json::json;

#[derive(Error, Debug)]
pub enum ProxyError {
    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),
    
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
    
    #[error("Hyper error: {0}")]
    Hyper(#[from] hyper::Error),
    
    #[error("Invalid service key")]
    InvalidServiceKey,
    
    #[error("Bad request: {0}")]
    BadRequest(String),
    
    #[error("Unauthorized: {0}")]
    Unauthorized(String),
    
    #[error("Rate limit exceeded")]
    RateLimitExceeded,
    
    #[error("Invalid URL: {0}")]
    InvalidUrl(String),
    
    #[error("Upstream error: {0}")]
    Upstream(String),
    
    #[error("Internal error: {0}")]
    Internal(String),
}

pub type Result<T> = std::result::Result<T, ProxyError>;

impl IntoResponse for ProxyError {
    fn into_response(self) -> Response {
        let (status, message) = match self {
            ProxyError::InvalidServiceKey => (StatusCode::UNAUTHORIZED, self.to_string()),
            ProxyError::BadRequest(_) => (StatusCode::BAD_REQUEST, self.to_string()),
            ProxyError::Unauthorized(_) => (StatusCode::UNAUTHORIZED, self.to_string()),
            ProxyError::RateLimitExceeded => (StatusCode::TOO_MANY_REQUESTS, self.to_string()),
            ProxyError::InvalidUrl(_) => (StatusCode::BAD_REQUEST, self.to_string()),
            ProxyError::Upstream(_) => (StatusCode::BAD_GATEWAY, self.to_string()),
            _ => (StatusCode::INTERNAL_SERVER_ERROR, self.to_string()),
        };

        let body = Json(json!({
            "error": message,
        }));

        (status, body).into_response()
    }
}
