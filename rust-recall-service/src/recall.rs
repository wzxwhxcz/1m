use ndarray::{Array1, Array2};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use crate::embedding::EmbeddingService;
use crate::error::{RecallError, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallRequest {
    pub messages: Vec<Message>,
    pub query: String,
    pub k: usize,
    #[serde(default = "default_algorithm")]
    pub algorithm: RecallAlgorithm,
}

fn default_algorithm() -> RecallAlgorithm {
    RecallAlgorithm::Car
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RecallAlgorithm {
    Dense,
    #[serde(rename = "hybrid_dat")]
    HybridDat,
    Car,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecallResponse {
    pub recalled_messages: Vec<Message>,
    pub original_count: usize,
    pub recalled_count: usize,
    pub latency_ms: u64,
}

pub struct RecallService {
    embedding: Arc<dyn EmbeddingService>,
}

impl RecallService {
    pub fn new(embedding: Arc<dyn EmbeddingService>) -> Self {
        Self { embedding }
    }

    pub async fn recall(&self, request: RecallRequest) -> Result<RecallResponse> {
        let start = std::time::Instant::now();
        
        let original_count = request.messages.len();
        
        // 如果消息数量小于等于 k，直接返回
        if original_count <= request.k {
            return Ok(RecallResponse {
                recalled_messages: request.messages,
                original_count,
                recalled_count: original_count,
                latency_ms: start.elapsed().as_millis() as u64,
            });
        }

        let recalled = match request.algorithm {
            RecallAlgorithm::Dense => {
                self.dense_recall(&request.messages, &request.query, request.k).await?
            }
            RecallAlgorithm::HybridDat => {
                self.hybrid_dat_recall(&request.messages, &request.query, request.k).await?
            }
            RecallAlgorithm::Car => {
                self.car_recall(&request.messages, &request.query, request.k).await?
            }
        };

        let latency_ms = start.elapsed().as_millis() as u64;

        Ok(RecallResponse {
            recalled_count: recalled.len(),
            recalled_messages: recalled,
            original_count,
            latency_ms,
        })
    }

    /// Dense 召回：基于语义相似度
    async fn dense_recall(&self, messages: &[Message], query: &str, k: usize) -> Result<Vec<Message>> {
        // 生成所有消息的 embeddings
        let texts: Vec<String> = messages.iter().map(|m| m.content.clone()).collect();
        let message_embeddings = self.embedding.embed_batch(texts).await?;
        
        // 生成查询 embedding
        let query_embedding = self.embedding.embed(query).await?;
        
        // 计算相似度
        let similarities = self.compute_similarities(&message_embeddings, &query_embedding);
        
        // 选择 top-k
        let indices = self.top_k_indices(&similarities, k);
        
        Ok(indices.into_iter().map(|i| messages[i].clone()).collect())
    }

    /// Hybrid DAT 召回：时间衰减 + 语义相似度
    async fn hybrid_dat_recall(&self, messages: &[Message], query: &str, k: usize) -> Result<Vec<Message>> {
        let texts: Vec<String> = messages.iter().map(|m| m.content.clone()).collect();
        let message_embeddings = self.embedding.embed_batch(texts).await?;
        let query_embedding = self.embedding.embed(query).await?;
        
        let similarities = self.compute_similarities(&message_embeddings, &query_embedding);
        
        // 时间衰减因子：越新的消息权重越高
        let time_weights: Vec<f32> = (0..messages.len())
            .map(|i| {
                let position = i as f32 / messages.len() as f32;
                0.5 + 0.5 * position // 从 0.5 衰减到 1.0
            })
            .collect();
        
        // 混合得分：60% 语义 + 40% 时间
        let hybrid_scores: Vec<f32> = similarities.iter()
            .zip(time_weights.iter())
            .map(|(sim, time)| 0.6 * sim + 0.4 * time)
            .collect();
        
        let indices = self.top_k_indices(&hybrid_scores, k);
        Ok(indices.into_iter().map(|i| messages[i].clone()).collect())
    }

    /// CAR 召回：聚类感知召回
    async fn car_recall(&self, messages: &[Message], query: &str, k: usize) -> Result<Vec<Message>> {
        let texts: Vec<String> = messages.iter().map(|m| m.content.clone()).collect();
        let message_embeddings = self.embedding.embed_batch(texts).await?;
        let query_embedding = self.embedding.embed(query).await?;
        
        let similarities = self.compute_similarities(&message_embeddings, &query_embedding);
        
        // 简化版 CAR：使用固定数量的聚类
        let n_clusters = (messages.len() / 10).max(3).min(10);
        let clusters = self.simple_kmeans(&message_embeddings, n_clusters);
        
        // 每个聚类选择最相似的消息
        let mut selected = Vec::new();
        let messages_per_cluster = (k / n_clusters).max(1);
        
        for cluster_id in 0..n_clusters {
            let cluster_indices: Vec<usize> = clusters.iter()
                .enumerate()
                .filter(|(_, &c)| c == cluster_id)
                .map(|(i, _)| i)
                .collect();
            
            if cluster_indices.is_empty() {
                continue;
            }
            
            // 从该聚类中选择相似度最高的消息
            let mut cluster_scores: Vec<(usize, f32)> = cluster_indices.iter()
                .map(|&i| (i, similarities[i]))
                .collect();
            
            cluster_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            
            for &(idx, _) in cluster_scores.iter().take(messages_per_cluster) {
                selected.push(idx);
            }
        }
        
        // 如果还没达到 k 个，补充剩余的高分消息
        if selected.len() < k {
            let remaining = k - selected.len();
            let mut all_scores: Vec<(usize, f32)> = similarities.iter()
                .enumerate()
                .map(|(i, &s)| (i, s))
                .filter(|(i, _)| !selected.contains(i))
                .collect();
            
            all_scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
            
            for &(idx, _) in all_scores.iter().take(remaining) {
                selected.push(idx);
            }
        }
        
        // 按原始顺序排序
        selected.sort_unstable();
        
        Ok(selected.into_iter().map(|i| messages[i].clone()).collect())
    }

    /// 计算余弦相似度
    fn compute_similarities(&self, embeddings: &[Vec<f32>], query: &[f32]) -> Vec<f32> {
        embeddings.iter()
            .map(|emb| self.cosine_similarity(emb, query))
            .collect()
    }

    fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
        
        if norm_a == 0.0 || norm_b == 0.0 {
            0.0
        } else {
            dot / (norm_a * norm_b)
        }
    }

    /// 获取 top-k 索引
    fn top_k_indices(&self, scores: &[f32], k: usize) -> Vec<usize> {
        let mut indexed: Vec<(usize, f32)> = scores.iter()
            .enumerate()
            .map(|(i, &s)| (i, s))
            .collect();
        
        indexed.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
        
        indexed.into_iter()
            .take(k)
            .map(|(i, _)| i)
            .collect()
    }

    /// 简化版 K-means 聚类
    fn simple_kmeans(&self, embeddings: &[Vec<f32>], k: usize) -> Vec<usize> {
        let n = embeddings.len();
        let dim = embeddings[0].len();
        
        if n <= k {
            return (0..n).collect();
        }
        
        // 随机初始化聚类中心
        let mut centroids: Vec<Vec<f32>> = Vec::new();
        let step = n / k;
        for i in 0..k {
            let idx = (i * step).min(n - 1);
            centroids.push(embeddings[idx].clone());
        }
        
        let mut assignments = vec![0; n];
        
        // 迭代 5 次（简化版）
        for _ in 0..5 {
            // 分配每个点到最近的中心
            for (i, emb) in embeddings.iter().enumerate() {
                let mut min_dist = f32::MAX;
                let mut best_cluster = 0;
                
                for (j, centroid) in centroids.iter().enumerate() {
                    let dist = self.euclidean_distance(emb, centroid);
                    if dist < min_dist {
                        min_dist = dist;
                        best_cluster = j;
                    }
                }
                
                assignments[i] = best_cluster;
            }
            
            // 更新聚类中心
            for j in 0..k {
                let cluster_points: Vec<&Vec<f32>> = embeddings.iter()
                    .enumerate()
                    .filter(|(i, _)| assignments[*i] == j)
                    .map(|(_, e)| e)
                    .collect();
                
                if !cluster_points.is_empty() {
                    let mut new_centroid = vec![0.0; dim];
                    for point in &cluster_points {
                        for (d, &val) in point.iter().enumerate() {
                            new_centroid[d] += val;
                        }
                    }
                    
                    let count = cluster_points.len() as f32;
                    for val in &mut new_centroid {
                        *val /= count;
                    }
                    
                    centroids[j] = new_centroid;
                }
            }
        }
        
        assignments
    }

    fn euclidean_distance(&self, a: &[f32], b: &[f32]) -> f32 {
        a.iter()
            .zip(b.iter())
            .map(|(x, y)| (x - y).powi(2))
            .sum::<f32>()
            .sqrt()
    }
}
