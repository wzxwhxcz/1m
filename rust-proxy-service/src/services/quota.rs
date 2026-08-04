use crate::models::User;
use crate::error::{ProxyError, Result};
use crate::DbPool;
use redis::AsyncCommands;

pub struct QuotaService {
    pool: DbPool,
    redis_client: Option<redis::Client>,
}

impl QuotaService {
    pub fn new(pool: DbPool, redis_url: Option<&str>) -> Result<Self> {
        let redis_client = if let Some(url) = redis_url {
            Some(redis::Client::open(url)
                .map_err(|e| ProxyError::Internal(format!("Failed to connect to Redis: {}", e)))?)
        } else {
            None
        };

        Ok(Self { pool, redis_client })
    }

    /// 检查用户是否有剩余配额
    pub async fn check_quota(&self, user: &User) -> Result<bool> {
        // 先检查数据库配额
        if !user.has_quota() {
            return Ok(false);
        }

        // 如果有 Redis，使用 Redis 进行实时配额检查
        if let Some(redis_client) = &self.redis_client {
            let mut conn = redis_client.get_multiplexed_async_connection()
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

            let key = format!("quota:user:{}:requests", user.id);
            let count: i64 = conn.get(&key)
                .await
                .unwrap_or(0);

            if count >= user.quota_daily as i64 {
                return Ok(false);
            }
        }

        Ok(true)
    }

    /// 递增用户配额使用计数
    pub async fn increment_quota(&self, user: &User, input_tokens: i32, output_tokens: i32) -> Result<()> {
        // 更新数据库
        user.increment_tokens(&self.pool, input_tokens, output_tokens).await?;

        // 更新 Redis 缓存
        if let Some(redis_client) = &self.redis_client {
            let mut conn = redis_client.get_multiplexed_async_connection()
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

            let key = format!("quota:user:{}:requests", user.id);
            let _: i64 = conn.incr(&key, 1)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis INCR error: {}", e)))?;

            // 设置过期时间为 24 小时
            let _: () = conn.expire(&key, 86400)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis EXPIRE error: {}", e)))?;

            // 记录 Token 使用
            let tokens_key = format!("quota:user:{}:tokens", user.id);
            let _: i64 = conn.incr(&tokens_key, (input_tokens + output_tokens) as i64)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis INCR error: {}", e)))?;
            
            let _: () = conn.expire(&tokens_key, 86400)
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis EXPIRE error: {}", e)))?;
        }

        Ok(())
    }

    /// 获取用户剩余配额
    pub async fn get_remaining_quota(&self, user: &User) -> Result<i32> {
        if let Some(redis_client) = &self.redis_client {
            let mut conn = redis_client.get_multiplexed_async_connection()
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

            let key = format!("quota:user:{}:requests", user.id);
            let used: i64 = conn.get(&key)
                .await
                .unwrap_or(user.quota_used_today as i64);

            Ok((user.quota_daily as i64 - used).max(0) as i32)
        } else {
            Ok(user.remaining_quota())
        }
    }

    /// 重置所有用户的每日配额（定时任务调用）
    pub async fn reset_all_daily_quotas(&self) -> Result<u64> {
        let count = User::reset_daily_quota(&self.pool).await?;

        // 清除 Redis 缓存
        if let Some(redis_client) = &self.redis_client {
            let mut conn = redis_client.get_multiplexed_async_connection()
                .await
                .map_err(|e| ProxyError::Internal(format!("Redis connection error: {}", e)))?;

            // 删除所有配额相关的 key
            let pattern = "quota:user:*";
            let keys: Vec<String> = redis::cmd("KEYS")
                .arg(pattern)
                .query_async(&mut conn)
                .await
                .unwrap_or_default();

            if !keys.is_empty() {
                let _: () = conn.del(keys)
                    .await
                    .map_err(|e| ProxyError::Internal(format!("Redis DEL error: {}", e)))?;
            }
        }

        Ok(count)
    }
}
