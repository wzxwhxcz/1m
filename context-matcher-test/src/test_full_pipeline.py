"""
完整流程测试：CAR粗筛 + Gemini精排
验证整个架构的端到端效果
"""
import numpy as np
import time
import json
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import requests


class FullPipelineTester:
    """完整流程测试器"""
    
    def __init__(self, api_base: str, api_key: str, model: str):
        print("初始化完整流程测试器...")
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        
        # CAR组件
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings_cache = {}
        self.cluster_labels = None
        self.cluster_centroids = None
        
        print(f"✓ API配置: {api_base}")
        print(f"✓ 模型: {model}")
    
    def embed(self, text: str) -> np.ndarray:
        """向量化（带缓存）"""
        if text not in self.embeddings_cache:
            self.embeddings_cache[text] = self.embedding_model.encode(text, convert_to_numpy=True)
        return self.embeddings_cache[text]
    
    def build_clusters(self, messages: List[Dict], n_clusters: int = 3):
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
    
    def car_retrieval(self, query: str, messages: List[Dict], k: int = 50) -> Tuple[List[Dict], float]:
        """CAR粗筛"""
        start = time.time()
        
        # 查询向量化
        query_emb = self.embed(query)
        query_emb_norm = normalize(query_emb.reshape(1, -1))[0]
        
        # 计算与簇中心的相似度
        cluster_scores = np.dot(self.cluster_centroids, query_emb_norm)
        top_clusters = np.argsort(cluster_scores)[::-1]
        
        # 从相关簇中召回
        results = []
        for cluster_id in top_clusters:
            cluster_mask = self.cluster_labels == cluster_id
            cluster_indices = np.where(cluster_mask)[0]
            
            for idx in cluster_indices:
                msg = messages[idx]
                msg_emb = self.embed(msg["content"])
                msg_emb_norm = normalize(msg_emb.reshape(1, -1))[0]
                similarity = np.dot(query_emb_norm, msg_emb_norm)
                results.append((msg, similarity))
        
        # 全局排序
        results.sort(key=lambda x: x[1], reverse=True)
        top_results = [msg for msg, score in results[:k]]
        
        elapsed = (time.time() - start) * 1000
        return top_results, elapsed
    
    def llm_rerank(self, query: str, candidates: List[Dict], top_k: int = 10) -> Tuple[str, float, Dict]:
        """LLM精排"""
        print(f"\n调用LLM精排 (模型: {self.model})...")
        start = time.time()
        
        # 构建精排提示
        candidates_text = "\n\n".join([
            f"[消息{i+1}] {msg['content']}"
            for i, msg in enumerate(candidates[:50])  # 限制到前50条
        ])
        
        prompt = f"""你是一个智能上下文筛选助手。用户正在与AI对话，当前有大量历史消息。你的任务是从候选消息中筛选出与用户当前问题最相关的内容。

用户当前问题:
{query}

候选历史消息 (共{len(candidates[:50])}条):
{candidates_text}

请完成以下任务:
1. 分析用户问题的核心意图
2. 从候选消息中选出最相关的{top_k}条消息编号（按相关性从高到低排序）
3. 生成一段精简的上下文摘要（200字以内），概括这些相关消息的关键信息

请以JSON格式返回结果:
{{
    "intent": "用户问题的核心意图",
    "selected_messages": [1, 5, 3, ...],  // 最相关的消息编号
    "summary": "精简的上下文摘要",
    "reasoning": "选择理由"
}}"""
        
        # 调用API
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 65536
                },
                timeout=30
            )
            
            elapsed = (time.time() - start) * 1000
            
            if response.status_code != 200:
                print(f"❌ API调用失败: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None, elapsed, None
            
            result = response.json()
            
            if "choices" not in result or len(result["choices"]) == 0:
                print(f"❌ API响应格式错误: {result}")
                return None, elapsed, None
            
            llm_output = result["choices"][0]["message"]["content"]
            
            # 尝试解析JSON
            try:
                # 提取JSON部分（处理可能的markdown代码块）
                if "```json" in llm_output:
                    json_start = llm_output.find("```json") + 7
                    json_end = llm_output.find("```", json_start)
                    json_str = llm_output[json_start:json_end].strip()
                elif "```" in llm_output:
                    json_start = llm_output.find("```") + 3
                    json_end = llm_output.find("```", json_start)
                    json_str = llm_output[json_start:json_end].strip()
                else:
                    json_str = llm_output.strip()
                
                parsed = json.loads(json_str)
                
                print(f"✓ LLM精排完成，耗时 {elapsed:.1f}ms")
                print(f"✓ 用户意图: {parsed.get('intent', 'N/A')}")
                print(f"✓ 选中消息: {len(parsed.get('selected_messages', []))}条")
                
                return llm_output, elapsed, parsed
                
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON解析失败: {e}")
                print(f"LLM原始输出:\n{llm_output}")
                return llm_output, elapsed, None
        
        except requests.exceptions.Timeout:
            elapsed = (time.time() - start) * 1000
            print(f"❌ API调用超时 (>{elapsed:.0f}ms)")
            return None, elapsed, None
        
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            print(f"❌ API调用异常: {e}")
            return None, elapsed, None
    
    def generate_test_data(self):
        """生成测试数据：300条消息，3个话题"""
        print("\n生成测试数据...")
        
        messages = []
        
        # 话题1: React (0-99)
        react_topics = [
            "How to use useState hook in React functional components?",
            "useEffect cleanup function and dependency array best practices",
            "React component lifecycle methods vs hooks comparison",
            "Preventing unnecessary re-renders with React.memo and useMemo",
            "Understanding useCallback and when to use it",
            "React Context API for state management tutorial",
            "useReducer vs useState for complex state logic",
            "React custom hooks creation and best practices",
            "React Suspense and lazy loading components",
            "React performance optimization techniques",
        ]
        
        # 话题2: Python数据分析 (100-199)
        python_topics = [
            "pandas DataFrame basic operations and methods",
            "numpy array manipulation and broadcasting",
            "matplotlib plotting examples and customization",
            "How to group and aggregate data in pandas DataFrame",
            "pandas merge vs join differences and use cases",
            "numpy linear algebra operations explained",
            "seaborn statistical visualization gallery",
            "pandas read_csv options and performance tuning",
            "numpy advanced indexing and slicing",
            "matplotlib subplots and figure layout",
        ]
        
        # 话题3: Docker (200-299)
        docker_topics = [
            "Dockerfile best practices for production",
            "docker-compose multi-container application setup",
            "How to reduce Docker image size effectively",
            "Docker networking modes and bridge networks",
            "Docker volumes vs bind mounts comparison",
            "Multi-stage Docker builds optimization",
            "Docker health checks configuration",
            "Docker secrets management strategies",
            "Docker Swarm vs Kubernetes comparison",
            "Docker layer caching and build optimization",
        ]
        
        # 生成300条消息
        for i in range(100):
            messages.append({
                "role": "user",
                "content": react_topics[i % len(react_topics)] + f" Additional context about React development scenario {i}.",
                "topic": "react",
                "index": i
            })
        
        for i in range(100):
            messages.append({
                "role": "user",
                "content": python_topics[i % len(python_topics)] + f" Data analysis use case number {i}.",
                "topic": "python",
                "index": 100 + i
            })
        
        for i in range(100):
            messages.append({
                "role": "user",
                "content": docker_topics[i % len(docker_topics)] + f" Container deployment scenario {i}.",
                "topic": "docker",
                "index": 200 + i
            })
        
        print(f"✓ 生成 {len(messages)} 条消息")
        return messages
    
    def run_test(self):
        """运行完整流程测试"""
        print("="*80)
        print("完整流程测试: CAR粗筛 + LLM精排")
        print("="*80)
        
        # 生成测试数据
        messages = self.generate_test_data()
        
        # 构建聚类索引
        self.build_clusters(messages, n_clusters=3)
        
        # 测试查询
        test_queries = [
            {
                "query": "How can I optimize React component rendering performance?",
                "expected_topic": "react",
                "description": "React性能优化相关"
            },
            {
                "query": "What's the best way to group and aggregate data in pandas?",
                "expected_topic": "python",
                "description": "Pandas数据聚合"
            },
            {
                "query": "How to reduce Docker image size for production deployment?",
                "expected_topic": "docker",
                "description": "Docker镜像优化"
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_queries):
            print(f"\n{'='*80}")
            print(f"测试 {i+1}/{len(test_queries)}: {test_case['description']}")
            print(f"{'='*80}")
            print(f"用户问题: {test_case['query']}")
            print(f"预期话题: {test_case['expected_topic']}")
            
            # 第一层：CAR粗筛
            print(f"\n【第一层】CAR粗筛...")
            candidates, car_time = self.car_retrieval(test_case['query'], messages, k=50)
            
            # 统计粗筛结果
            topic_counts = {}
            for msg in candidates[:50]:
                topic = msg.get("topic", "unknown")
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            car_precision = topic_counts.get(test_case['expected_topic'], 0) / 50 * 100
            
            print(f"✓ 粗筛完成: 召回50条候选消息")
            print(f"  话题分布: {topic_counts}")
            print(f"  Precision@50: {car_precision:.1f}%")
            print(f"  耗时: {car_time:.1f}ms")
            
            # 第二层：LLM精排
            print(f"\n【第二层】LLM精排...")
            llm_output, llm_time, parsed = self.llm_rerank(
                test_case['query'],
                candidates,
                top_k=10
            )
            
            if parsed:
                print(f"\n精排结果:")
                print(f"  用户意图: {parsed.get('intent', 'N/A')}")
                print(f"  选中消息: {parsed.get('selected_messages', [])}")
                print(f"  摘要: {parsed.get('summary', 'N/A')[:100]}...")
                print(f"  选择理由: {parsed.get('reasoning', 'N/A')[:100]}...")
                
                # 验证选中的消息是否正确
                selected_indices = parsed.get('selected_messages', [])
                if selected_indices:
                    selected_topics = [candidates[idx-1].get("topic", "unknown") 
                                     for idx in selected_indices 
                                     if 0 < idx <= len(candidates)]
                    
                    correct_count = sum(1 for t in selected_topics if t == test_case['expected_topic'])
                    llm_precision = correct_count / len(selected_topics) * 100 if selected_topics else 0
                    
                    print(f"\n  选中消息话题分布: {dict((t, selected_topics.count(t)) for t in set(selected_topics))}")
                    print(f"  LLM精排准确率: {llm_precision:.1f}%")
                else:
                    llm_precision = 0
            else:
                print(f"\n精排结果 (未能解析JSON):")
                if llm_output:
                    print(f"  原始输出: {llm_output[:200]}...")
                llm_precision = 0
            
            # 记录结果
            result = {
                "query": test_case['query'],
                "expected_topic": test_case['expected_topic'],
                "car_precision": car_precision,
                "car_time": car_time,
                "llm_precision": llm_precision,
                "llm_time": llm_time,
                "total_time": car_time + llm_time,
                "parsed": parsed is not None
            }
            results.append(result)
            
            print(f"\n总耗时: {result['total_time']:.1f}ms (粗筛{car_time:.1f}ms + 精排{llm_time:.1f}ms)")
        
        # 汇总报告
        self._print_summary(results)
        
        return results
    
    def _print_summary(self, results: List[Dict]):
        """打印汇总报告"""
        print(f"\n{'='*80}")
        print("测试汇总")
        print(f"{'='*80}")
        
        print(f"\n{'查询':<50} {'CAR准确率':<12} {'LLM准确率':<12} {'总耗时'}")
        print("-" * 80)
        
        for r in results:
            query_short = r['query'][:47] + "..." if len(r['query']) > 50 else r['query']
            print(f"{query_short:<50} {r['car_precision']:>6.1f}%      {r['llm_precision']:>6.1f}%      {r['total_time']:>6.0f}ms")
        
        # 平均指标
        avg_car_precision = np.mean([r['car_precision'] for r in results])
        avg_llm_precision = np.mean([r['llm_precision'] for r in results])
        avg_total_time = np.mean([r['total_time'] for r in results])
        
        print("-" * 80)
        print(f"{'平均':<50} {avg_car_precision:>6.1f}%      {avg_llm_precision:>6.1f}%      {avg_total_time:>6.0f}ms")
        
        # 成功率
        parse_success_rate = sum(1 for r in results if r['parsed']) / len(results) * 100
        
        print(f"\n关键指标:")
        print(f"  CAR粗筛平均准确率: {avg_car_precision:.1f}%")
        print(f"  LLM精排平均准确率: {avg_llm_precision:.1f}%")
        print(f"  JSON解析成功率: {parse_success_rate:.1f}%")
        print(f"  平均总耗时: {avg_total_time:.0f}ms")
        
        if avg_car_precision >= 90 and parse_success_rate >= 80:
            print(f"\n✅ 测试通过！系统运行正常")
        else:
            print(f"\n⚠️  测试未完全通过，请检查配置")


if __name__ == "__main__":
    # API配置
    API_BASE = "http://154.201.79.82:8080/v1"
    API_KEY = "sk-asdfghjkl123456"
    MODEL = "Gemini 3 Flash Preview"
    
    # 运行测试
    tester = FullPipelineTester(API_BASE, API_KEY, MODEL)
    results = tester.run_test()
