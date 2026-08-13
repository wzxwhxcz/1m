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
        let mut indices = cutoff_indices(&scores, None, &scores, k, 0.28);
        indices.sort_unstable();
        indices.into_iter().map(|i| messages[i].clone()).collect()
    }

    /// 长文档：文首/文尾分段 embed，取 max 余弦；再做伪相关反馈拉开簇间距。
    async fn dense_scores(&self, messages: &[Message], query: &str) -> Result<Vec<f32>> {
        const PASSAGE_CHARS: usize = 512;
        let mut texts = Vec::new();
        let mut owner = Vec::new();
        for (i, m) in messages.iter().enumerate() {
            for p in split_passages(&m.content, PASSAGE_CHARS) {
                texts.push(p);
                owner.push(i);
            }
        }
        let embs = self.embedding.embed_batch(texts).await?;
        if embs.len() != owner.len() {
            return Err(RecallError::Embedding(format!(
                "passage embedding count mismatch: {} vs {}",
                embs.len(),
                owner.len()
            )));
        }
        let q = self.embedding.embed(query).await?;
        let n = messages.len();
        let (sims1, best_emb) = maxsim_docs(n, &owner, &embs, &q);
        let q2 = prf_expand(&q, &best_emb, &sims1, 8, 0.6);
        let (sims2, _) = maxsim_docs(n, &owner, &embs, &q2);
        Ok(sims2)
    }

    /// 混合检索：BM25(稀疏) + 稠密向量，RRF 融合（2026 RAG 生产标准）。
    /// embedding API 不可用时自动退化为纯 BM25，保证可用性。
    async fn hybrid_recall(&self, messages: &[Message], query: &str, k: usize) -> Result<Vec<Message>> {
        // 1) 稀疏通道：BM25（纯词法，永不失败）
        let sparse_scores = bm25_scores(messages, query);
        let sparse_rank = rank_indices(&sparse_scores);

        // 2) 稠密通道：分段 maxsim + 伪相关反馈（失败则跳过，退化纯 BM25）
        let dense_sims: Option<Vec<f32>> = match self.dense_scores(messages, query).await {
            Ok(s) => Some(s),
            Err(e) => {
                tracing::warn!(error = %e, "dense channel failed, BM25-only");
                None
            }
        };
        let dense_rank = dense_sims.as_ref().map(|s| rank_indices(s));

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

        let floor: f32 = std::env::var("RECALL_COSINE_FLOOR")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(0.28);
        let mut indices = cutoff_indices(&rrf_scores, dense_sims.as_deref(), &sparse_scores, k, floor);
        if let Some(sims) = dense_sims.as_ref() {
            let peak = sims.iter().copied().fold(0.0f32, f32::max);
            let effective = effective_floor(peak, floor);
            tracing::info!(
                kept = indices.len(),
                max_k = k,
                peak_cosine = peak,
                cosine_floor = effective,
                knee = knee_k(sims, k, effective),
                "Adaptive recall cutoff (k is a cap, not a quota)"
            );
        }
        indices.sort_unstable();
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
        cosine_similarity(a, b)
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

/// k 是上限不是配额。
/// 稠密通道：安全地板 + 分数悬崖（knee）截断，避免用跨书文档填满预算。
/// 无稠密：BM25 为 0 的文档不填充。
fn cutoff_indices(
    rank_scores: &[f32],
    dense_sims: Option<&[f32]>,
    sparse_scores: &[f32],
    k: usize,
    abs_floor: f32,
) -> Vec<usize> {
    let n = rank_scores.len();
    if n == 0 || k == 0 {
        return Vec::new();
    }

    if let Some(sims) = dense_sims {
        let peak = sims.iter().copied().fold(0.0f32, f32::max);
        if peak <= 0.0 {
            return Vec::new();
        }
        let floor = effective_floor(peak, abs_floor);
        let keep_n = knee_k(sims, k, floor);
        let bm25_max = sparse_scores.iter().copied().fold(0.0f32, f32::max);
        let mut dense_idx = rank_indices(sims);
        dense_idx.retain(|&i| sims.get(i).copied().unwrap_or(0.0) >= floor);
        dense_idx.truncate(keep_n);
        if bm25_max > 0.0 {
            let mut set: HashSet<usize> = dense_idx.into_iter().collect();
            for i in rank_indices(sparse_scores) {
                if sparse_scores[i] > 0.0 {
                    set.insert(i);
                }
            }
            let mut all: Vec<usize> = set.into_iter().collect();
            all.sort_by(|&a, &b| {
                rank_scores[b]
                    .partial_cmp(&rank_scores[a])
                    .unwrap_or(std::cmp::Ordering::Equal)
            });
            all.truncate(k);
            all
        } else {
            dense_idx
        }
    } else {
        let mut idx = rank_indices(rank_scores);
        idx.retain(|&i| sparse_scores.get(i).copied().unwrap_or(0.0) > 0.0);
        idx.truncate(k);
        idx
    }
}

fn effective_floor(peak: f32, abs_floor: f32) -> f32 {
    abs_floor.min(peak * 0.85)
}

/// 在高于 floor 的分数里找最大悬崖；没有明显悬崖则全留。
fn knee_k(sims: &[f32], max_k: usize, floor: f32) -> usize {
    let mut vals: Vec<f32> = sims.iter().copied().filter(|&s| s >= floor).collect();
    if vals.is_empty() {
        return 0;
    }
    vals.sort_by(|a, b| b.partial_cmp(a).unwrap());
    let cap = vals.len().min(max_k);
    if cap <= 3 {
        return cap;
    }
    let min_keep = 5.min(cap);
    let mut best_i = cap;
    let mut best_gap = 0.0f32;
    for i in min_keep..cap {
        let gap = vals[i - 1] - vals[i];
        if gap > best_gap {
            best_gap = gap;
            best_i = i;
        }
    }
    let span_gap = (vals[0] - vals[cap - 1]) / (cap as f32 - 1.0).max(1.0);
    if best_gap < (span_gap * 1.8).max(0.015) {
        two_means_k(&vals, cap)
    } else {
        best_i
    }
}

/// 1D 二均值：把高于 floor 的分数分成高/低两簇，只留更靠近高簇中心的前缀。
fn two_means_k(vals_desc: &[f32], cap: usize) -> usize {
    if cap == 0 {
        return 0;
    }
    let vals = &vals_desc[..cap];
    if cap < 8 {
        return cap;
    }
    let mut c_high = vals[0];
    let mut c_low = vals[cap - 1];
    for _ in 0..8 {
        let mut sum_h = 0.0;
        let mut n_h = 0.0;
        let mut sum_l = 0.0;
        let mut n_l = 0.0;
        for &v in vals {
            if (v - c_high).abs() <= (v - c_low).abs() {
                sum_h += v;
                n_h += 1.0;
            } else {
                sum_l += v;
                n_l += 1.0;
            }
        }
        if n_h > 0.0 {
            c_high = sum_h / n_h;
        }
        if n_l > 0.0 {
            c_low = sum_l / n_l;
        }
    }
    if (c_high - c_low).abs() < 0.02 {
        return cap;
    }
    let mut keep = 0usize;
    for &v in vals {
        if (v - c_high).abs() <= (v - c_low).abs() {
            keep += 1;
        } else {
            break;
        }
    }
    keep.max(1).min(cap)
}

fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        dot / (norm_a * norm_b)
    }
}

fn l2_normalize(v: &mut [f32]) {
    let n = v.iter().map(|x| x * x).sum::<f32>().sqrt().max(1e-9);
    for x in v {
        *x /= n;
    }
}

/// 文首 + 文尾各一段；短文本不切。
fn split_passages(text: &str, passage_chars: usize) -> Vec<String> {
    let total = text.chars().count();
    if total <= passage_chars {
        return vec![text.to_string()];
    }
    let head: String = text.chars().take(passage_chars).collect();
    let tail: String = text.chars().skip(total - passage_chars).collect();
    if head == tail {
        vec![head]
    } else {
        vec![head, tail]
    }
}

fn maxsim_docs(
    n: usize,
    owner: &[usize],
    embs: &[Vec<f32>],
    query: &[f32],
) -> (Vec<f32>, Vec<Vec<f32>>) {
    let mut sims = vec![f32::NEG_INFINITY; n];
    let mut best = vec![Vec::new(); n];
    for (j, emb) in embs.iter().enumerate() {
        let d = owner[j];
        if d >= n {
            continue;
        }
        let s = cosine_similarity(query, emb);
        if s > sims[d] {
            sims[d] = s;
            best[d] = emb.clone();
        }
    }
    for s in &mut sims {
        if *s == f32::NEG_INFINITY {
            *s = 0.0;
        }
    }
    (sims, best)
}

/// 伪相关反馈：q' = normalize(q + α · mean(top-m 最佳段落向量))
fn prf_expand(query: &[f32], best_emb: &[Vec<f32>], sims: &[f32], m: usize, alpha: f32) -> Vec<f32> {
    let mut idx = rank_indices(sims);
    idx.retain(|&i| i < best_emb.len() && !best_emb[i].is_empty());
    let m = m.min(idx.len()).max(1);
    let dim = query.len();
    let mut acc = vec![0.0f32; dim];
    let mut used = 0usize;
    for &i in idx.iter().take(m) {
        if best_emb[i].len() != dim {
            continue;
        }
        for (d, &v) in best_emb[i].iter().enumerate() {
            acc[d] += v;
        }
        used += 1;
    }
    if used == 0 {
        return query.to_vec();
    }
    let used_f = used as f32;
    let mut out = vec![0.0f32; dim];
    for d in 0..dim {
        out[d] = query[d] + alpha * (acc[d] / used_f);
    }
    l2_normalize(&mut out);
    out
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

    #[test]
    fn cutoff_drops_low_cosine_padding() {
        let rrf = vec![0.9, 0.8, 0.7, 0.6];
        let dense = vec![0.46, 0.44, 0.31, 0.29]; // 两本相关，两本跨书
        let sparse = vec![0.0, 0.0, 0.0, 0.0];
        let kept = cutoff_indices(&rrf, Some(&dense), &sparse, 10, 0.36);
        let mut kept = kept;
        kept.sort();
        assert_eq!(kept, vec![0, 1], "{kept:?}");
    }

    #[test]
    fn cutoff_bm25_skips_zero_fill() {
        let sparse = vec![2.1, 0.0, 1.3, 0.0];
        let kept = cutoff_indices(&sparse, None, &sparse, 10, 0.36);
        let mut kept = kept;
        kept.sort();
        assert_eq!(kept, vec![0, 2]);
    }

    #[test]
    fn cutoff_lowers_floor_when_peak_is_weak() {
        let rrf = vec![0.5, 0.4];
        let dense = vec![0.32, 0.30];
        let sparse = vec![0.0, 0.0];
        // peak*0.85=0.272 < abs 0.36 → floor=0.272，两条都过
        let kept = cutoff_indices(&rrf, Some(&dense), &sparse, 10, 0.36);
        assert_eq!(kept.len(), 2);
    }

    #[test]
    fn knee_cuts_at_cluster_cliff() {
        let mut sims = vec![0.50, 0.48, 0.47, 0.46, 0.45, 0.44, 0.43, 0.42];
        sims.extend_from_slice(&[0.28, 0.27, 0.26, 0.25, 0.24]);
        let k = knee_k(&sims, 20, 0.20);
        assert!(k >= 8 && k <= 9, "knee={k} sims_above_cliff should be 8");
    }

    #[test]
    fn two_means_splits_bimodal_scores() {
        let mut vals: Vec<f32> = (0..40).map(|i| 0.70 - i as f32 * 0.003).collect();
        vals.extend((0..40).map(|i| 0.38 - i as f32 * 0.002));
        let k = two_means_k(&vals, 80);
        assert!(k >= 35 && k <= 45, "two-means k={k}");
    }

    #[test]
    fn split_passages_head_and_tail() {
        let s: String = (0..200).map(|i| char::from_u32(0x4e00 + i).unwrap()).collect();
        let ps = split_passages(&s, 40);
        assert_eq!(ps.len(), 2);
        assert_eq!(ps[0].chars().count(), 40);
        assert_eq!(ps[1].chars().count(), 40);
        assert_eq!(ps[0].chars().next(), s.chars().next());
        assert_eq!(ps[1].chars().last(), s.chars().last());
    }

    #[test]
    fn prf_moves_query_toward_top_docs() {
        let q = vec![1.0, 0.0];
        let best = vec![vec![1.0, 0.0], vec![0.9, 0.1], vec![0.0, 1.0]];
        let sims = vec![0.9, 0.8, 0.1];
        let q2 = prf_expand(&q, &best, &sims, 2, 1.0);
        // top-2 are on the x-axis cluster; y component should stay small
        assert!(q2[0] > q2[1], "{q2:?}");
    }
}

