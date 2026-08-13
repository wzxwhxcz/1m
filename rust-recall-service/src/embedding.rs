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
    embeddings_url: String,
    api_key: String,
    model: String,
    cache: Arc<CacheManager>,
    batch_size: usize,
    max_chars: usize,
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
    #[serde(default)]
    index: usize,
}

/// 兼容三种写法：
/// - `http://host`           → `{host}/v1/embeddings`
/// - `http://host/v1`        → `{host}/v1/embeddings`
/// - `http://host/v1/embeddings` 原样
pub fn embeddings_url(api_base: &str) -> String {
    let base = api_base.trim().trim_end_matches('/');
    if base.ends_with("/embeddings") {
        base.to_string()
    } else if base.ends_with("/v1") {
        format!("{}/embeddings", base)
    } else {
        format!("{}/v1/embeddings", base)
    }
}

/// 按 Unicode 字符截断。超长文本取文首 75% + 文尾 25%（章末点题），避免只看开头。
pub fn truncate_chars(text: &str, max_chars: usize) -> String {
    if max_chars == 0 {
        return text.to_string();
    }
    let total = text.chars().count();
    if total <= max_chars {
        return text.to_string();
    }
    // 很短的预算退化为纯前缀，保证单测和短查询行为稳定
    if max_chars < 32 {
        return text.chars().take(max_chars).collect();
    }
    let tail_n = (max_chars / 4).max(1);
    let head_n = max_chars.saturating_sub(tail_n + 1);
    let head: String = text.chars().take(head_n).collect();
    let tail: String = text.chars().skip(total.saturating_sub(tail_n)).collect();
    format!("{head}…{tail}")
}

impl RemoteEmbeddingClient {
    pub async fn new(
        api_base: String,
        api_key: String,
        model: String,
        cache: Arc<CacheManager>,
    ) -> Result<Self> {
        let timeout_secs: u64 = std::env::var("EMBEDDING_TIMEOUT_SECS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(120);
        let batch_size: usize = std::env::var("EMBEDDING_BATCH_SIZE")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(32);
        let max_chars: usize = std::env::var("EMBEDDING_MAX_CHARS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(1024);

        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs.max(30)))
            .connect_timeout(Duration::from_secs(10))
            .build()
            .map_err(RecallError::Http)?;

        let embeddings_url = embeddings_url(&api_base);
        tracing::info!(
            embeddings_url = %embeddings_url,
            timeout_secs,
            batch_size,
            max_chars,
            "Embedding client ready"
        );

        Ok(Self {
            client,
            embeddings_url,
            api_key,
            model,
            cache,
            batch_size: batch_size.max(1),
            max_chars: max_chars.max(64),
        })
    }

    fn cache_key(&self, text: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        let hash = hasher.finish();

        format!("emb:v3:{}:{}:{:x}", self.model, self.max_chars, hash)
    }

    async fn call_api_once(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        let request = EmbeddingRequest {
            model: self.model.clone(),
            input: texts.to_vec(),
        };

        let response = self.client
            .post(&self.embeddings_url)
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
        let mut data = result.data;
        data.sort_by_key(|d| d.index);
        Ok(data.into_iter().map(|d| d.embedding).collect())
    }

    async fn call_api(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(Vec::new());
        }
        let mut all = Vec::with_capacity(texts.len());
        for chunk in texts.chunks(self.batch_size) {
            let part = self.call_api_once(chunk).await?;
            if part.len() != chunk.len() {
                return Err(RecallError::Embedding(format!(
                    "embedding count mismatch: sent {} got {}",
                    chunk.len(),
                    part.len()
                )));
            }
            all.extend(part);
        }
        Ok(all)
    }
}

#[async_trait::async_trait]
impl EmbeddingService for RemoteEmbeddingClient {
    async fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let text = truncate_chars(text, self.max_chars);
        let cache_key = self.cache_key(&text);

        if let Some(cached) = self.cache.get_embedding(&cache_key).await? {
            return Ok(cached);
        }

        let embeddings = self.call_api(vec![text]).await?;

        if embeddings.is_empty() {
            return Err(RecallError::Embedding("Empty response".to_string()));
        }

        let embedding = embeddings[0].clone();
        self.cache.set_embedding(&cache_key, &embedding).await?;
        Ok(embedding)
    }

    async fn embed_batch(&self, texts: Vec<String>) -> Result<Vec<Vec<f32>>> {
        let texts: Vec<String> = texts
            .iter()
            .map(|t| truncate_chars(t, self.max_chars))
            .collect();
        let cache_keys: Vec<String> = texts.iter().map(|t| self.cache_key(t)).collect();

        let cached = self.cache.get_embeddings_batch(&cache_keys).await?;

        let mut to_fetch = Vec::new();
        let mut to_fetch_indices = Vec::new();

        for (i, cached_emb) in cached.iter().enumerate() {
            if cached_emb.is_none() {
                to_fetch.push(texts[i].clone());
                to_fetch_indices.push(i);
            }
        }

        let fetched = if !to_fetch.is_empty() {
            tracing::info!(
                fetch = to_fetch.len(),
                cached = texts.len() - to_fetch.len(),
                "Embedding cache miss, calling API"
            );
            self.call_api(to_fetch).await?
        } else {
            Vec::new()
        };

        if fetched.len() != to_fetch_indices.len() {
            return Err(RecallError::Embedding(format!(
                "embedding count mismatch: expected {} got {}",
                to_fetch_indices.len(),
                fetched.len()
            )));
        }

        let mut results: Vec<Option<Vec<f32>>> = cached;
        for (idx, embedding) in to_fetch_indices.into_iter().zip(fetched.into_iter()) {
            results[idx] = Some(embedding.clone());
            let cache_key = cache_keys[idx].clone();
            let cache = self.cache.clone();
            tokio::spawn(async move {
                let _ = cache.set_embedding(&cache_key, &embedding).await;
            });
        }

        results
            .into_iter()
            .enumerate()
            .map(|(i, v)| {
                v.ok_or_else(|| RecallError::Embedding(format!("missing embedding at {i}")))
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embeddings_url_normalizes_host_only() {
        assert_eq!(
            embeddings_url("http://router.tumuer.me"),
            "http://router.tumuer.me/v1/embeddings"
        );
        assert_eq!(
            embeddings_url("http://router.tumuer.me/"),
            "http://router.tumuer.me/v1/embeddings"
        );
    }

    #[test]
    fn embeddings_url_keeps_v1_and_full_path() {
        assert_eq!(
            embeddings_url("http://router.tumuer.me/v1"),
            "http://router.tumuer.me/v1/embeddings"
        );
        assert_eq!(
            embeddings_url("https://router.tumuer.me/v1/embeddings"),
            "https://router.tumuer.me/v1/embeddings"
        );
    }

    #[test]
    fn truncate_chars_cuts_on_unicode_boundary() {
        let s = "三体罗辑黑暗森林";
        assert_eq!(truncate_chars(s, 2), "三体");
        assert_eq!(truncate_chars(s, 100), s);
    }

    #[test]
    fn truncate_chars_keeps_head_and_tail_on_long_text() {
        let s: String = (0..100).map(|i| char::from_u32(0x4e00 + i).unwrap()).collect();
        let out = truncate_chars(&s, 40);
        let chars: Vec<char> = out.chars().collect();
        assert!(chars.contains(&'…'), "{out}");
        assert_eq!(chars[0], s.chars().next().unwrap());
        assert_eq!(chars[chars.len() - 1], s.chars().last().unwrap());
        assert!(chars.len() <= 40, "{}", chars.len());
    }
}
