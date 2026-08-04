pub mod cache;
pub mod embedding;
pub mod recall;
pub mod metrics;
pub mod error;

pub use cache::CacheManager;
pub use embedding::{EmbeddingService, RemoteEmbeddingClient};
pub use recall::{RecallAlgorithm, RecallService, RecallRequest, RecallResponse};
pub use error::{RecallError, Result};
