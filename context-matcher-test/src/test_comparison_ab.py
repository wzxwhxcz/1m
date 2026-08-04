"""
真实对比测试：方案A vs 方案B
测试最终400K模型的回答质量差异
"""
import numpy as np
import time
import json
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import requests


class ComparisonTester:
    """对比测试器：方案A vs 方案B"""
    
    def __init__(self, api_base: str, api_key: str, model: str):
        print("="*80)
        print("初始化对比测试器")
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
    
    def embed(self, text: str) -> np.ndarray:
        """向量化（带缓存）"""
        if text not in self.embeddings_cache:
            self.embeddings_cache[text] = self.embedding_model.encode(text, convert_to_numpy=True)
        return self.embeddings_cache[text]
    
    def build_clusters(self, messages: List[Dict], n_clusters: int = 3):
        """构建聚类索引"""
        embeddings = []
        for msg in messages:
            emb = self.embed(msg["content"])
            embeddings.append(emb)
        
        embeddings = np.array(embeddings)
        embeddings_norm = normalize(embeddings)
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        self.cluster_labels = kmeans.fit_predict(embeddings_norm)
        self.cluster_centroids = kmeans.cluster_centers_
    
    def car_retrieval(self, query: str, messages: List[Dict], k: int = 100) -> List[Dict]:
        """CAR召回"""
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
                results.append((msg, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return [msg for msg, score in results[:k]]
    
    def estimate_tokens(self, text: str) -> int:
        """估算token数量"""
        return len(text) // 4
    
    def call_llm(self, prompt: str, max_tokens: int = 4096) -> Tuple[str, float]:
        """调用LLM"""
        start = time.time()
        
        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": max_tokens
                },
                timeout=60
            )
            
            elapsed = time.time() - start
            
            if response.status_code == 200:
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                return answer, elapsed
            else:
                print(f"❌ API调用失败: {response.status_code}")
                return None, elapsed
                
        except Exception as e:
            elapsed = time.time() - start
            print(f"❌ API调用异常: {e}")
            return None, elapsed
    
    def method_a_traditional_rerank(self, query: str, candidates: List[Dict]) -> str:
        """
        方案A: 传统LLM精排
        50条候选 → LLM选择10条 → 构建上下文
        """
        print(f"\n{'='*80}")
        print("方案A: 传统LLM精排")
        print(f"{'='*80}")
        
        # 限制到前50条
        candidates = candidates[:50]
        
        # 构建精排提示
        candidates_text = "\n\n".join([
            f"[消息{i+1}] {msg['content']}"
            for i, msg in enumerate(candidates)
        ])
        
        rerank_prompt = f"""请从以下50条候选消息中，选择与用户问题最相关的10条消息。

用户问题: {query}

候选消息:
{candidates_text}

请返回JSON格式：
{{
    "selected": [1, 5, 3, ...],  // 选中的消息编号
    "reasoning": "选择理由"
}}"""
        
        print(f"步骤1: LLM精排（从50条选10条）...")
        rerank_result, rerank_time = self.call_llm(rerank_prompt, max_tokens=2048)
        
        if not rerank_result:
            print("❌ 精排失败")
            return None
        
        # 解析结果
        try:
            if "```json" in rerank_result:
                json_start = rerank_result.find("```json") + 7
                json_end = rerank_result.find("```", json_start)
                json_str = rerank_result[json_start:json_end].strip()
            else:
                json_str = rerank_result.strip()
            
            parsed = json.loads(json_str)
            selected_indices = parsed.get("selected", [])
            
            # 构建最终上下文（10条完整消息）
            selected_messages = []
            for idx in selected_indices:
                if 1 <= idx <= len(candidates):
                    selected_messages.append(candidates[idx-1])
            
            context = f"""# 相关历史消息

"""
            for i, msg in enumerate(selected_messages[:10]):
                context += f"[消息{i+1}] {msg['content']}\n\n"
            
            context += f"""---
用户当前问题: {query}
"""
            
            print(f"✓ 精排完成: 选中{len(selected_messages)}条消息")
            print(f"✓ 精排耗时: {rerank_time:.1f}s")
            print(f"✓ 上下文tokens: ~{self.estimate_tokens(context):,}")
            
            return context
            
        except Exception as e:
            print(f"❌ 解析精排结果失败: {e}")
            # 回退：直接取前10条
            print("⚠️  回退策略：直接使用前10条")
            context = f"""# 相关历史消息

"""
            for i, msg in enumerate(candidates[:10]):
                context += f"[消息{i+1}] {msg['content']}\n\n"
            
            context += f"""---
用户当前问题: {query}
"""
            return context
    
    def method_b_layered_context(self, query: str, candidates: List[Dict]) -> str:
        """
        方案B: 分层上下文构建
        100条候选 → 分层构建 → 完整上下文
        """
        print(f"\n{'='*80}")
        print("方案B: 分层上下文构建")
        print(f"{'='*80}")
        
        # Tier 1: 完整保留前30条
        tier1_count = 30
        tier1_messages = candidates[:tier1_count]
        
        print(f"步骤1: Tier 1 - 完整保留前{tier1_count}条核心消息")
        tier1_context = ""
        for i, msg in enumerate(tier1_messages):
            tier1_context += f"[消息{i+1}] {msg['content']}\n\n"
        
        tier1_tokens = self.estimate_tokens(tier1_context)
        print(f"✓ Tier 1完成: {tier1_count}条消息, ~{tier1_tokens:,} tokens")
        
        # Tier 2: 压缩保留31-60条
        tier2_start = tier1_count
        tier2_end = min(tier2_start + 30, len(candidates))
        tier2_messages = candidates[tier2_start:tier2_end]
        
        if tier2_messages:
            print(f"\n步骤2: Tier 2 - 压缩保留第{tier2_start+1}-{tier2_end}条消息")
            
            tier2_text = "\n\n".join([
                f"[消息{i+tier2_start+1}] {msg['content']}"
                for i, msg in enumerate(tier2_messages)
            ])
            
            compress_prompt = f"""请将以下{len(tier2_messages)}条消息压缩成简洁摘要（300字内），保留关键信息：

{tier2_text}

摘要："""
            
            tier2_compressed, compress_time = self.call_llm(compress_prompt, max_tokens=1024)
            
            if tier2_compressed:
                tier2_tokens = self.estimate_tokens(tier2_compressed)
                print(f"✓ Tier 2完成: {len(tier2_messages)}条消息压缩, ~{tier2_tokens:,} tokens")
                print(f"✓ 压缩耗时: {compress_time:.1f}s")
            else:
                tier2_compressed = f"（消息{tier2_start+1}-{tier2_end}讨论了相关话题）"
                tier2_tokens = self.estimate_tokens(tier2_compressed)
                print(f"⚠️  压缩失败，使用占位符")
        else:
            tier2_compressed = ""
            tier2_tokens = 0
        
        # Tier 3: 索引保留61-100条
        tier3_start = tier2_end
        tier3_end = min(tier3_start + 40, len(candidates))
        tier3_messages = candidates[tier3_start:tier3_end]
        
        tier3_context = ""
        if tier3_messages:
            print(f"\n步骤3: Tier 3 - 索引保留第{tier3_start+1}-{tier3_end}条消息")
            for i, msg in enumerate(tier3_messages):
                title = msg["content"][:50].replace('\n', ' ')
                if len(msg["content"]) > 50:
                    title += "..."
                topic = msg.get("topic", "general")
                tier3_context += f"[{i+tier3_start+1}] {title} | #{topic}\n"
            
            tier3_tokens = self.estimate_tokens(tier3_context)
            print(f"✓ Tier 3完成: {len(tier3_messages)}条消息索引, ~{tier3_tokens:,} tokens")
        else:
            tier3_tokens = 0
        
        # 构建最终上下文
        final_context = f"""# 上下文结构

## 🔥 核心相关消息 (完整保留)

{tier1_context}"""
        
        if tier2_compressed:
            final_context += f"""
## 📚 相关背景消息 (压缩保留)

<compressed>
{tier2_compressed}
</compressed>
"""
        
        if tier3_context:
            final_context += f"""
## 📑 扩展参考索引 (可追溯)

{tier3_context}"""
        
        final_context += f"""
---
用户当前问题: {query}
"""
        
        total_tokens = tier1_tokens + tier2_tokens + tier3_tokens
        print(f"\n✓ 分层上下文构建完成")
        print(f"  - Tier 1: {tier1_tokens:,} tokens")
        print(f"  - Tier 2: {tier2_tokens:,} tokens")
        print(f"  - Tier 3: {tier3_tokens:,} tokens")
        print(f"  - 总计: ~{total_tokens:,} tokens")
        
        return final_context
    
    def ask_final_model(self, context: str, query: str, method_name: str) -> Dict:
        """向最终400K模型提问"""
        print(f"\n{'='*80}")
        print(f"{method_name} - 最终模型回答")
        print(f"{'='*80}")
        
        final_prompt = f"""{context}

请基于以上上下文，回答用户问题。

要求：
1. 给出具体的技术建议或代码示例
2. 解释为什么这样做
3. 如果上下文中有相关信息，请引用

用户问题：{query}

回答："""
        
        print(f"调用最终模型...")
        answer, elapsed = self.call_llm(final_prompt, max_tokens=4096)
        
        if answer:
            print(f"✓ 模型回答完成")
            print(f"✓ 耗时: {elapsed:.1f}s")
            print(f"✓ 回答长度: {len(answer)} 字符")
            
            return {
                "answer": answer,
                "time": elapsed,
                "context_tokens": self.estimate_tokens(context),
                "answer_length": len(answer)
            }
        else:
            print(f"❌ 模型回答失败")
            return None
    
    def generate_realistic_test_data(self):
        """生成真实场景的测试数据"""
        print("\n生成真实测试数据...")
        
        messages = []
        
        # 场景：一个正在开发React应用的开发者，历史对话涉及多个技术栈
        
        # React开发（60条，主要话题）
        react_conversations = [
            "I'm building a dashboard with React. How do I set up the initial project structure?",
            "What's the best way to manage state in a React app? Should I use Context or Redux?",
            "I need to fetch data from an API. Should I use useEffect or a library like React Query?",
            "How do I prevent unnecessary re-renders in my React components?",
            "I'm seeing performance issues when rendering a large list. What are my options?",
            "Can you explain the difference between useMemo and useCallback?",
            "I want to optimize my React app. Where should I start?",
            "What's React.memo and when should I use it?",
            "How do I profile my React app to find performance bottlenecks?",
            "Should I use React.lazy for code splitting?",
            "I'm getting warnings about missing dependencies in useEffect. What does that mean?",
            "How do I handle form validation in React?",
            "What's the best way to manage routing in a React app?",
            "I need to implement authentication. Any recommendations?",
            "How do I test React components?",
        ]
        
        for i, conv in enumerate(react_conversations):
            messages.append({
                "role": "user",
                "content": f"{conv} (Context: Building a real-time analytics dashboard, scenario {i})",
                "topic": "react",
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # Python数据处理（25条，次要话题）
        python_conversations = [
            "I have a CSV file with user data. How do I load it with pandas?",
            "How do I group and aggregate data in a pandas DataFrame?",
            "What's the best way to handle missing values in my dataset?",
            "I need to merge two DataFrames. What's the difference between merge and join?",
            "How do I calculate running averages in pandas?",
        ]
        
        for i, conv in enumerate(python_conversations):
            messages.append({
                "role": "user",
                "content": f"{conv} (Context: Processing user analytics data, scenario {i})",
                "topic": "python",
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        # Docker部署（15条，边缘话题）
        docker_conversations = [
            "How do I create a Dockerfile for my React app?",
            "What's the best base image for a Node.js application?",
            "How do I reduce my Docker image size?",
        ]
        
        for i, conv in enumerate(docker_conversations):
            messages.append({
                "role": "user",
                "content": f"{conv} (Context: Deploying to production, scenario {i})",
                "topic": "docker",
                "timestamp": f"2026-08-{(i % 30) + 1:02d}"
            })
        
        print(f"✓ 生成 {len(messages)} 条真实对话消息")
        print(f"  - React: {sum(1 for m in messages if m['topic'] == 'react')}条")
        print(f"  - Python: {sum(1 for m in messages if m['topic'] == 'python')}条")
        print(f"  - Docker: {sum(1 for m in messages if m['topic'] == 'docker')}条")
        
        return messages
    
    def run_comparison(self):
        """运行完整对比测试"""
        print(f"\n{'#'*80}")
        print("真实场景对比测试：方案A vs 方案B")
        print(f"{'#'*80}")
        
        # 生成测试数据
        messages = self.generate_realistic_test_data()
        
        # 构建聚类
        print(f"\n构建聚类索引...")
        self.build_clusters(messages, n_clusters=3)
        print(f"✓ 聚类完成")
        
        # 设计真实测试问题
        test_query = "My React dashboard is slow when rendering the user table with 1000+ rows. How can I optimize the rendering performance? Please give me specific code examples."
        
        print(f"\n{'='*80}")
        print(f"测试问题: {test_query}")
        print(f"{'='*80}")
        
        # CAR召回
        print(f"\nCAR召回相关消息...")
        candidates = self.car_retrieval(test_query, messages, k=100)
        print(f"✓ 召回 {len(candidates)} 条候选消息")
        
        # 方案A测试
        context_a = self.method_a_traditional_rerank(test_query, candidates)
        if context_a:
            result_a = self.ask_final_model(context_a, test_query, "方案A")
        else:
            result_a = None
        
        # 方案B测试
        context_b = self.method_b_layered_context(test_query, candidates)
        if context_b:
            result_b = self.ask_final_model(context_b, test_query, "方案B")
        else:
            result_b = None
        
        # 对比分析
        self._print_comparison(test_query, result_a, result_b, context_a, context_b)
        
        return {
            "query": test_query,
            "result_a": result_a,
            "result_b": result_b,
            "context_a": context_a,
            "context_b": context_b
        }
    
    def _print_comparison(self, query: str, result_a: Dict, result_b: Dict, 
                         context_a: str, context_b: str):
        """打印对比分析"""
        print(f"\n{'#'*80}")
        print("对比分析")
        print(f"{'#'*80}")
        
        print(f"\n## 上下文对比\n")
        print(f"{'指标':<20} {'方案A（传统精排）':<25} {'方案B（分层上下文）':<25}")
        print("-" * 80)
        
        if result_a and result_b:
            print(f"{'上下文tokens':<20} {result_a['context_tokens']:>20,}    {result_b['context_tokens']:>20,}")
            print(f"{'回答长度':<20} {result_a['answer_length']:>20}    {result_b['answer_length']:>20}")
            print(f"{'回答耗时':<20} {result_a['time']:>19.1f}s    {result_b['time']:>19.1f}s")
        
        # 打印回答内容（前500字符）
        if result_a:
            print(f"\n## 方案A回答（前500字符）:\n")
            print(result_a['answer'][:500] + "..." if len(result_a['answer']) > 500 else result_a['answer'])
        
        if result_b:
            print(f"\n## 方案B回答（前500字符）:\n")
            print(result_b['answer'][:500] + "..." if len(result_b['answer']) > 500 else result_b['answer'])
        
        # 保存完整结果
        output_file = "D:/1m/context-matcher-test/reports/comparison_test_result.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "query": query,
                "context_a": context_a,
                "context_b": context_b,
                "result_a": result_a,
                "result_b": result_b
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\n✓ 完整结果已保存到: {output_file}")


if __name__ == "__main__":
    # API配置
    API_BASE = "http://154.201.79.82:8080/v1"
    API_KEY = "sk-asdfghjkl123456"
    MODEL = "Gemini 3 Flash Preview"
    
    # 运行对比测试
    tester = ComparisonTester(API_BASE, API_KEY, MODEL)
    results = tester.run_comparison()
