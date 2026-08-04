use multi_tier_cache::{CacheSystem, CacheStrategy};
use bytes::Bytes;
use std::time::Duration;
use crate::error::{RecallError, Result};

/// 高性能多层缓存管理器
/// L1: Moka 内存缓存 (< 1ms)
/// L2: Redis 分布式缓存 (2-5ms)
pub struct CacheManager {
    cache: CacheSystem,
}

impl CacheManager {
    /// 创建缓存管理器
    pub async fn new(redis_url: &str) -> Result<Self> {
        let cache = CacheSystem::with_redis_url(redis_url)
            .await
            .map_err(|e| RecallError::Cache(e.to_string()))?;
        
        Ok(Self { cache })
    }

    /// 获取 embedding 缓存
    /// 键格式: "emb:v1:{model}:{hash}"
    pub async fn get_embedding(&self, key: &str) -> Result<Option<Vec<f32>>> {
        match self.cache.cache_manager().get(key).await {
            Ok(Some(bytes)) => {
                let vec: Vec<f32> = serde_json::from_slice(&bytes)
                    .map_err(|e| RecallError::Serialization(e))?;
                Ok(Some(vec))
            }
            Ok(None) => Ok(None),
            Err(e) => Err(RecallError::Cache(e.to_string())),
        }
    }

    /// 设置 embedding 缓存 (1小时 TTL)
    pub async fn set_embedding(&self, key: &str, embedding: &[f32]) -> Result<()> {
        let bytes = Bytes::from(serde_json::to_vec(embedding)?);
        
        self.cache.cache_manager()
            .set_with_strategy(key, bytes, CacheStrategy::MediumTerm)
            .await
            .map_err(|e| RecallError::Cache(e.to_string()))?;
        
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
        let stats = self.cache.cache_manager().get_stats();
        
        CacheStats {
            hit_rate: stats.hit_rate,
            total_hits: stats.total_hits,
            total_misses: stats.total_misses,
        }
    }

    /// 清除所有缓存
    pub async fn clear_all(&self) -> Result<()> {
        self.cache.cache_manager()
            .invalidate_all()
            .await
            .map_err(|e| RecallError::Cache(e.to_string()))?;
        
        Ok(())
    }
}

#[derive(Debug, Clone)]
pub struct CacheStats {
    pub hit_rate: f64,
    pub total_hits: u64,
    pub total_misses: u64,
}
