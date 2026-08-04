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
    current_index: std::sync::Arc<std::sync::atomic::AtomicUsize>,
}

impl RecallService {
    pub fn new(urls: Vec<String>, timeout_secs: u64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .unwrap();

        Self {
            client,
            urls,
            current_index: std::sync::Arc::new(std::sync::atomic::AtomicUsize::new(0)),
        }
    }

    fn get_next_url(&self) -> &str {
        let index = self.current_index.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
        &self.urls[index % self.urls.len()]
    }

    pub async fn recall(&self, messages: Vec<Message>, query: String, k: usize) -> Result<RecallResponse> {
        let request = RecallRequest {
            messages,
            query,
            k,
            algorithm: "car".to_string(),
        };

        let max_retries = 3;
        let mut last_error = None;

        for attempt in 0..max_retries {
            let url = format!("{}/api/v1/recall", self.get_next_url());
            let start = std::time::Instant::now();
            
            match self.client
                .post(&url)
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
            if let Ok(response) = self.client.get(&health_url).send().await {
                if response.status().is_success() {
                    return true;
                }
            }
        }
        false
    }

    // 兼容旧代码的 recall_messages 方法
    pub async fn recall_messages(
        &self,
        messages: &[Message],
        query: String,
        k: usize,
        _algorithm: &str,
        _threshold: usize,
    ) -> Result<Vec<Message>> {
        let response = self.recall(messages.to_vec(), query, k).await?;
        Ok(response.recalled_messages)
    }
}
