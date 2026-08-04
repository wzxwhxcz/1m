"""
SOTA 召回算法实现（2024-2025）

实现以下先进算法：
1. Hybrid Retrieval (BM25 + Dense + RRF)
2. Cross-Encoder Reranking
3. Dynamic Alpha Tuning (DAT)
4. Contextual Retrieval (简化版)
"""
import json
import time
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder
from typing import List, Dict, Tuple
import math
from collections import Counter
import random

class SOTARetriever:
    def __init__(self):
        print("加载模型...")
        # Dense retrieval model
        self.dense_model = SentenceTransformer('all-MiniLM-L6-v2')
        # Cross-encoder for reranking
        print("加载 Cross-Encoder 模型...")
        self.cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        print("模型加载完成")
        
        # BM25 参数
        self.k1 = 1.5  # term frequency saturation
        self.b = 0.75  # length normalization
        
        # Document statistics for BM25
        self.doc_lengths = []
        self.avg_doc_length = 0
        self.doc_count = 0
        self.idf_cache = {}
    
    def tokenize(self, text: str) -> List[str]:
        """简单分词"""
        return text.lower().split()
    
    def compute_idf(self, term: str, documents: List[Dict]) -> float:
        """计算IDF (Inverse Document Frequency)"""
        if term in self.idf_cache:
            return self.idf_cache[term]
        
        doc_freq = sum(1 for doc in documents if term in self.tokenize(doc["content"]))
        idf = math.log((self.doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
        self.idf_cache[term] = idf
        return idf
    
    def bm25_score(self, query: str, doc: Dict, documents: List[Dict]) -> float:
        """BM25 评分"""
        query_terms = self.tokenize(query)
        doc_terms = self.tokenize(doc["content"])
        doc_length = len(doc_terms)
        
        # Term frequency in document
        term_freqs = Counter(doc_terms)
        
        score = 0.0
        for term in query_terms:
            if term not in term_freqs:
                continue
            
            tf = term_freqs[term]
            idf = self.compute_idf(term, documents)
            
            # BM25 formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
            score += idf * (numerator / denominator)
        
        return score
    
    def prepare_bm25(self, documents: List[Dict]):
        """预计算BM25统计信息"""
        self.doc_count = len(documents)
        self.doc_lengths = [len(self.tokenize(doc["content"])) for doc in documents]
        self.avg_doc_length = sum(self.doc_lengths) / self.doc_count if self.doc_count > 0 else 0
        self.idf_cache = {}
    
    def dense_retrieval(self, query: str, documents: List[Dict], k: int = 100) -> List[Tuple[Dict, float]]:
        """Dense vector 检索"""
        query_embedding = self.dense_model.encode(query, normalize_embeddings=True)
        
        results = []
        for doc in documents:
            doc_embedding = self.dense_model.encode(doc["content"], normalize_embeddings=True)
            similarity = float(np.dot(query_embedding, doc_embedding))
            results.append((doc, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def sparse_retrieval_bm25(self, query: str, documents: List[Dict], k: int = 100) -> List[Tuple[Dict, float]]:
        """BM25 稀疏检索"""
        results = []
        for doc in documents:
            score = self.bm25_score(query, doc, documents)
            results.append((doc, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def reciprocal_rank_fusion(self, 
                                sparse_results: List[Tuple[Dict, float]], 
                                dense_results: List[Tuple[Dict, float]], 
                                k: int = 60) -> List[Tuple[Dict, float]]:
        """
        Reciprocal Rank Fusion (RRF)
        Score(doc) = sum(1 / (k + rank_i)) for all rankings
        """
        rrf_scores = {}
        
        # Sparse results
        for rank, (doc, _) in enumerate(sparse_results, 1):
            doc_id = doc["index"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
        
        # Dense results
        for rank, (doc, _) in enumerate(dense_results, 1):
            doc_id = doc["index"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
        
        # Create document lookup
        all_docs = {doc["index"]: doc for doc, _ in sparse_results + dense_results}
        
        # Sort by RRF score
        results = [(all_docs[doc_id], score) for doc_id, score in rrf_scores.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def cross_encoder_rerank(self, query: str, candidates: List[Tuple[Dict, float]], top_k: int = 50) -> List[Tuple[Dict, float]]:
        """使用 Cross-Encoder 进行精排"""
        if len(candidates) == 0:
            return []
        
        # 准备 (query, doc) pairs
        pairs = [(query, doc["content"]) for doc, _ in candidates]
        
        # Cross-encoder 打分
        ce_scores = self.cross_encoder.predict(pairs)
        
        # 组合结果
        reranked = [(candidates[i][0], float(ce_scores[i])) for i in range(len(candidates))]
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        return reranked[:top_k]
    
    def dynamic_alpha_tuning(self, query: str, sparse_top1: Tuple[Dict, float], dense_top1: Tuple[Dict, float]) -> float:
        """
        Dynamic Alpha Tuning (DAT)
        根据top-1结果的质量动态调整BM25和Dense的权重
        
        简化版：使用启发式规则
        - 如果查询短且包含专有名词 → 提高BM25权重
        - 如果查询长且语义复杂 → 提高Dense权重
        """
        query_terms = self.tokenize(query)
        query_length = len(query_terms)
        
        # 启发式规则
        if query_length <= 3:
            # 短查询，偏向BM25
            alpha = 0.7  # 70% BM25
        elif query_length <= 8:
            # 中等长度，平衡
            alpha = 0.5
        else:
            # 长查询，偏向Dense
            alpha = 0.3  # 30% BM25
        
        return alpha
    
    def hybrid_retrieval_dat(self, query: str, documents: List[Dict], k: int = 50) -> List[Tuple[Dict, float]]:
        """
        Hybrid Retrieval with Dynamic Alpha Tuning
        """
        # 1. Sparse retrieval (BM25)
        sparse_results = self.sparse_retrieval_bm25(query, documents, k=100)
        
        # 2. Dense retrieval (Vector)
        dense_results = self.dense_retrieval(query, documents, k=100)
        
        # 3. Dynamic Alpha Tuning
        if len(sparse_results) > 0 and len(dense_results) > 0:
            alpha = self.dynamic_alpha_tuning(query, sparse_results[0], dense_results[0])
        else:
            alpha = 0.5
        
        # 4. Weighted fusion
        doc_scores = {}
        
        # Normalize sparse scores
        max_sparse = max(score for _, score in sparse_results) if sparse_results else 1.0
        for doc, score in sparse_results:
            doc_id = doc["index"]
            normalized_score = score / max_sparse if max_sparse > 0 else 0
            doc_scores[doc_id] = alpha * normalized_score
        
        # Normalize dense scores
        max_dense = max(score for _, score in dense_results) if dense_results else 1.0
        for doc, score in dense_results:
            doc_id = doc["index"]
            normalized_score = score / max_dense if max_dense > 0 else 0
            doc_scores[doc_id] = doc_scores.get(doc_id, 0) + (1 - alpha) * normalized_score
        
        # Create document lookup
        all_docs = {doc["index"]: doc for doc, _ in sparse_results + dense_results}
        
        # Sort by fused score
        results = [(all_docs[doc_id], score) for doc_id, score in doc_scores.items()]
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:k]
    
    def contextual_chunks(self, documents: List[Dict]) -> List[Dict]:
        """
        Contextual Retrieval (简化版)
        为每个消息添加上下文摘要
        
        真实场景：用LLM为每个chunk生成上下文
        简化版：使用前后消息作为上下文
        """
        enriched_docs = []
        
        for i, doc in enumerate(documents):
            # 获取前后上下文
            context_parts = []
            if i > 0:
                context_parts.append(f"Previous: {documents[i-1]['content'][:50]}")
            if i < len(documents) - 1:
                context_parts.append(f"Next: {documents[i+1]['content'][:50]}")
            
            context = " | ".join(context_parts)
            
            # 创建增强后的文档
            enriched_doc = doc.copy()
            enriched_doc["content"] = f"{context} || {doc['content']}"
            enriched_doc["original_content"] = doc["content"]
            enriched_docs.append(enriched_doc)
        
        return enriched_docs

def generate_test_conversation():
    """生成测试对话（与之前相同）"""
    react_messages = [
        {"role": "user", "content": "How do I use useState in React?", "topic": "react"},
        {"role": "assistant", "content": "useState is a Hook that lets you add state to functional components:\n\n```jsx\nconst [count, setCount] = useState(0);\n```", "topic": "react"},
        {"role": "user", "content": "What's the difference between useEffect and useLayoutEffect?", "topic": "react"},
        {"role": "assistant", "content": "useEffect runs after paint, useLayoutEffect runs before paint.", "topic": "react"},
        {"role": "user", "content": "How to optimize React performance?", "topic": "react"},
        {"role": "assistant", "content": "Key optimization techniques:\n1. Use React.memo for expensive components\n2. Use useMemo for expensive calculations\n3. Use useCallback for stable function references", "topic": "react"},
    ]
    
    # 填充更多消息
    for i in range(6, 50):
        react_messages.append({
            "role": "user",
            "content": f"React question {i}: How to handle forms and controlled components?",
            "topic": "react"
        })
        react_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use controlled components with useState to handle form inputs.",
            "topic": "react"
        })
    
    python_messages = [
        {"role": "user", "content": "How to use pandas DataFrame?", "topic": "python"},
        {"role": "assistant", "content": "DataFrame is a 2D data structure:\n\n```python\nimport pandas as pd\ndf = pd.DataFrame({'A': [1,2,3]})\n```", "topic": "python"},
    ]
    
    for i in range(2, 50):
        python_messages.append({
            "role": "user",
            "content": f"Python question {i}: How to use matplotlib for data visualization?",
            "topic": "python"
        })
        python_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use plt.plot() for line plots and customize with labels.",
            "topic": "python"
        })
    
    docker_messages = [
        {"role": "user", "content": "How to write a Dockerfile?", "topic": "docker"},
        {"role": "assistant", "content": "Basic Dockerfile:\n\n```dockerfile\nFROM python:3.11\nCOPY . .\nCMD [\"python\", \"app.py\"]\n```", "topic": "docker"},
    ]
    
    for i in range(2, 50):
        docker_messages.append({
            "role": "user",
            "content": f"Docker question {i}: How to optimize Docker image size for production?",
            "topic": "docker"
        })
        docker_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use multi-stage builds and alpine base images to reduce size.",
            "topic": "docker"
        })
    
    all_messages = react_messages + python_messages + docker_messages
    
    for i, msg in enumerate(all_messages):
        msg["index"] = i
    
    return all_messages

def create_test_queries():
    """创建测试查询"""
    return [
        {
            "query": "How can I prevent unnecessary re-renders in React components using memoization?",
            "expected_topic": "react",
            "description": "React 性能优化"
        },
        {
            "query": "group aggregate pandas DataFrame",
            "expected_topic": "python",
            "description": "短查询 - Pandas"
        },
        {
            "query": "What are the best practices for reducing Docker image size in production deployments?",
            "expected_topic": "docker",
            "description": "长查询 - Docker"
        },
    ]

def evaluate_recall(recalled: List[Tuple[Dict, float]], expected_topic: str, k: int) -> Dict:
    """评估召回质量"""
    relevant_count = sum(1 for doc, _ in recalled[:k] if doc.get("topic") == expected_topic)
    precision = relevant_count / k if k > 0 else 0.0
    
    first_relevant_rank = None
    for rank, (doc, _) in enumerate(recalled[:k], 1):
        if doc.get("topic") == expected_topic:
            first_relevant_rank = rank
            break
    
    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
    
    return {
        "relevant_count": relevant_count,
        "precision": precision,
        "mrr": mrr,
        "first_relevant_rank": first_relevant_rank or "N/A"
    }

def run_sota_benchmark():
    """运行SOTA算法benchmark"""
    print("="*80)
    print("SOTA 召回算法 Benchmark (2024-2025)")
    print("="*80)
    print()
    
    messages = generate_test_conversation()
    print(f"生成了 {len(messages)} 条消息")
    print()
    
    queries = create_test_queries()
    
    retriever = SOTARetriever()
    retriever.prepare_bm25(messages)
    
    print("\n" + "="*80)
    print("测试策略")
    print("="*80)
    print("1. BM25 Only (稀疏检索)")
    print("2. Dense Only (密集检索)")
    print("3. Hybrid RRF (RRF融合)")
    print("4. Hybrid DAT (动态权重)")
    print("5. Hybrid DAT + Cross-Encoder Reranking (完整SOTA)")
    print()
    
    k = 50
    
    all_results = {
        "BM25 Only": [],
        "Dense Only": [],
        "Hybrid RRF": [],
        "Hybrid DAT": [],
        "Hybrid DAT + Reranking": []
    }
    
    for query_idx, test_case in enumerate(queries, 1):
        print("="*80)
        print(f"测试 {query_idx}/{len(queries)}: {test_case['description']}")
        print(f"Query: {test_case['query']}")
        print(f"Expected: {test_case['expected_topic']}")
        print("="*80)
        
        # 1. BM25 Only
        start = time.time()
        bm25_results = retriever.sparse_retrieval_bm25(test_case['query'], messages, k=k)
        bm25_time = (time.time() - start) * 1000
        bm25_metrics = evaluate_recall(bm25_results, test_case['expected_topic'], k)
        all_results["BM25 Only"].append(bm25_metrics)
        print(f"\n1. BM25 Only: P@{k}={bm25_metrics['precision']*100:.1f}%, Time={bm25_time:.1f}ms")
        
        # 2. Dense Only
        start = time.time()
        dense_results = retriever.dense_retrieval(test_case['query'], messages, k=k)
        dense_time = (time.time() - start) * 1000
        dense_metrics = evaluate_recall(dense_results, test_case['expected_topic'], k)
        all_results["Dense Only"].append(dense_metrics)
        print(f"2. Dense Only: P@{k}={dense_metrics['precision']*100:.1f}%, Time={dense_time:.1f}ms")
        
        # 3. Hybrid RRF
        start = time.time()
        rrf_sparse = retriever.sparse_retrieval_bm25(test_case['query'], messages, k=100)
        rrf_dense = retriever.dense_retrieval(test_case['query'], messages, k=100)
        rrf_results = retriever.reciprocal_rank_fusion(rrf_sparse, rrf_dense, k=60)[:k]
        rrf_time = (time.time() - start) * 1000
        rrf_metrics = evaluate_recall(rrf_results, test_case['expected_topic'], k)
        all_results["Hybrid RRF"].append(rrf_metrics)
        print(f"3. Hybrid RRF: P@{k}={rrf_metrics['precision']*100:.1f}%, Time={rrf_time:.1f}ms")
        
        # 4. Hybrid DAT
        start = time.time()
        dat_results = retriever.hybrid_retrieval_dat(test_case['query'], messages, k=k)
        dat_time = (time.time() - start) * 1000
        dat_metrics = evaluate_recall(dat_results, test_case['expected_topic'], k)
        all_results["Hybrid DAT"].append(dat_metrics)
        print(f"4. Hybrid DAT: P@{k}={dat_metrics['precision']*100:.1f}%, Time={dat_time:.1f}ms")
        
        # 5. Hybrid DAT + Reranking
        start = time.time()
        dat_candidates = retriever.hybrid_retrieval_dat(test_case['query'], messages, k=100)
        reranked_results = retriever.cross_encoder_rerank(test_case['query'], dat_candidates, top_k=k)
        rerank_time = (time.time() - start) * 1000
        rerank_metrics = evaluate_recall(reranked_results, test_case['expected_topic'], k)
        all_results["Hybrid DAT + Reranking"].append(rerank_metrics)
        print(f"5. Hybrid DAT + Reranking: P@{k}={rerank_metrics['precision']*100:.1f}%, Time={rerank_time:.1f}ms")
        print()
    
    # 汇总
    print("\n" + "="*80)
    print("汇总结果：所有查询平均")
    print("="*80)
    print(f"{'策略':<30} {'Precision@50':<15} {'MRR':<10} {'First Rank'}")
    print("-"*80)
    
    for strategy in all_results:
        results = all_results[strategy]
        avg_precision = np.mean([r['precision'] for r in results])
        avg_mrr = np.mean([r['mrr'] for r in results])
        first_ranks = [r['first_relevant_rank'] for r in results if isinstance(r['first_relevant_rank'], int)]
        avg_first_rank = np.mean(first_ranks) if first_ranks else float('inf')
        
        print(f"{strategy:<30} {avg_precision*100:>6.1f}%         {avg_mrr:>6.3f}    {avg_first_rank:>6.1f}")
    
    print("\n" + "="*80)
    print("结论")
    print("="*80)
    best_strategy = max(all_results.keys(), 
                       key=lambda s: np.mean([r['precision'] for r in all_results[s]]))
    best_precision = np.mean([r['precision'] for r in all_results[best_strategy]])
    print(f"\n✅ 最佳策略: {best_strategy}")
    print(f"   Precision@50: {best_precision*100:.1f}%")

if __name__ == "__main__":
    run_sota_benchmark()
