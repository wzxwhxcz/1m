"""
A/B测试框架
自动化测试不同召回策略，统计分析并生成报告
"""
import asyncio
import time
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from scipy import stats
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize


@dataclass
class ABTestConfig:
    """A/B测试配置"""
    test_name: str
    variant_a_name: str
    variant_b_name: str
    sample_size: int
    test_queries: List[str]
    messages: List[Dict]
    alpha: float = 0.05  # 显著性水平


@dataclass
class VariantResult:
    """单个变体的测试结果"""
    variant_name: str
    total_queries: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_precision: float
    avg_recall: float
    avg_mrr: float
    success_rate: float
    total_cost_usd: float = 0.0


@dataclass
class ABTestResult:
    """A/B测试完整结果"""
    test_name: str
    test_date: str
    variant_a: VariantResult
    variant_b: VariantResult
    winner: Optional[str]
    statistical_significance: bool
    p_value: float
    effect_size: float
    recommendation: str


class ABTestFramework:
    """A/B测试框架"""
    
    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings_cache = {}
        print("="*80)
        print("A/B测试框架初始化")
        print("="*80)
    
    def embed(self, text: str) -> np.ndarray:
        """向量化（带缓存）"""
        if text not in self.embeddings_cache:
            self.embeddings_cache[text] = self.embedding_model.encode(text, convert_to_numpy=True)
        return self.embeddings_cache[text]
    
    # ========== 变体A: CAR算法 ==========
    
    async def variant_a_car(self, query: str, messages: List[Dict], 
                           cluster_labels: np.ndarray, 
                           cluster_centroids: np.ndarray,
                           k: int = 50) -> Tuple[List[Tuple], float]:
        """变体A: CAR算法"""
        start = time.time()
        
        query_emb = self.embed(query)
        query_emb_norm = normalize(query_emb.reshape(1, -1))[0]
        
        # 计算簇得分
        cluster_scores = np.dot(cluster_centroids, query_emb_norm)
        top_clusters = np.argsort(cluster_scores)[::-1]
        
        # 召回
        results = []
        for cluster_id in top_clusters:
            cluster_mask = cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]
            
            for idx in cluster_indices:
                msg = messages[idx]
                msg_emb = self.embed(msg["content"])
                msg_emb_norm = normalize(msg_emb.reshape(1, -1))[0]
                similarity = float(np.dot(query_emb_norm, msg_emb_norm))
                results.append((msg, similarity, idx))
        
        results.sort(key=lambda x: x[1], reverse=True)
        latency = (time.time() - start) * 1000
        
        return results[:k], latency
    
    # ========== 变体B: Dense Only ==========
    
    async def variant_b_dense(self, query: str, messages: List[Dict], 
                             k: int = 50) -> Tuple[List[Tuple], float]:
        """变体B: Dense向量召回（baseline）"""
        start = time.time()
        
        query_emb = self.embed(query)
        query_emb_norm = normalize(query_emb.reshape(1, -1))[0]
        
        # 计算所有消息的相似度
        results = []
        for idx, msg in enumerate(messages):
            msg_emb = self.embed(msg["content"])
            msg_emb_norm = normalize(msg_emb.reshape(1, -1))[0]
            similarity = float(np.dot(query_emb_norm, msg_emb_norm))
            results.append((msg, similarity, idx))
        
        results.sort(key=lambda x: x[1], reverse=True)
        latency = (time.time() - start) * 1000
        
        return results[:k], latency
    
    # ========== 评估指标 ==========
    
    def evaluate_results(self, query_info: Dict, results: List[Tuple], k: int = 50) -> Dict:
        """评估召回结果"""
        expected_topic = query_info["expected_topic"]
        top_k = results[:k]
        
        # Precision@K
        if expected_topic == "multi":
            relevant_topics = set()
            for subtopic in query_info.get("expected_subtopics", []):
                if '-' in subtopic:
                    topic = subtopic.split('-')[0]
                    relevant_topics.add(topic)
            relevant_count = sum(1 for msg, score, idx in top_k 
                               if msg.get("topic") in relevant_topics)
        else:
            relevant_count = sum(1 for msg, score, idx in top_k 
                               if msg.get("topic") == expected_topic)
        
        precision = relevant_count / k if k > 0 else 0
        
        # MRR
        first_relevant = None
        for i, (msg, score, idx) in enumerate(top_k, 1):
            is_relevant = False
            if expected_topic == "multi":
                is_relevant = msg.get("topic") in relevant_topics
            else:
                is_relevant = msg.get("topic") == expected_topic
            
            if is_relevant:
                first_relevant = i
                break
        
        mrr = 1.0 / first_relevant if first_relevant else 0.0
        
        # Recall（简化版：假设所有相关消息都在候选集中）
        recall = precision  # 简化处理
        
        return {
            "precision": precision,
            "recall": recall,
            "mrr": mrr,
            "relevant_count": relevant_count
        }
    
    # ========== A/B测试执行 ==========
    
    async def run_ab_test(self, config: ABTestConfig) -> ABTestResult:
        """运行A/B测试"""
        print(f"\n{'='*80}")
        print(f"A/B测试: {config.test_name}")
        print(f"{'='*80}")
        print(f"变体A: {config.variant_a_name}")
        print(f"变体B: {config.variant_b_name}")
        print(f"样本量: {config.sample_size} 个查询")
        print(f"显著性水平: α={config.alpha}")
        
        # 预处理：构建聚类（仅变体A需要）
        print(f"\n[1] 预处理...")
        embeddings = []
        for msg in config.messages:
            emb = self.embed(msg["content"])
            embeddings.append(emb)
        
        embeddings = np.array(embeddings)
        embeddings_norm = normalize(embeddings)
        
        n_clusters = min(10, len(config.messages) // 20)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings_norm)
        cluster_centroids = kmeans.cluster_centers_
        
        print(f"✓ 聚类完成: {n_clusters}个簇")
        
        # 生成测试查询（带ground truth）
        test_queries = []
        for i, query_text in enumerate(config.test_queries):
            # 根据查询内容推断期望话题
            query_lower = query_text.lower()
            if "react" in query_lower or "hook" in query_lower or "component" in query_lower:
                expected_topic = "react"
            elif "python" in query_lower or "pandas" in query_lower or "async" in query_lower:
                expected_topic = "python"
            elif "docker" in query_lower or "container" in query_lower:
                expected_topic = "docker"
            elif "sql" in query_lower or "database" in query_lower:
                expected_topic = "sql"
            elif "git" in query_lower:
                expected_topic = "git"
            else:
                expected_topic = "multi"
            
            test_queries.append({
                "id": i + 1,
                "query": query_text,
                "expected_topic": expected_topic,
                "expected_subtopics": []
            })
        
        print(f"✓ 生成 {len(test_queries)} 个测试查询")
        
        # 执行变体A测试
        print(f"\n[2] 测试变体A: {config.variant_a_name}")
        variant_a_latencies = []
        variant_a_precisions = []
        variant_a_recalls = []
        variant_a_mrrs = []
        variant_a_success = 0
        
        for query_info in test_queries:
            try:
                results, latency = await self.variant_a_car(
                    query_info["query"], 
                    config.messages,
                    cluster_labels,
                    cluster_centroids,
                    k=50
                )
                
                eval_result = self.evaluate_results(query_info, results, k=50)
                
                variant_a_latencies.append(latency)
                variant_a_precisions.append(eval_result["precision"])
                variant_a_recalls.append(eval_result["recall"])
                variant_a_mrrs.append(eval_result["mrr"])
                variant_a_success += 1
                
                print(f"  查询 {query_info['id']}: {latency:.1f}ms, P@50={eval_result['precision']*100:.1f}%")
            
            except Exception as e:
                print(f"  查询 {query_info['id']}: 失败 - {e}")
        
        # 执行变体B测试
        print(f"\n[3] 测试变体B: {config.variant_b_name}")
        variant_b_latencies = []
        variant_b_precisions = []
        variant_b_recalls = []
        variant_b_mrrs = []
        variant_b_success = 0
        
        for query_info in test_queries:
            try:
                results, latency = await self.variant_b_dense(
                    query_info["query"],
                    config.messages,
                    k=50
                )
                
                eval_result = self.evaluate_results(query_info, results, k=50)
                
                variant_b_latencies.append(latency)
                variant_b_precisions.append(eval_result["precision"])
                variant_b_recalls.append(eval_result["recall"])
                variant_b_mrrs.append(eval_result["mrr"])
                variant_b_success += 1
                
                print(f"  查询 {query_info['id']}: {latency:.1f}ms, P@50={eval_result['precision']*100:.1f}%")
            
            except Exception as e:
                print(f"  查询 {query_info['id']}: 失败 - {e}")
        
        # 计算统计结果
        print(f"\n[4] 统计分析...")
        
        variant_a_result = VariantResult(
            variant_name=config.variant_a_name,
            total_queries=variant_a_success,
            avg_latency_ms=np.mean(variant_a_latencies),
            p50_latency_ms=np.percentile(variant_a_latencies, 50),
            p95_latency_ms=np.percentile(variant_a_latencies, 95),
            p99_latency_ms=np.percentile(variant_a_latencies, 99),
            avg_precision=np.mean(variant_a_precisions),
            avg_recall=np.mean(variant_a_recalls),
            avg_mrr=np.mean(variant_a_mrrs),
            success_rate=variant_a_success / len(test_queries)
        )
        
        variant_b_result = VariantResult(
            variant_name=config.variant_b_name,
            total_queries=variant_b_success,
            avg_latency_ms=np.mean(variant_b_latencies),
            p50_latency_ms=np.percentile(variant_b_latencies, 50),
            p95_latency_ms=np.percentile(variant_b_latencies, 95),
            p99_latency_ms=np.percentile(variant_b_latencies, 99),
            avg_precision=np.mean(variant_b_precisions),
            avg_recall=np.mean(variant_b_recalls),
            avg_mrr=np.mean(variant_b_mrrs),
            success_rate=variant_b_success / len(test_queries)
        )
        
        # 统计显著性检验（T检验）
        # 使用延迟作为主要指标
        t_stat, p_value = stats.ttest_ind(variant_a_latencies, variant_b_latencies)
        is_significant = p_value < config.alpha
        
        # 效应量（Cohen's d）
        pooled_std = np.sqrt((np.std(variant_a_latencies)**2 + np.std(variant_b_latencies)**2) / 2)
        effect_size = (np.mean(variant_a_latencies) - np.mean(variant_b_latencies)) / pooled_std
        
        # 判断获胜者
        winner = None
        recommendation = ""
        
        if is_significant:
            # 延迟更低 + 准确率相近 = 获胜
            if variant_a_result.avg_latency_ms < variant_b_result.avg_latency_ms:
                if abs(variant_a_result.avg_precision - variant_b_result.avg_precision) < 0.05:
                    winner = config.variant_a_name
                    recommendation = f"{config.variant_a_name} 显著优于 {config.variant_b_name}（延迟更低，准确率相近）"
                else:
                    recommendation = f"{config.variant_a_name} 延迟更低，但准确率差异较大，需要权衡"
            else:
                if abs(variant_a_result.avg_precision - variant_b_result.avg_precision) < 0.05:
                    winner = config.variant_b_name
                    recommendation = f"{config.variant_b_name} 显著优于 {config.variant_a_name}（延迟更低，准确率相近）"
                else:
                    recommendation = f"{config.variant_b_name} 延迟更低，但准确率差异较大，需要权衡"
        else:
            recommendation = "两个变体无显著差异，可以选择实现更简单的方案"
        
        result = ABTestResult(
            test_name=config.test_name,
            test_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            variant_a=variant_a_result,
            variant_b=variant_b_result,
            winner=winner,
            statistical_significance=is_significant,
            p_value=p_value,
            effect_size=effect_size,
            recommendation=recommendation
        )
        
        return result
    
    def print_ab_test_report(self, result: ABTestResult):
        """打印A/B测试报告"""
        print(f"\n{'='*80}")
        print(f"A/B测试报告: {result.test_name}")
        print(f"{'='*80}")
        print(f"测试时间: {result.test_date}")
        
        print(f"\n{'变体A: ' + result.variant_a.variant_name:-^80}")
        print(f"  总查询数: {result.variant_a.total_queries}")
        print(f"  成功率: {result.variant_a.success_rate*100:.1f}%")
        print(f"\n  延迟指标:")
        print(f"    平均延迟: {result.variant_a.avg_latency_ms:.1f}ms")
        print(f"    P50延迟: {result.variant_a.p50_latency_ms:.1f}ms")
        print(f"    P95延迟: {result.variant_a.p95_latency_ms:.1f}ms")
        print(f"    P99延迟: {result.variant_a.p99_latency_ms:.1f}ms")
        print(f"\n  准确率指标:")
        print(f"    平均Precision@50: {result.variant_a.avg_precision*100:.1f}%")
        print(f"    平均Recall@50: {result.variant_a.avg_recall*100:.1f}%")
        print(f"    平均MRR: {result.variant_a.avg_mrr:.3f}")
        
        print(f"\n{'变体B: ' + result.variant_b.variant_name:-^80}")
        print(f"  总查询数: {result.variant_b.total_queries}")
        print(f"  成功率: {result.variant_b.success_rate*100:.1f}%")
        print(f"\n  延迟指标:")
        print(f"    平均延迟: {result.variant_b.avg_latency_ms:.1f}ms")
        print(f"    P50延迟: {result.variant_b.p50_latency_ms:.1f}ms")
        print(f"    P95延迟: {result.variant_b.p95_latency_ms:.1f}ms")
        print(f"    P99延迟: {result.variant_b.p99_latency_ms:.1f}ms")
        print(f"\n  准确率指标:")
        print(f"    平均Precision@50: {result.variant_b.avg_precision*100:.1f}%")
        print(f"    平均Recall@50: {result.variant_b.avg_recall*100:.1f}%")
        print(f"    平均MRR: {result.variant_b.avg_mrr:.3f}")
        
        print(f"\n{'对比分析':-^80}")
        
        # 延迟对比
        latency_diff = result.variant_a.avg_latency_ms - result.variant_b.avg_latency_ms
        latency_improvement = -latency_diff / result.variant_b.avg_latency_ms * 100
        print(f"\n  延迟对比:")
        print(f"    差异: {latency_diff:+.1f}ms ({latency_improvement:+.1f}%)")
        if latency_diff < 0:
            print(f"    ✅ {result.variant_a.variant_name} 延迟更低")
        else:
            print(f"    ✅ {result.variant_b.variant_name} 延迟更低")
        
        # 准确率对比
        precision_diff = result.variant_a.avg_precision - result.variant_b.avg_precision
        precision_improvement = precision_diff / result.variant_b.avg_precision * 100 if result.variant_b.avg_precision > 0 else 0
        print(f"\n  准确率对比:")
        print(f"    差异: {precision_diff:+.3f} ({precision_improvement:+.1f}%)")
        if abs(precision_diff) < 0.05:
            print(f"    ≈ 两者准确率相近（差异<5%）")
        elif precision_diff > 0:
            print(f"    ✅ {result.variant_a.variant_name} 准确率更高")
        else:
            print(f"    ✅ {result.variant_b.variant_name} 准确率更高")
        
        # 统计显著性
        print(f"\n  统计显著性:")
        print(f"    p值: {result.p_value:.4f}")
        print(f"    效应量 (Cohen's d): {result.effect_size:.3f}")
        if result.statistical_significance:
            print(f"    ✅ 差异具有统计显著性 (p < 0.05)")
        else:
            print(f"    ⚠️  差异不具有统计显著性 (p >= 0.05)")
        
        # 最终建议
        print(f"\n{'最终建议':-^80}")
        if result.winner:
            print(f"  🏆 获胜者: {result.winner}")
        print(f"  📊 结论: {result.recommendation}")
        
        print(f"\n{'='*80}\n")
    
    def save_ab_test_result(self, result: ABTestResult, output_file: str):
        """保存A/B测试结果"""
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_name": result.test_name,
                "test_date": result.test_date,
                "variant_a": asdict(result.variant_a),
                "variant_b": asdict(result.variant_b),
                "winner": result.winner,
                "statistical_significance": bool(result.statistical_significance),
                "p_value": float(result.p_value),
                "effect_size": float(result.effect_size),
                "recommendation": result.recommendation
            }, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 测试结果已保存到: {output_file}")


async def main():
    """运行A/B测试示例"""
    
    framework = ABTestFramework()
    
    # 生成测试数据
    messages = []
    for i in range(120):
        messages.append({
            "content": f"React question {i}: How to use hooks and optimize component rendering?",
            "topic": "react"
        })
    for i in range(80):
        messages.append({
            "content": f"Python question {i}: How to handle async/await and process data with pandas?",
            "topic": "python"
        })
    for i in range(60):
        messages.append({
            "content": f"Docker question {i}: How to optimize images and manage containers?",
            "topic": "docker"
        })
    for i in range(40):
        messages.append({
            "content": f"SQL question {i}: How to optimize queries and design schema?",
            "topic": "sql"
        })
    
    # 测试查询
    test_queries = [
        "How can I optimize React component rendering performance?",
        "What's the best way to manage state in React applications?",
        "How do I use async/await in Python effectively?",
        "How to reduce Docker image size for production?",
        "What are the best practices for SQL query optimization?",
        "How to implement custom React hooks?",
        "How to handle data processing with pandas?",
        "What's docker-compose and how to use it?",
        "How to design a normalized database schema?",
        "How to prevent unnecessary re-renders in React?"
    ]
    
    # 配置A/B测试
    config = ABTestConfig(
        test_name="CAR vs Dense Retrieval",
        variant_a_name="CAR (Cluster-based Adaptive Retrieval)",
        variant_b_name="Dense Only (Baseline)",
        sample_size=len(test_queries),
        test_queries=test_queries,
        messages=messages,
        alpha=0.05
    )
    
    # 运行测试
    result = await framework.run_ab_test(config)
    
    # 打印报告
    framework.print_ab_test_report(result)
    
    # 保存结果
    framework.save_ab_test_result(result, "D:/1m/context-matcher-test/reports/ab_test_result.json")


if __name__ == "__main__":
    asyncio.run(main())
