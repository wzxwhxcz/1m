use serde::Deserialize;

/// 运行时可调参数（管理后台 system_config 动态更新，无需重启）
#[derive(Debug, Clone)]
pub struct RuntimeConfig {
    /// 触发上下文压缩的阈值（原 CONTEXT_THRESHOLD，默认 1M tokens）
    pub recall_threshold: usize,
    /// 压缩目标 tokens（原 RECALL_TARGET，默认 400K）
    pub recall_target: usize,
    /// 每分钟请求限流（预留，当前未强制）
    pub rate_limit_per_minute: u32,
    /// 允许的最大输入 tokens（超过拒绝 413）
    pub max_context_length: usize,
    /// 上游请求超时（秒）
    pub upstream_timeout_secs: u64,
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            recall_threshold: 1_000_000,
            recall_target: 400_000,
            rate_limit_per_minute: 60,
            max_context_length: 2_000_000,
            upstream_timeout_secs: 300,
        }
    }
}

impl RuntimeConfig {
    pub fn from_map(map: &std::collections::HashMap<String, String>) -> Self {
        let base = Self::default();
        fn parse<T: std::str::FromStr>(map: &std::collections::HashMap<String, String>, key: &str, default: T) -> T {
            map.get(key).and_then(|v| v.parse().ok()).unwrap_or(default)
        }
        Self {
            recall_threshold: parse(map, "recall_threshold", base.recall_threshold),
            recall_target: parse(map, "recall_target", base.recall_target),
            rate_limit_per_minute: parse(map, "rate_limit_per_minute", base.rate_limit_per_minute),
            max_context_length: parse(map, "max_context_length", base.max_context_length),
            upstream_timeout_secs: parse(map, "upstream_timeout_secs", base.upstream_timeout_secs),
        }
    }
}

/// JWT 密钥：优先环境变量 JWT_SECRET（≥32 字节）；
/// 未配置时生成进程级随机密钥（重启即失效，避免硬编码常量被伪造 token）
pub fn jwt_secret() -> Vec<u8> {
    if let Ok(s) = std::env::var("JWT_SECRET") {
        let b: Vec<u8> = s.into_bytes();
        if b.len() >= 32 {
            return b;
        }
        tracing::warn!("JWT_SECRET 长度不足 32 字节，忽略并使用随机密钥");
    }
    let mut key = Vec::with_capacity(64);
    key.extend_from_slice(uuid::Uuid::new_v4().as_bytes());
    key.extend_from_slice(&std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos().to_le_bytes())
        .unwrap_or([0u8; 16]));
    key.extend_from_slice(&std::process::id().to_le_bytes());
    while key.len() < 64 {
        key.extend_from_slice(uuid::Uuid::new_v4().as_bytes());
    }
    key.truncate(64);
    tracing::warn!("未配置 JWT_SECRET，使用进程级随机密钥（服务重启后 admin token 将失效）");
    key
}

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub server: ServerConfig,
    pub database: DatabaseConfig,
    pub recall: RecallConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub port: u16,
    pub host: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DatabaseConfig {
    pub url: String,
    pub max_connections: u32,
    pub min_connections: u32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RecallConfig {
    pub urls: Vec<String>,
    pub timeout_secs: u64,
}

impl Config {
    pub fn from_env() -> Self {
        let port = std::env::var("PORT")
            .unwrap_or_else(|_| "8080".to_string())
            .parse()
            .expect("PORT must be a valid u16");

        let host = std::env::var("HOST")
            .unwrap_or_else(|_| "0.0.0.0".to_string());

        let database_url = std::env::var("DATABASE_URL")
            .or_else(|_| std::env::var("POSTGRES_URL"))
            .unwrap_or_else(|_| "sqlite://proxy.db".to_string());

        let recall_urls_str = std::env::var("PYTHON_RECALL_URLS")
            .unwrap_or_else(|_| "http://localhost:8001".to_string());
        
        let recall_urls: Vec<String> = recall_urls_str
            .split(',')
            .map(|s| s.trim().to_string())
            .collect();

        Self {
            server: ServerConfig { port, host },
            database: DatabaseConfig {
                url: database_url,
                max_connections: 50,
                min_connections: 10,
            },
            recall: RecallConfig {
                urls: recall_urls,
                timeout_secs: 30,
            },
        }
    }
}
