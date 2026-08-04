use thiserror::Error;

#[derive(Error, Debug)]
pub enum RecallError {
    #[error("Cache error: {0}")]
    Cache(String),
    
    #[error("Embedding error: {0}")]
    Embedding(String),
    
    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),
    
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
    
    #[error("Redis error: {0}")]
    Redis(String),
    
    #[error("Invalid input: {0}")]
    InvalidInput(String),
    
    #[error("Internal error: {0}")]
    Internal(String),
}

pub type Result<T> = std::result::Result<T, RecallError>;
