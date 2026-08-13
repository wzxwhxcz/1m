use ndarray::{Array1, Array2};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
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
    RecallAlgorithm::Hybrid
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum RecallAlgorithm {
    Dense,
    #[serde(rename = "hybrid_dat")]
    HybridDat,
    /// 纯 BM25 稀疏检索（无 embedding 依赖，标识符/术语/专名场景强）
    Bm25,
    /// 混合检索：BM25 + 稠密向量，RRF 融合（2026 RAG 生产标准）
    Hybrid,
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
            RecallAlgorithm::Bm25 => {
                self.bm25_recall(&request.messages, &request.query, request.k)
            }
            RecallAlgorithm::Hybrid => {
                self.hybrid_recall(&request.messages, &request.query, request.k).await?
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
        
        Ok(self.take_in_original_order(messages, &similarities, k))
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
        
        Ok(self.take_in_original_order(messages, &hybrid_scores, k))
    }

    /// BM25 召回：纯词法稀疏检索（无 embedding 依赖）
    /// 对标识符、专名、术语等精确匹配场景强于稠密检索（2026 基准：BM25 在金融文档上全面胜出稠密）。
    fn bm25_recall(&self, messages: &[Message], query: &str, k: usize) -> Vec<Message> {
        let scores = bm25_scores(messages, query);
        self.take_in_original_order(messages, &scores, k)
    }

    /// 混合检索：BM25(稀疏) + 稠密向量，RRF 融合（2026 RAG 生产标准）。
    /// embedding API 不可用时自动退化为纯 BM25，保证可用性。
    async fn hybrid_recall(&self, messages: &[Message], query: &str, k: usize) -> Result<Vec<Message>> {
        // 1) 稀疏通道：BM25（纯词法，永不失败）
        let sparse_scores = bm25_scores(messages, query);
        let sparse_rank = rank_indices(&sparse_scores);

        // 2) 稠密通道：语义相似度（失败则跳过，退化纯 BM25）
        let dense_rank: Option<Vec<usize>> = {
            let texts: Vec<String> = messages.iter().map(|m| m.content.clone()).collect();
            match self.embedding.embed_batch(texts).await {
                Ok(embs) => match self.embedding.embed(query).await {
                    Ok(q_vec) => {
                        let similarities = self.compute_similarities(&embs, &q_vec);
                        Some(rank_indices(&similarities))
                    }
                    Err(_) => None,
                },
                Err(_) => None,
            }
        };

        // 3) RRF 融合：score(i) = Σ 1/(60 + rank(i))
        // 稀疏通道退化（query 词在语料中完全缺失，所有 BM25 得分为 0）时跳过，
        // 避免全 0 平分按任意顺序稀释稠密语义排序。
        let n = messages.len();
        let mut rrf_scores = vec![0.0f32; n];
        let bm25_max = sparse_scores.iter().copied().fold(0.0f32, f32::max);
        if bm25_max > 0.0 {
            for (rank, idx) in sparse_rank.iter().enumerate() {
                rrf_scores[*idx] += 1.0 / (60.0 + rank as f32 + 1.0);
            }
        }
        if let Some(dense_rank) = &dense_rank {
            for (rank, idx) in dense_rank.iter().enumerate() {
                rrf_scores[*idx] += 1.0 / (60.0 + rank as f32 + 1.0);
            }
        }

        Ok(self.take_in_original_order(messages, &rrf_scores, k))
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

    /// 按分数取 top-k，再恢复原始顺序（对话历史连贯性 > 分数序）
    fn take_in_original_order(&self, messages: &[Message], scores: &[f32], k: usize) -> Vec<Message> {
        let mut indices = self.top_k_indices(scores, k);
        indices.sort_unstable();
        indices.into_iter().map(|i| messages[i].clone()).collect()
    }

    /// 获取 top-k 索引（分数降序）
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

// ==================== BM25 稀疏检索（CJK 兼容分词） ====================

/// 分词：ASCII 词按整词（小写），CJK 连续段按字符 bigram。
/// bigram 对中文检索有效（无需分词器），可捕获「三体」「罗辑」等专名片段。
fn tokenize(text: &str) -> Vec<String> {
    let mut tokens: Vec<String> = Vec::new();
    let mut ascii_buf = String::new();
    let mut cjk_buf: Vec<char> = Vec::new();

    for c in text.chars() {
        if c.is_ascii_alphanumeric() {
            if !cjk_buf.is_empty() {
                push_cjk_bigrams(&cjk_buf, &mut tokens);
                cjk_buf.clear();
            }
            ascii_buf.push(c.to_ascii_lowercase());
        } else if c.is_alphanumeric() {
            // CJK 及其它 Unicode 字母
            if !ascii_buf.is_empty() {
                tokens.push(std::mem::take(&mut ascii_buf));
            }
            cjk_buf.push(c);
        } else if c.is_whitespace() {
            // 空白不打断 CJK run（修复 "redis 连接池" 空格导致 bigram 断裂）
            if !ascii_buf.is_empty() {
                tokens.push(std::mem::take(&mut ascii_buf));
            }
        } else {
            if !ascii_buf.is_empty() {
                tokens.push(std::mem::take(&mut ascii_buf));
            }
            if !cjk_buf.is_empty() {
                push_cjk_bigrams(&cjk_buf, &mut tokens);
                cjk_buf.clear();
            }
        }
    }
    if !ascii_buf.is_empty() {
        tokens.push(ascii_buf);
    }
    if !cjk_buf.is_empty() {
        push_cjk_bigrams(&cjk_buf, &mut tokens);
    }
    tokens
}

fn push_cjk_bigrams(chars: &[char], out: &mut Vec<String>) {
    if chars.len() == 1 {
        out.push(chars[0].to_string());
        return;
    }
    for w in chars.windows(2) {
        out.push(format!("{}{}", w[0], w[1]));
    }
}

/// 标准 BM25：k1=1.5, b=0.75，IDF 用平滑 ln 版本
fn bm25_scores(messages: &[Message], query: &str) -> Vec<f32> {
    let n = messages.len();
    if n == 0 {
        return Vec::new();
    }

    // 文档词频
    let docs: Vec<Vec<String>> = messages
        .iter()
        .map(|m| tokenize(&m.content))
        .collect();
    let avgdl: f32 = docs.iter().map(|d| d.len() as f32).sum::<f32>() / n as f32;

    // 文档频率 df(t)：出现该词的文档数
    let mut df: HashMap<String, usize> = HashMap::new();
    for doc in &docs {
        let mut seen = HashSet::new();
        for t in doc {
            if seen.insert(t.clone()) {
                *df.entry(t.clone()).or_insert(0) += 1;
            }
        }
    }

    // 每条文档的 term 计数
    let mut tf: Vec<HashMap<String, usize>> = Vec::with_capacity(n);
    for doc in &docs {
        let mut m = HashMap::new();
        for t in doc {
            *m.entry(t.clone()).or_insert(0) += 1;
        }
        tf.push(m);
    }

    let query_tokens = tokenize(query);
    let k1 = 1.5f32;
    let b = 0.75f32;

    let mut scores = vec![0.0f32; n];
    for q in &query_tokens {
        let df_q = *df.get(q).unwrap_or(&0) as f32;
        let idf = ((n as f32 - df_q + 0.5) / (df_q + 0.5) + 1.0).ln();
        if idf <= 0.0 {
            continue;
        }
        for (i, tfi) in tf.iter().enumerate() {
            let f = *tfi.get(q).unwrap_or(&0) as f32;
            if f > 0.0 {
                let dl = docs[i].len() as f32;
                let denom = f + k1 * (1.0 - b + b * dl / avgdl.max(1.0));
                scores[i] += idf * (f * (k1 + 1.0)) / denom;
            }
        }
    }
    scores
}

/// 按分数降序返回排名（rank 从 0 开始，分数相同按原顺序，保证稳定性）
fn rank_indices(scores: &[f32]) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..scores.len()).collect();
    idx.sort_by(|&a, &b| {
        scores[b].partial_cmp(&scores[a]).unwrap_or(std::cmp::Ordering::Equal)
    });
    idx
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenize_glues_cjk_across_spaces() {
        let q = tokenize("redis连接池线程安全");
        let d = tokenize("redis 连接 池的线程 安全问题");
        let set: HashSet<&String> = d.iter().collect();
        let shared = q.iter().filter(|t| set.contains(t)).count();
        assert!(shared * 100 / q.len() >= 80, "shared={}/{}", shared, q.len());
    }

    #[test]
    fn bm25_zero_when_query_absent() {
        let msgs = vec![
            Message { role: "user".into(), content: "罗辑在黑暗森林里等待".into() },
            Message { role: "user".into(), content: "孙悟空大闹天宫".into() },
        ];
        let scores = bm25_scores(&msgs, "三体");
        assert!(scores.iter().all(|&s| s == 0.0), "{:?}", scores);
    }
}

