use moka::future::Cache;
use bytes::Bytes;
use std::time::Duration;
use crate::error::Result;

/// 高性能内存缓存管理器
/// 使用 Moka 提供高性能 LRU 缓存
pub struct CacheManager {
    cache: Cache<String, Bytes>,
}

impl CacheManager {
    /// 创建缓存管理器
    pub async fn new(_redis_url: &str) -> Result<Self> {
        // 5 万条目、24h TTL：同一会话二次压缩应几乎全命中
        let cache = Cache::builder()
            .max_capacity(50_000)
            .time_to_live(Duration::from_secs(24 * 3600))
            .build();
        
        Ok(Self { cache })
    }

    /// 获取 embedding 缓存
    /// 键格式: "emb:v1:{model}:{hash}"
    pub async fn get_embedding(&self, key: &str) -> Result<Option<Vec<f32>>> {
        match self.cache.get(&key.to_string()).await {
            Some(bytes) => {
                let vec: Vec<f32> = serde_json::from_slice(&bytes)?;
                Ok(Some(vec))
            }
            None => Ok(None),
        }
    }

    /// 设置 embedding 缓存 (1小时 TTL)
    pub async fn set_embedding(&self, key: &str, embedding: &[f32]) -> Result<()> {
        let bytes = Bytes::from(serde_json::to_vec(embedding)?);
        self.cache.insert(key.to_string(), bytes).await;
        Ok(())
    }

    /// 批量获取 embeddings
    pub async fn get_embeddings_batch(&self, keys: &[String]) -> Result<Vec<Option<Vec<f32>>>> {
        let mut results = Vec::with_capacity(keys.len());
        
        for key in keys {
            results.push(self.get_embedding(key).await?);
        }
        
        Ok(results)
    }

    /// 批量设置 embeddings
    pub async fn set_embeddings_batch(&self, items: Vec<(String, Vec<f32>)>) -> Result<()> {
        for (key, embedding) in items {
            self.set_embedding(&key, &embedding).await?;
        }
        
        Ok(())
    }

    /// 获取缓存统计
    pub fn get_stats(&self) -> CacheStats {
        let entry_count = self.cache.entry_count();
        let weighted_size = self.cache.weighted_size();
        
        CacheStats {
            entry_count,
            weighted_size,
            hit_rate: 0.0, // Moka 不提供命中率统计
        }
    }

    /// 清除所有缓存
    pub async fn clear_all(&self) -> Result<()> {
        self.cache.invalidate_all();
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct CacheStats {
    pub entry_count: u64,
    pub weighted_size: u64,
    pub hit_rate: f64,
}
