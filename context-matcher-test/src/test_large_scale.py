"""
扩大测试规模：300条消息 + 10个问题类型
验证分层上下文方案在大规模场景下的表现
"""
import numpy as np
import time
import json
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import requests


class LargeScaleTester:
    """大规模测试器：300条消息 + 10个问题类型"""
    
    def __init__(self, api_base: str, api_key: str, model: str):
        print("="*80)
        print("初始化大规模测试器")
        print("="*80)
        
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        
        # CAR组件
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings_cache = {}
        self.cluster_labels = None
        self.cluster_centroids = None
        
        print(f"✓ API: {api_base}")
        print(f"✓ 模型: {model}")
        print()
    
    def generate_large_dataset(self) -> List[Dict]:
        """生成300条真实场景的测试数据"""
        print("\n生成大规模测试数据集 (300条消息)...")
        
        messages = []
        
        # 话题1: React开发 (120条, 40%)
        react_topics = [
            "React Hooks基础",
            "State管理",
            "性能优化",
            "组件设计",
            "路由配置",
            "API集成",
            "表单处理",
            "错误处理",
            "测试",
            "部署"
        ]
        
        react_questions = [
            "How do I use useState in React?",
            "What's the difference between useEffect and useLayoutEffect?",
            "How to prevent unnecessary re-renders?",
            "When should I use useMemo vs useCallback?",
            "How to implement React.lazy for code splitting?",
            "What's the best way to manage global state?",
            "How do I handle form validation in React?",
            "How to optimize rendering performance for large lists?",
            "What are React error boundaries?",
            "How to test React components with Jest?",
            "How do I implement custom hooks?",
            "What's the Context API and when to use it?",
        ]
        
        for i in range(120):
            topic = react_topics[i % len(react_topics)]
            question = react_questions[i % len(react_questions)]
            messages.append({
                "role": "user",
                "content": f"{question} (Topic: {topic}, Scenario {i})",
                "topic": "react",
                "subtopic": topic,
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # 话题2: Python开发 (80条, 27%)
        python_topics = [
            "数据处理",
            "异步编程",
            "面向对象",
            "函数式编程",
            "文件操作",
            "网络请求",
            "数据库",
            "测试"
        ]
        
        python_questions = [
            "How do I read a CSV file with pandas?",
            "What's the difference between lists and tuples?",
            "How to use async/await in Python?",
            "How do I handle exceptions properly?",
            "What's the best way to connect to a database?",
            "How to make HTTP requests in Python?",
            "How do I use list comprehensions?",
            "What are decorators and how do they work?",
            "How to write unit tests with pytest?",
            "How do I work with JSON data?",
        ]
        
        for i in range(80):
            topic = python_topics[i % len(python_topics)]
            question = python_questions[i % len(python_questions)]
            messages.append({
                "role": "user",
                "content": f"{question} (Topic: {topic}, Scenario {i})",
                "topic": "python",
                "subtopic": topic,
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # 话题3: Docker/DevOps (50条, 17%)
        docker_topics = [
            "容器化",
            "镜像优化",
            "编排",
            "网络",
            "存储"
        ]
        
        docker_questions = [
            "How do I create a Dockerfile?",
            "What's the best base image for Node.js?",
            "How to reduce Docker image size?",
            "How do I use docker-compose?",
            "What's the difference between CMD and ENTRYPOINT?",
            "How to handle environment variables in Docker?",
            "How do I debug a running container?",
            "What's Docker networking?",
            "How to persist data in Docker?",
            "How do I optimize build times?",
        ]
        
        for i in range(50):
            topic = docker_topics[i % len(docker_topics)]
            question = docker_questions[i % len(docker_questions)]
            messages.append({
                "role": "user",
                "content": f"{question} (Topic: {topic}, Scenario {i})",
                "topic": "docker",
                "subtopic": topic,
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # 话题4: SQL/数据库 (30条, 10%)
        sql_questions = [
            "What's the difference between INNER JOIN and LEFT JOIN?",
            "How do I optimize slow queries?",
            "What are indexes and when should I use them?",
            "How to prevent SQL injection?",
            "What's database normalization?",
            "How do I use transactions?",
            "What's the difference between SQL and NoSQL?",
            "How to backup and restore a database?",
        ]
        
        for i in range(30):
            question = sql_questions[i % len(sql_questions)]
            messages.append({
                "role": "user",
                "content": f"{question} (Database topic, Scenario {i})",
                "topic": "sql",
                "subtopic": "database",
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # 话题5: Git/版本控制 (20条, 7%)
        git_questions = [
            "How do I resolve merge conflicts?",
            "What's the difference between merge and rebase?",
            "How to undo a commit?",
            "How do I use git branches effectively?",
            "What's git cherry-pick?",
        ]
        
        for i in range(20):
            question = git_questions[i % len(git_questions)]
            messages.append({
                "role": "user",
                "content": f"{question} (Git workflow, Scenario {i})",
                "topic": "git",
                "subtopic": "version-control",
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        print(f"✓ 生成 {len(messages)} 条消息")
        
        # 统计
        topic_counts = {}
        for msg in messages:
            topic = msg['topic']
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(messages) * 100
            print(f"  - {topic}: {count}条 ({percentage:.1f}%)")
        
        return messages
    
    def generate_diverse_queries(self) -> List[Dict]:
        """生成10个不同类型的测试查询"""
        queries = [
            {
                "id": 1,
                "type": "技术具体问题",
                "query": "My React dashboard renders 1000+ rows slowly. How can I optimize the rendering performance with specific code examples?",
                "expected_topic": "react",
                "expected_subtopics": ["性能优化", "组件设计"],
                "complexity": "medium"
            },
            {
                "id": 2,
                "type": "架构设计问题",
                "query": "I'm building a real-time data dashboard. What's the best architecture for managing state between components? Should I use Context, Redux, or something else?",
                "expected_topic": "react",
                "expected_subtopics": ["State管理", "组件设计"],
                "complexity": "high"
            },
            {
                "id": 3,
                "type": "对比分析问题",
                "query": "What's the difference between useMemo and useCallback in React? When should I use each one?",
                "expected_topic": "react",
                "expected_subtopics": ["React Hooks基础", "性能优化"],
                "complexity": "low"
            },
            {
                "id": 4,
                "type": "跨领域综合问题",
                "query": "I need to deploy my React app with Docker. What's the complete workflow from development to production deployment?",
                "expected_topic": "multi",
                "expected_subtopics": ["react-部署", "docker-容器化"],
                "complexity": "high"
            },
            {
                "id": 5,
                "type": "数据处理问题",
                "query": "I have a CSV file with 10,000 rows of user data. How do I load it, clean missing values, and calculate statistics with pandas?",
                "expected_topic": "python",
                "expected_subtopics": ["数据处理"],
                "complexity": "medium"
            },
            {
                "id": 6,
                "type": "调试排错问题",
                "query": "My async Python function is not working as expected. How do I debug async/await code?",
                "expected_topic": "python",
                "expected_subtopics": ["异步编程"],
                "complexity": "medium"
            },
            {
                "id": 7,
                "type": "最佳实践问题",
                "query": "What are the best practices for writing Dockerfiles? How can I reduce my image size and improve build times?",
                "expected_topic": "docker",
                "expected_subtopics": ["镜像优化"],
                "complexity": "medium"
            },
            {
                "id": 8,
                "type": "概念理解问题",
                "query": "Can you explain what database normalization is and why it matters?",
                "expected_topic": "sql",
                "expected_subtopics": ["database"],
                "complexity": "low"
            },
            {
                "id": 9,
                "type": "工作流问题",
                "query": "I accidentally committed sensitive data to git. How do I remove it from history?",
                "expected_topic": "git",
                "expected_subtopics": ["version-control"],
                "complexity": "high"
            },
            {
                "id": 10,
                "type": "模糊开放问题",
                "query": "My web application is slow. How do I find and fix performance bottlenecks?",
                "expected_topic": "multi",
                "expected_subtopics": ["react-性能优化", "sql-优化", "docker-优化"],
                "complexity": "very_high"
            }
        ]
        
        print(f"\n✓ 生成 {len(queries)} 个测试查询")
        for q in queries:
            print(f"  [{q['id']}] {q['type']}: {q['query'][:60]}...")
        
        return queries
    
    def embed(self, text: str) -> np.ndarray:
        """向量化（带缓存）"""
        if text not in self.embeddings_cache:
            self.embeddings_cache[text] = self.embedding_model.encode(text, convert_to_numpy=True)
        return self.embeddings_cache[text]
    
    def build_clusters(self, messages: List[Dict], n_clusters: int = 10):
        """构建聚类索引"""
        print(f"\n构建聚类索引 (n_clusters={n_clusters})...")
        start = time.time()
        
        embeddings = []
        for msg in messages:
            emb = self.embed(msg["content"])
            embeddings.append(emb)
        
        embeddings = np.array(embeddings)
        embeddings_norm = normalize(embeddings)
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.cluster_labels = kmeans.fit_predict(embeddings_norm)
        self.cluster_centroids = kmeans.cluster_centers_
        
        elapsed = (time.time() - start) * 1000
        print(f"✓ 聚类完成: {n_clusters}个簇, 耗时 {elapsed:.1f}ms")
    
    def car_retrieval(self, query: str, messages: List[Dict], k: int = 100) -> List[Dict]:
        """CAR召回"""
        start = time.time()
        
        query_emb = self.embed(query)
        query_emb_norm = normalize(query_emb.reshape(1, -1))[0]
        
        cluster_scores = np.dot(self.cluster_centroids, query_emb_norm)
        top_clusters = np.argsort(cluster_scores)[::-1]
        
        results = []
        for cluster_id in top_clusters:
            cluster_mask = self.cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]
            
            for idx in cluster_indices:
                msg = messages[idx]
                msg_emb = self.embed(msg["content"])
                msg_emb_norm = normalize(msg_emb.reshape(1, -1))[0]
                similarity = float(np.dot(query_emb_norm, msg_emb_norm))
                results.append((msg, similarity, idx))
        
        results.sort(key=lambda x: x[1], reverse=True)
        
        elapsed = (time.time() - start) * 1000
        
        return [(msg, score, idx) for msg, score, idx in results[:k]], elapsed
    
    def evaluate_recall_quality(self, query_info: Dict, retrieved: List[Tuple], 
                                messages: List[Dict], k: int = 50) -> Dict:
        """评估召回质量"""
        expected_topic = query_info["expected_topic"]
        top_k = retrieved[:k]
        
        # 计算Precision@K
        if expected_topic == "multi":
            # 多话题查询：任何相关话题都算正确
            relevant_topics = set()
            for subtopic in query_info["expected_subtopics"]:
                topic = subtopic.split('-')[0]
                relevant_topics.add(topic)
            
            relevant_count = sum(1 for msg, score, idx in top_k 
                               if msg["topic"] in relevant_topics)
        else:
            # 单话题查询
            relevant_count = sum(1 for msg, score, idx in top_k 
                               if msg["topic"] == expected_topic)
        
        precision_at_k = relevant_count / k if k > 0 else 0
        
        # 计算MRR
        first_relevant = None
        for i, (msg, score, idx) in enumerate(top_k, 1):
            if expected_topic == "multi":
                if msg["topic"] in relevant_topics:
                    first_relevant = i
                    break
            else:
                if msg["topic"] == expected_topic:
                    first_relevant = i
                    break
        
        mrr = 1.0 / first_relevant if first_relevant else 0.0
        
        # 话题分布
        topic_dist = {}
        for msg, score, idx in top_k:
            topic = msg["topic"]
            topic_dist[topic] = topic_dist.get(topic, 0) + 1
        
        return {
            "precision_at_k": precision_at_k,
            "mrr": mrr,
            "relevant_count": relevant_count,
            "total_k": k,
            "topic_distribution": topic_dist,
            "first_relevant_rank": first_relevant
        }
    
    def run_large_scale_test(self):
        """运行大规模测试"""
        print(f"\n{'#'*80}")
        print("大规模测试：300条消息 + 10个问题类型")
        print(f"{'#'*80}")
        
        # 生成数据
        messages = self.generate_large_dataset()
        queries = self.generate_diverse_queries()
        
        # 构建聚类
        self.build_clusters(messages, n_clusters=10)
        
        # 测试所有查询
        results = []
        
        for query_info in queries:
            print(f"\n{'='*80}")
            print(f"测试 [{query_info['id']}]: {query_info['type']}")
            print(f"{'='*80}")
            print(f"查询: {query_info['query']}")
            print(f"预期话题: {query_info['expected_topic']}")
            print(f"复杂度: {query_info['complexity']}")
            
            # CAR召回
            retrieved, car_time = self.car_retrieval(query_info['query'], messages, k=100)
            print(f"\n✓ CAR召回完成: {len(retrieved)}条, 耗时 {car_time:.1f}ms")
            
            # 评估质量
            eval_result = self.evaluate_recall_quality(query_info, retrieved, messages, k=50)
            
            print(f"\n召回质量:")
            print(f"  - Precision@50: {eval_result['precision_at_k']*100:.1f}%")
            print(f"  - MRR: {eval_result['mrr']:.3f}")
            print(f"  - 相关消息数: {eval_result['relevant_count']}/50")
            print(f"  - 首个相关消息排名: {eval_result['first_relevant_rank']}")
            
            print(f"\n话题分布 (Top 50):")
            for topic, count in sorted(eval_result['topic_distribution'].items(), 
                                      key=lambda x: x[1], reverse=True):
                percentage = count / 50 * 100
                print(f"  - {topic}: {count}条 ({percentage:.1f}%)")
            
            results.append({
                "query_id": query_info['id'],
                "query_type": query_info['type'],
                "complexity": query_info['complexity'],
                "car_time": car_time,
                **eval_result
            })
        
        # 汇总统计
        self._print_summary(results)
        
        # 保存结果
        output_file = "D:/1m/context-matcher-test/reports/large_scale_test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "test_config": {
                    "total_messages": len(messages),
                    "n_clusters": 10,
                    "k": 100,
                    "num_queries": len(queries)
                },
                "results": results
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 详细结果已保存到: {output_file}")
        
        return results
    
    def _print_summary(self, results: List[Dict]):
        """打印汇总统计"""
        print(f"\n{'#'*80}")
        print("汇总统计")
        print(f"{'#'*80}")
        
        # 总体指标
        avg_precision = np.mean([r['precision_at_k'] for r in results])
        avg_mrr = np.mean([r['mrr'] for r in results])
        avg_car_time = np.mean([r['car_time'] for r in results])
        
        print(f"\n总体性能:")
        print(f"  - 平均 Precision@50: {avg_precision*100:.1f}%")
        print(f"  - 平均 MRR: {avg_mrr:.3f}")
        print(f"  - 平均 CAR延迟: {avg_car_time:.1f}ms")
        
        # 按复杂度分组
        complexity_groups = {}
        for r in results:
            complexity = r['complexity']
            if complexity not in complexity_groups:
                complexity_groups[complexity] = []
            complexity_groups[complexity].append(r)
        
        print(f"\n按复杂度分组:")
        for complexity in ['low', 'medium', 'high', 'very_high']:
            if complexity in complexity_groups:
                group = complexity_groups[complexity]
                avg_p = np.mean([r['precision_at_k'] for r in group])
                avg_m = np.mean([r['mrr'] for r in group])
                print(f"  - {complexity}: Precision={avg_p*100:.1f}%, MRR={avg_m:.3f} (n={len(group)})")
        
        # 最佳和最差
        best = max(results, key=lambda x: x['precision_at_k'])
        worst = min(results, key=lambda x: x['precision_at_k'])
        
        print(f"\n最佳表现:")
        print(f"  - 查询{best['query_id']} ({best['query_type']})")
        print(f"  - Precision@50: {best['precision_at_k']*100:.1f}%")
        
        print(f"\n最差表现:")
        print(f"  - 查询{worst['query_id']} ({worst['query_type']})")
        print(f"  - Precision@50: {worst['precision_at_k']*100:.1f}%")


if __name__ == "__main__":
    # API配置
    API_BASE = "http://154.201.79.82:8080/v1"
    API_KEY = "sk-asdfghjkl123456"
    MODEL = "Gemini 3 Flash Preview"
    
    # 运行大规模测试
    tester = LargeScaleTester(API_BASE, API_KEY, MODEL)
    results = tester.run_large_scale_test()
