"""
粗筛召回质量测试：测试从大量历史消息中召回最相关消息的效果

测试目标：
1. 给定一个真实的用户问题 (query)
2. 给定大量历史对话 (300+ 条消息)
3. 测试不同粗筛策略能否召回与 query 真正相关的消息

评估指标：
- Recall@K: 在召回的前K条中，有多少是真正相关的
- Precision@K: 召回的前K条中，相关消息的比例
- MRR: Mean Reciprocal Rank (第一个相关结果的排名倒数)
"""
import json
import time
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Tuple
import random

class RecallTester:
    def __init__(self):
        print("加载 embedding 模型...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        print("模型加载完成")
    
    def embed(self, text: str) -> np.ndarray:
        """向量化文本"""
        return self.model.encode(text, normalize_embeddings=True)
    
    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度"""
        return float(np.dot(a, b))
    
    def extract_keywords(self, text: str) -> set:
        """提取关键词（简化版）"""
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                     'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                     'what', 'how', 'why', 'when', 'where', 'who', 'which', 'this', 'that',
                     'i', 'you', 'it', 'they', 'we', 'my', 'your', 'do', 'does', 'did'}
        
        words = text.lower().split()
        keywords = {w.strip('.,?!;:') for w in words if len(w) > 3 and w not in stopwords}
        return keywords
    
    def recall_by_vector(self, query: str, messages: List[Dict], k: int = 50) -> List[Tuple[Dict, float]]:
        """策略1：纯向量相似度召回"""
        query_embedding = self.embed(query)
        
        results = []
        for msg in messages:
            msg_embedding = self.embed(msg["content"])
            similarity = self.cosine_similarity(query_embedding, msg_embedding)
            results.append((msg, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def recall_by_keyword(self, query: str, messages: List[Dict], k: int = 50) -> List[Tuple[Dict, float]]:
        """策略2：关键词匹配召回"""
        query_keywords = self.extract_keywords(query)
        
        results = []
        for msg in messages:
            msg_keywords = self.extract_keywords(msg["content"])
            overlap = len(query_keywords & msg_keywords)
            jaccard = overlap / len(query_keywords | msg_keywords) if len(query_keywords | msg_keywords) > 0 else 0.0
            results.append((msg, jaccard))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def recall_hybrid(self, query: str, messages: List[Dict], k: int = 50) -> List[Tuple[Dict, float]]:
        """策略3：混合策略（向量 0.6 + 关键词 0.4）"""
        query_embedding = self.embed(query)
        query_keywords = self.extract_keywords(query)
        
        results = []
        for msg in messages:
            msg_embedding = self.embed(msg["content"])
            vector_sim = self.cosine_similarity(query_embedding, msg_embedding)
            
            msg_keywords = self.extract_keywords(msg["content"])
            overlap = len(query_keywords & msg_keywords)
            keyword_sim = overlap / len(query_keywords | msg_keywords) if len(query_keywords | msg_keywords) > 0 else 0.0
            
            hybrid_score = 0.6 * vector_sim + 0.4 * keyword_sim
            results.append((msg, hybrid_score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]
    
    def recall_with_time_decay(self, query: str, messages: List[Dict], k: int = 50) -> List[Tuple[Dict, float]]:
        """策略4：向量 + 时间衰减（越新的消息权重越高）"""
        query_embedding = self.embed(query)
        
        results = []
        total_msgs = len(messages)
        for i, msg in enumerate(messages):
            msg_embedding = self.embed(msg["content"])
            vector_sim = self.cosine_similarity(query_embedding, msg_embedding)
            
            time_weight = 0.5 + 0.5 * (i / total_msgs)
            score = 0.7 * vector_sim + 0.3 * time_weight
            results.append((msg, score))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

def generate_realistic_conversation():
    """生成一个真实的长对话，包含多个话题"""
    
    # 话题1：React 开发 (前100条)
    react_messages = [
        {"role": "user", "content": "How do I use useState in React?", "topic": "react"},
        {"role": "assistant", "content": "useState is a Hook that lets you add state to functional components:\n\n```jsx\nconst [count, setCount] = useState(0);\n```", "topic": "react"},
        {"role": "user", "content": "What's the difference between useEffect and useLayoutEffect?", "topic": "react"},
        {"role": "assistant", "content": "useEffect runs after paint, useLayoutEffect runs before paint. Use useLayoutEffect when you need to read layout and synchronously re-render.", "topic": "react"},
        {"role": "user", "content": "How to optimize React performance?", "topic": "react"},
        {"role": "assistant", "content": "Key optimization techniques:\n1. Use React.memo for expensive components\n2. Use useMemo for expensive calculations\n3. Use useCallback for stable function references\n4. Code splitting with React.lazy", "topic": "react"},
        {"role": "user", "content": "Explain React Context API", "topic": "react"},
        {"role": "assistant", "content": "Context provides a way to pass data through the component tree without props drilling:\n\n```jsx\nconst ThemeContext = React.createContext('light');\n```", "topic": "react"},
        {"role": "user", "content": "When should I use useReducer instead of useState?", "topic": "react"},
        {"role": "assistant", "content": "Use useReducer when:\n- State logic is complex with multiple sub-values\n- Next state depends on previous state\n- You want to optimize performance by passing dispatch down", "topic": "react"},
    ]
    
    # 填充更多 React 消息
    for i in range(10, 50):
        react_messages.append({
            "role": "user",
            "content": f"React question {i}: How to handle forms and controlled components in React applications?",
            "topic": "react"
        })
        react_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use controlled components with useState to handle form inputs. Controlled components keep form state in React state.",
            "topic": "react"
        })
    
    # 话题2：Python 数据分析 (中间100条)
    python_messages = [
        {"role": "user", "content": "How to use pandas DataFrame?", "topic": "python"},
        {"role": "assistant", "content": "DataFrame is a 2D data structure:\n\n```python\nimport pandas as pd\ndf = pd.DataFrame({'A': [1,2,3], 'B': [4,5,6]})\n```", "topic": "python"},
        {"role": "user", "content": "How to merge two DataFrames?", "topic": "python"},
        {"role": "assistant", "content": "Use pd.merge():\n\n```python\nmerged = pd.merge(df1, df2, on='key', how='inner')\n```", "topic": "python"},
        {"role": "user", "content": "Explain NumPy broadcasting", "topic": "python"},
        {"role": "assistant", "content": "Broadcasting allows NumPy to work with arrays of different shapes:\n\n```python\na = np.array([1, 2, 3])\nb = 2\nresult = a * b\n```", "topic": "python"},
    ]
    
    # 填充更多 Python 消息
    for i in range(10, 50):
        python_messages.append({
            "role": "user",
            "content": f"Python question {i}: How to use matplotlib for data visualization and plotting?",
            "topic": "python"
        })
        python_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use plt.plot() for line plots, plt.scatter() for scatter plots. Customize with labels and colors.",
            "topic": "python"
        })
    
    # 话题3：Docker 部署 (后100条)
    docker_messages = [
        {"role": "user", "content": "How to write a Dockerfile?", "topic": "docker"},
        {"role": "assistant", "content": "Basic Dockerfile structure:\n\n```dockerfile\nFROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"python\", \"app.py\"]\n```", "topic": "docker"},
        {"role": "user", "content": "What's the difference between CMD and ENTRYPOINT?", "topic": "docker"},
        {"role": "assistant", "content": "CMD provides default arguments that can be overridden. ENTRYPOINT defines the executable that always runs.", "topic": "docker"},
        {"role": "user", "content": "How to use docker-compose?", "topic": "docker"},
        {"role": "assistant", "content": "docker-compose.yml example:\n\n```yaml\nservices:\n  web:\n    build: .\n    ports:\n      - \"8000:8000\"\n```", "topic": "docker"},
    ]
    
    # 填充更多 Docker 消息
    for i in range(10, 50):
        docker_messages.append({
            "role": "user",
            "content": f"Docker question {i}: How to optimize Docker image size for production deployments?",
            "topic": "docker"
        })
        docker_messages.append({
            "role": "assistant",
            "content": f"Answer {i}: Use multi-stage builds and alpine base images to reduce Docker image size significantly.",
            "topic": "docker"
        })
    
    all_messages = react_messages + python_messages + docker_messages
    
    for i, msg in enumerate(all_messages):
        msg["index"] = i
        msg["timestamp"] = 1700000000 + i * 60
    
    return all_messages

def create_test_queries():
    """创建测试查询"""
    return [
        {
            "query": "How can I prevent unnecessary re-renders in React components using memoization?",
            "relevant_topics": ["react"],
            "expected_topic": "react",
            "description": "查询关于 React 性能优化，应该召回早期的 React 消息（索引 0-99）"
        },
        {
            "query": "What's the best way to handle complex state logic in React with multiple actions?",
            "relevant_topics": ["react"],
            "expected_topic": "react",
            "description": "查询关于 React useReducer，应该召回早期的 React 消息"
        },
        {
            "query": "How do I group and aggregate data in pandas DataFrame by multiple columns?",
            "relevant_topics": ["python"],
            "expected_topic": "python",
            "description": "查询关于 pandas，应该召回中间的 Python 消息（索引 100-199）"
        },
        {
            "query": "What are the best practices for reducing Docker image size in production?",
            "relevant_topics": ["docker"],
            "expected_topic": "docker",
            "description": "查询关于 Docker 优化，应该召回后期的 Docker 消息（索引 200-299）"
        },
        {
            "query": "Explain the React hooks lifecycle and when each hook runs during component rendering",
            "relevant_topics": ["react"],
            "expected_topic": "react",
            "description": "查询关于 React hooks，应该召回早期消息"
        }
    ]

def evaluate_recall(recalled: List[Tuple[Dict, float]], expected_topic: str, k: int) -> Dict:
    """评估召回质量"""
    relevant_count = 0
    first_relevant_rank = None
    relevant_scores = []
    
    for rank, (msg, score) in enumerate(recalled[:k], 1):
        if msg.get("topic") == expected_topic:
            relevant_count += 1
            relevant_scores.append(score)
            if first_relevant_rank is None:
                first_relevant_rank = rank
    
    precision = relevant_count / k if k > 0 else 0.0
    mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
    avg_score = np.mean(relevant_scores) if relevant_scores else 0.0
    
    return {
        "relevant_count": relevant_count,
        "precision": precision,
        "mrr": mrr,
        "avg_score": avg_score,
        "first_relevant_rank": first_relevant_rank or "N/A"
    }

def run_recall_test():
    """运行完整的召回质量测试"""
    print("="*80)
    print("粗筛召回质量测试")
    print("="*80)
    print()
    
    print("生成测试对话...")
    messages = generate_realistic_conversation()
    print(f"生成了 {len(messages)} 条消息")
    print(f"  - React 话题: 0-99")
    print(f"  - Python 话题: 100-199")
    print(f"  - Docker 话题: 200-299")
    print()
    
    queries = create_test_queries()
    print(f"创建了 {len(queries)} 个测试查询")
    print()
    
    tester = RecallTester()
    
    k_values = [10, 20, 50]
    
    strategies = {
        "Vector Only": tester.recall_by_vector,
        "Keyword Only": tester.recall_by_keyword,
        "Hybrid (0.6V + 0.4K)": tester.recall_hybrid,
        "Vector + Time Decay": tester.recall_with_time_decay
    }
    
    all_results = {strategy: {k: [] for k in k_values} for strategy in strategies}
    
    for query_idx, test_case in enumerate(queries, 1):
        print("="*80)
        print(f"测试 {query_idx}/{len(queries)}: {test_case['description']}")
        print(f"Query: {test_case['query']}")
        print(f"Expected Topic: {test_case['expected_topic']}")
        print("="*80)
        print()
        
        for strategy_name, strategy_func in strategies.items():
            print(f"\n{'='*80}")
            print(f"策略: {strategy_name}")
            print(f"{'='*80}")
            
            start_time = time.time()
            recalled = strategy_func(test_case['query'], messages, k=max(k_values))
            elapsed = time.time() - start_time
            
            print(f"召回耗时: {elapsed*1000:.2f}ms")
            print()
            
            for k in k_values:
                metrics = evaluate_recall(recalled, test_case['expected_topic'], k)
                all_results[strategy_name][k].append(metrics)
                
                print(f"  K={k}:")
                print(f"    Precision@{k}: {metrics['precision']*100:.1f}% ({metrics['relevant_count']}/{k} 条相关)")
                print(f"    MRR: {metrics['mrr']:.3f}")
                print(f"    First Relevant Rank: {metrics['first_relevant_rank']}")
                print(f"    Avg Score (relevant): {metrics['avg_score']:.4f}")
            
            print(f"\n  Top 5 召回消息:")
            for rank, (msg, score) in enumerate(recalled[:5], 1):
                topic_match = "✓" if msg.get("topic") == test_case['expected_topic'] else "✗"
                content_preview = msg["content"][:60].replace("\n", " ")
                print(f"    {rank}. [{topic_match}] Score={score:.4f} | {content_preview}...")
    
    print("\n\n")
    print("="*80)
    print("汇总统计：所有查询的平均表现")
    print("="*80)
    print()
    
    for k in k_values:
        print(f"\n{'='*80}")
        print(f"K = {k}")
        print(f"{'='*80}")
        print(f"{'策略':<30} {'Precision@K':<15} {'MRR':<10} {'Avg Score'}")
        print("-"*80)
        
        for strategy_name in strategies:
            results = all_results[strategy_name][k]
            avg_precision = np.mean([r['precision'] for r in results])
            avg_mrr = np.mean([r['mrr'] for r in results])
            avg_score = np.mean([r['avg_score'] for r in results])
            
            print(f"{strategy_name:<30} {avg_precision*100:>6.1f}%         {avg_mrr:>6.3f}    {avg_score:>6.4f}")
    
    print("\n\n")
    print("="*80)
    print("最终推荐")
    print("="*80)
    
    k = 50
    best_strategy = None
    best_precision = 0.0
    
    for strategy_name in strategies:
        results = all_results[strategy_name][k]
        avg_precision = np.mean([r['precision'] for r in results])
        if avg_precision > best_precision:
            best_precision = avg_precision
            best_strategy = strategy_name
    
    print(f"\n✅ 最佳策略: {best_strategy}")
    print(f"   Precision@50: {best_precision*100:.1f}%")
    print(f"\n说明：")
    print(f"  - Precision@K 表示召回的前K条中，有多少比例是真正相关的")
    print(f"  - MRR 表示第一个相关结果的排名质量（越高越好，最高1.0）")
    print(f"  - 在300条跨3个话题的消息中，能召回 {best_precision*100:.1f}% 相关消息")

if __name__ == "__main__":
    run_recall_test()
