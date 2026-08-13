use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;
use reqwest::Client;
use crate::{
    models::{RecallRequest, RecallResponse, Message},
    error::{ProxyError, Result},
};

#[derive(Clone)]
pub struct RecallService {
    client: Client,
    urls: Vec<String>,
    current_index: Arc<AtomicUsize>,
    timeout_secs: Arc<AtomicU64>,
}

impl RecallService {
    pub fn new(urls: Vec<String>, timeout_secs: u64) -> Self {
        let client = Client::builder()
            .connect_timeout(Duration::from_secs(5))
            // 与 ProxyService 一致：直连 recall 服务，不走系统代理
            .no_proxy()
            .build()
            .unwrap();

        Self {
            client,
            urls,
            current_index: Arc::new(AtomicUsize::new(0)),
            timeout_secs: Arc::new(AtomicU64::new(timeout_secs.max(1))),
        }
    }

    pub fn set_timeout(&self, timeout_secs: u64) {
        self.timeout_secs.store(timeout_secs.max(1), Ordering::Relaxed);
    }

    fn timeout(&self) -> Duration {
        Duration::from_secs(self.timeout_secs.load(Ordering::Relaxed))
    }

    fn get_next_url(&self) -> &str {
        let index = self.current_index.fetch_add(1, Ordering::Relaxed);
        &self.urls[index % self.urls.len()]
    }

    pub async fn recall(
        &self,
        messages: Vec<Message>,
        query: String,
        k: usize,
        algorithm: &str,
    ) -> Result<RecallResponse> {
        let request = RecallRequest {
            messages,
            query,
            k,
            algorithm: algorithm.to_string(),
        };

        let max_retries = 3;
        let mut last_error = None;

        for attempt in 0..max_retries {
            let url = format!("{}/api/v1/recall", self.get_next_url());
            let start = std::time::Instant::now();

            match self.client
                .post(&url)
                .timeout(self.timeout())
                .json(&request)
                .send()
                .await
            {
                Ok(response) => {
                    if response.status().is_success() {
                        match response.json::<RecallResponse>().await {
                            Ok(mut recall_response) => {
                                recall_response.latency_ms = start.elapsed().as_millis() as u64;
                                crate::metrics::RECALL_DURATION.observe(start.elapsed().as_secs_f64());
                                return Ok(recall_response);
                            }
                            Err(e) => {
                                last_error = Some(format!("Failed to parse response: {}", e));
                            }
                        }
                    } else {
                        last_error = Some(format!("Recall service returned status: {}", response.status()));
                    }
                }
                Err(e) => {
                    last_error = Some(format!("Request failed: {}", e));
                    // 超时说明对端还在算（稠密 embed 可达 2 分钟），重试只会叠加请求、打爆 API
                    if e.is_timeout() {
                        break;
                    }
                }
            }

            if attempt < max_retries - 1 {
                tokio::time::sleep(Duration::from_millis(100 * (attempt as u64 + 1))).await;
            }
        }

        Err(ProxyError::Upstream(
            last_error.unwrap_or_else(|| "All recall attempts failed".to_string())
        ))
    }

    pub async fn health_check(&self) -> bool {
        for url in &self.urls {
            let health_url = format!("{}/health", url);
            if let Ok(response) = self.client
                .get(&health_url)
                .timeout(Duration::from_secs(5))
                .send()
                .await
            {
                if response.status().is_success() {
                    return true;
                }
            }
        }
        false
    }

    pub async fn recall_messages(
        &self,
        messages: &[Message],
        query: String,
        k: usize,
        algorithm: &str,
        _threshold: usize,
    ) -> Result<Vec<Message>> {
        let response = self.recall(messages.to_vec(), query, k, algorithm).await?;
        Ok(response.recalled_messages)
    }
}
