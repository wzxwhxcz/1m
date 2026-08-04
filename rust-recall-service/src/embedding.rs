use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use std::sync::Arc;
use crate::error::{RecallError, Result};
use crate::cache::CacheManager;

/// Embedding 服务 trait
#[async_trait::async_trait]
pub trait EmbeddingService: Send + Sync {
    async fn embed(&self, text: &str) -> Result<Vec<f32>>;
    async fn embed_batch(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>>;
}

/// 远程 Embedding API 客户端
pub struct RemoteEmbeddingClient {
    client: Client,
    api_base: String,
    api_key: String,
    model: String,
    cache: Arc<CacheManager>,
}

#[derive(Serialize)]
struct EmbeddingRequest {
    model: String,
    input: Vec<String>,
}

#[derive(Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}

impl RemoteEmbeddingClient {
    pub async fn new(
        api_base: String,
        api_key: String,
        model: String,
        cache: Arc<CacheManager>,
    ) -> Result<Self> {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .map_err(|e| RecallError::Http(e))?;
        
        Ok(Self {
            client,
            api_base,
            api_key,
            model,
            cache,
        })
    }

    fn cache_key(&self, text: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        
        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        let hash = hasher.finish();
        
        format!("emb:v1:{}:{:x}", self.model, hash)
    }

    async fn call_api(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        let request = EmbeddingRequest {
            model: self.model.clone(),
            input: texts,
        };

        let response = self.client
            .post(&format!("{}/embeddings", self.api_base))
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&request)
            .send()
            .await?;

        if !response.status().is_success() {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            return Err(RecallError::Embedding(format!(
                "API error {}: {}",
                status, body
            )));
        }

        let result: EmbeddingResponse = response.json().await?;
        Ok(result.data.into_iter().map(|d| d.embedding).collect())
    }
}

#[async_trait::async_trait]
impl EmbeddingService for RemoteEmbeddingClient {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let cache_key = self.cache_key(text);
        
        // 检查缓存
        if let Some(cached) = self.cache.get_embedding(&cache_key).await? {
            return Ok(cached);
        }
        
        // 调用 API
        let embeddings = self.call_api(vec![text.to_string()]).await?;
        
        if embeddings.is_empty() {
            return Err(RecallError::Embedding("Empty response".to_string()));
        }
        
        let embedding = embeddings[0].clone();
        
        // 写入缓存
        self.cache.set_embedding(&cache_key, &embedding).await?;
        
        Ok(embedding)
    }

    async fn embed_batch(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        let cache_keys: Vec<String> = texts.iter().map(|t| self.cache_key(t)).collect();
        
        // 批量检查缓存
        let cached = self.cache.get_embeddings_batch(&cache_keys).await?;
        
        // 找出需要调用 API 的文本
        let mut to_fetch = Vec::new();
        let mut to_fetch_indices = Vec::new();
        
        for (i, cached_emb) in cached.iter().enumerate() {
            if cached_emb.is_none() {
                to_fetch.push(texts[i].clone());
                to_fetch_indices.push(i);
            }
        }
        
        // 调用 API 获取缺失的 embeddings
        let fetched = if !to_fetch.is_empty() {
            self.call_api(to_fetch).await?
        } else {
            Vec::new()
        };
        
        // 合并结果
        let mut results: Vec<Option<Vec<f32>>> = cached;
        for (idx, embedding) in to_fetch_indices.into_iter().zip(fetched.into_iter()) {
            results[idx] = Some(embedding.clone());
            
            // 异步写入缓存（不阻塞）
            let cache_key = cache_keys[idx].clone();
            let cache = self.cache.clone();
            tokio::spawn(async move {
                let _ = cache.set_embedding(&cache_key, &embedding).await;
            });
        }
        
        // 所有结果都应该有值
        Ok(results.into_iter().filter_map(|x| x).collect())
    }
}

