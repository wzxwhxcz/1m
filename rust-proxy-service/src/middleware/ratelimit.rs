use tower_governor::{
    governor::GovernorConfigBuilder,
    GovernorLayer,
};
use std::time::Duration;
use redis::AsyncCommands;
use crate::error::{ProxyError, Result};

pub struct RateLimitMiddleware;

impl RateLimitMiddleware {
    pub fn layer(requests_per_minute: u64) -> GovernorLayer<impl tower_governor::key_extractor::KeyExtractor, tower_governor::governor::DefaultDirectRateLimiter> {
        let config = GovernorConfigBuilder::default()
            .per_second(requests_per_minute / 60)
            .burst_size(requests_per_minute as u32)
            .finish()
            .unwrap();

        GovernorLayer { config: Box::leak(Box::new(config)) }
    }
}

/// Redis 基于的用户速率限制
pub struct RedisRateLimiter {
    redis_client: redis::Client,
}

impl RedisRateLimiter {
    pub fn new(redis_url: &str) -> Result<Self> {
        let redis_client = redis::Client::open(redis_url)
            .map_err(|e| ProxyError::Internal(format!("Failed to connect to Redis: {}", e)))?;
        
        Ok(Self { redis_client })
    }

    /// 检查用户速率限制
    /// 返回 Ok(()) 表示通过，Err 表示超过限制
    pub async fn check_rate_limit(
        &self,
        user_id: i64,
        limit_per_minute: i64,
    ) -> Result<()> {
        let mut conn = self.redis_client.get_multiplexed_async_connection()
            .await
            .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

        let key = format!("rate_limit:user:{}:minute", user_id);
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let window_key = format!("{}:{}", key, current_time / 60);

        // 使用 INCR 和 EXPIRE 实现滑动窗口
        let count: i64 = conn.incr(&window_key, 1)
            .await
            .map_err(|e| ProxyError::Internal(format!("Redis INCR error: {}", e)))?;

        if count == 1 {
            // 第一次访问，设置过期时间
            let _: () = conn.expire(&window_key, 70)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis EXPIRE error: {}", e)))?;
        }

        if count > limit_per_minute {
            crate::metrics::RATE_LIMIT_EXCEEDED.inc();
            return Err(ProxyError::RateLimitExceeded);
        }

        Ok(())
    }

    /// 检查每日配额
    pub async fn check_daily_quota(
        &self,
        user_id: i64,
        daily_limit: i64,
    ) -> Result<i64> {
        let mut conn = self.redis_client.get_multiplexed_async_connection()
            .await
            .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

        let key = format!("quota:user:{}:day", user_id);
        let current_time = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        let day_key = format!("{}:{}", key, current_time / 86400);

        let count: i64 = conn.incr(&day_key, 1)
            .await
            .map_err(|e| ProxyError::Internal(format!("Redis INCR error: {}", e)))?;

        if count == 1 {
            let _: () = conn.expire(&day_key, 90000)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis EXPIRE error: {}", e)))?;
        }

        if count > daily_limit {
            return Err(ProxyError::RateLimitExceeded);
        }

        Ok(daily_limit - count)
    }
}
