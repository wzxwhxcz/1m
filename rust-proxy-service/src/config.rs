use serde::Deserialize;

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
