use reqwest::{Client, header::HeaderMap};
use std::time::Duration;
use bytes::Bytes;
use futures::stream::Stream;
use crate::{models::ChatRequest, error::{ProxyError, Result}};

#[derive(Clone)]
pub struct ProxyService {
    client: Client,
}

impl ProxyService {
    pub fn new(timeout_secs: u64) -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .unwrap();

        Self { client }
    }

    pub async fn proxy_request(
        &self,
        upstream_url: &str,
        api_key: &str,
        request_body: ChatRequest,
        extra_headers: Option<HeaderMap>,
    ) -> Result<impl Stream<Item = std::result::Result<Bytes, reqwest::Error>>> {
        let start = std::time::Instant::now();

        let mut request_builder = self.client
            .post(upstream_url)
            .header("Authorization", format!("Bearer {}", api_key))
            .header("Content-Type", "application/json");

        // 透传额外的 headers
        if let Some(headers) = extra_headers {
            for (key, value) in headers.iter() {
                if key != "authorization" && key != "content-type" && key != "host" {
                    request_builder = request_builder.header(key, value);
                }
            }
        }

        let response = request_builder
            .json(&request_body)
            .send()
            .await
            .map_err(|e| ProxyError::Upstream(e.to_string()))?;

        let status = response.status();
        if !status.is_success() {
            let error_body = response.text().await.unwrap_or_default();
            return Err(ProxyError::Upstream(format!(
                "Upstream API returned status {}: {}",
                status, error_body
            )));
        }

        crate::metrics::UPSTREAM_DURATION.observe(start.elapsed().as_secs_f64());

        Ok(response.bytes_stream())
    }

    pub async fn proxy_non_stream(
        &self,
        upstream_url: &str,
        api_key: &str,
        request_body: ChatRequest,
        extra_headers: Option<HeaderMap>,
    ) -> Result<String> {
        let start = std::time::Instant::now();

        let mut request_builder = self.client
            .post(upstream_url)
            .header("Authorization", format!("Bearer {}", api_key))
            .header("Content-Type", "application/json");

        // 透传额外的 headers
        if let Some(headers) = extra_headers {
            for (key, value) in headers.iter() {
                if key != "authorization" && key != "content-type" && key != "host" {
                    request_builder = request_builder.header(key, value);
                }
            }
        }

        let response = request_builder
            .json(&request_body)
            .send()
            .await
            .map_err(|e| ProxyError::Upstream(e.to_string()))?;

        let status = response.status();
        if !status.is_success() {
            let error_body = response.text().await.unwrap_or_default();
            return Err(ProxyError::Upstream(format!(
                "Upstream API returned status {}: {}",
                status, error_body
            )));
        }

        let body = response.text().await
            .map_err(|e| ProxyError::Upstream(e.to_string()))?;

        crate::metrics::UPSTREAM_DURATION.observe(start.elapsed().as_secs_f64());

        Ok(body)
    }
}
