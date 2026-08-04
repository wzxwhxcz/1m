"""
分层上下文构建器 - 原文优先策略
避免信息丢失，最大化上下文利用率
"""
import numpy as np
import time
import json
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import requests


class LayeredContextBuilder:
    """分层上下文构建器"""
    
    def __init__(self, api_base: str = None, api_key: str = None, model: str = None):
        print("初始化分层上下文构建器...")
        
        # CAR组件
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.embeddings_cache = {}
        self.cluster_labels = None
        self.cluster_centroids = None
        
        # LLM API配置（可选，用于压缩Tier 2）
        self.api_base = api_base.rstrip('/') if api_base else None
        self.api_key = api_key
        self.model = model
        
        print("✓ 初始化完成")
    
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
    
    def car_retrieval(self, query: str, messages: List[Dict], k: int = 100) -> Tuple[List[Dict], List[float]]:
        """CAR召回，返回消息和相关性分数"""
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
                results.append((msg, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        top_messages = [msg for msg, score in results[:k]]
        top_scores = [score for msg, score in results[:k]]
        
        elapsed = (time.time() - start) * 1000
        print(f"✓ CAR召回完成: Top-{k}, 耗时 {elapsed:.1f}ms")
        
        return top_messages, top_scores
    
    def estimate_tokens(self, text: str) -> int:
        """估算token数量（简单估算：1 token ≈ 4 字符）"""
        return len(text) // 4
    
    def compress_tier2(self, messages: List[Dict]) -> str:
        """压缩Tier 2消息（可选使用LLM）"""
        if not self.api_base:
            # 简单压缩：提取摘要
            summaries = []
            for i, msg in enumerate(messages):
                content = msg["content"]
                # 取前100字符作为摘要
                summary = content[:100] + "..." if len(content) > 100 else content
                summaries.append(f"[{i+1}] {summary}")
            return "\n".join(summaries)
        
        # 使用LLM压缩
        print(f"  使用LLM压缩Tier 2 ({len(messages)}条消息)...")
        
        messages_text = "\n\n".join([
            f"[消息{i+1}] {msg['content']}"
            for i, msg in enumerate(messages)
        ])
        
        prompt = f"""请将以下{len(messages)}条历史消息压缩成简洁的摘要，保留关键信息：

{messages_text}

要求：
1. 按主题分组总结
2. 保留重要的技术细节和代码片段
3. 控制在300字以内

摘要："""
        
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
                    "temperature": 0.3,
                    "max_tokens": 2000
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                compressed = result["choices"][0]["message"]["content"]
                print(f"  ✓ LLM压缩完成")
                return compressed
            else:
                print(f"  ⚠️ LLM压缩失败，使用简单压缩")
                return self.compress_tier2(messages)  # 回退到简单压缩
                
        except Exception as e:
            print(f"  ⚠️ LLM调用异常: {e}，使用简单压缩")
            # 回退到简单压缩
            summaries = []
            for i, msg in enumerate(messages):
                content = msg["content"]
                summary = content[:100] + "..." if len(content) > 100 else content
                summaries.append(f"[{i+1}] {summary}")
            return "\n".join(summaries)
    
    def create_index(self, messages: List[Dict]) -> List[Dict]:
        """创建Tier 3索引"""
        index = []
        for i, msg in enumerate(messages):
            # 提取标题（前50字符）
            title = msg["content"][:50].replace('\n', ' ')
            if len(msg["content"]) > 50:
                title += "..."
            
            # 提取话题标签
            topic = msg.get("topic", "general")
            
            index.append({
                "id": i + 1,
                "title": title,
                "topic": topic
            })
        
        return index
    
    def build_context(self, query: str, messages: List[Dict], budget: int = 350000) -> Dict:
        """
        构建分层上下文
        
        Args:
            query: 用户查询
            messages: 历史消息
            budget: Token预算（默认350K，留50K给查询和响应）
        
        Returns:
            分层上下文字典
        """
        print(f"\n{'='*80}")
        print(f"构建分层上下文")
        print(f"{'='*80}")
        print(f"查询: {query}")
        print(f"历史消息总数: {len(messages)}")
        print(f"Token预算: {budget:,}")
        
        # 1. CAR召回 Top-100
        print(f"\n【第一步】CAR召回...")
        candidates, scores = self.car_retrieval(query, messages, k=100)
        
        # 2. 分配预算
        tier1_budget = int(budget * 0.50)  # 50% 给Tier 1
        tier2_budget = int(budget * 0.30)  # 30% 给Tier 2
        tier3_budget = int(budget * 0.10)  # 10% 给Tier 3
        summary_budget = int(budget * 0.10)  # 10% 给全局摘要
        
        context = {
            "query": query,
            "tier1_full": [],
            "tier2_compressed": "",
            "tier3_index": [],
            "global_summary": "",
            "stats": {}
        }
        
        # 3. Tier 1: 完整保留最相关的消息
        print(f"\n【第二步】Tier 1 - 完整保留核心消息...")
        print(f"  预算: {tier1_budget:,} tokens")
        
        tier1_messages = []
        tier1_tokens = 0
        
        for msg in candidates:
            msg_tokens = self.estimate_tokens(msg["content"])
            if tier1_tokens + msg_tokens <= tier1_budget:
                tier1_messages.append(msg)
                tier1_tokens += msg_tokens
            else:
                break
        
        context["tier1_full"] = tier1_messages
        print(f"  ✓ 保留 {len(tier1_messages)} 条完整消息")
        print(f"  ✓ 使用 {tier1_tokens:,} tokens")
        
        # 4. Tier 2: 压缩保留中等相关消息
        print(f"\n【第三步】Tier 2 - 压缩保留相关背景...")
        print(f"  预算: {tier2_budget:,} tokens")
        
        tier2_start = len(tier1_messages)
        tier2_end = min(tier2_start + 30, len(candidates))
        tier2_messages = candidates[tier2_start:tier2_end]
        
        if tier2_messages:
            compressed = self.compress_tier2(tier2_messages)
            tier2_tokens = self.estimate_tokens(compressed)
            context["tier2_compressed"] = compressed
            print(f"  ✓ 压缩 {len(tier2_messages)} 条消息")
            print(f"  ✓ 使用 {tier2_tokens:,} tokens")
        else:
            tier2_tokens = 0
            print(f"  ✓ 无需Tier 2消息")
        
        # 5. Tier 3: 索引保留扩展参考
        print(f"\n【第四步】Tier 3 - 索引保留扩展参考...")
        print(f"  预算: {tier3_budget:,} tokens")
        
        tier3_start = tier2_end
        tier3_end = min(tier3_start + 30, len(candidates))
        tier3_messages = candidates[tier3_start:tier3_end]
        
        if tier3_messages:
            index = self.create_index(tier3_messages)
            context["tier3_index"] = index
            tier3_tokens = self.estimate_tokens(str(index))
            print(f"  ✓ 索引 {len(tier3_messages)} 条消息")
            print(f"  ✓ 使用 {tier3_tokens:,} tokens")
        else:
            tier3_tokens = 0
            print(f"  ✓ 无需Tier 3索引")
        
        # 6. 全局摘要
        print(f"\n【第五步】全局摘要...")
        print(f"  预算: {summary_budget:,} tokens")
        
        # 统计话题分布
        topic_counts = {}
        for msg in messages:
            topic = msg.get("topic", "unknown")
            topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        summary = f"""用户在过去的对话中涉及{len(topic_counts)}个主要话题：
"""
        for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = count / len(messages) * 100
            summary += f"- {topic}: {count}条消息 ({percentage:.1f}%)\n"
        
        summary += f"\n当前查询最相关的话题是: {candidates[0].get('topic', 'unknown')}"
        
        context["global_summary"] = summary
        summary_tokens = self.estimate_tokens(summary)
        print(f"  ✓ 生成全局摘要")
        print(f"  ✓ 使用 {summary_tokens:,} tokens")
        
        # 7. 统计信息
        total_tokens = tier1_tokens + tier2_tokens + tier3_tokens + summary_tokens
        context["stats"] = {
            "total_messages": len(messages),
            "retrieved_messages": len(candidates),
            "tier1_count": len(tier1_messages),
            "tier1_tokens": tier1_tokens,
            "tier2_count": len(tier2_messages),
            "tier2_tokens": tier2_tokens,
            "tier3_count": len(tier3_messages),
            "tier3_tokens": tier3_tokens,
            "summary_tokens": summary_tokens,
            "total_tokens": total_tokens,
            "budget": budget,
            "utilization": f"{total_tokens/budget*100:.1f}%"
        }
        
        print(f"\n{'='*80}")
        print(f"上下文构建完成")
        print(f"{'='*80}")
        print(f"Tier 1 (完整): {len(tier1_messages)}条消息, {tier1_tokens:,} tokens")
        print(f"Tier 2 (压缩): {len(tier2_messages)}条消息, {tier2_tokens:,} tokens")
        print(f"Tier 3 (索引): {len(tier3_messages)}条消息, {tier3_tokens:,} tokens")
        print(f"全局摘要: {summary_tokens:,} tokens")
        print(f"总计: {total_tokens:,} tokens / {budget:,} ({context['stats']['utilization']})")
        
        return context
    
    def format_for_llm(self, context: Dict) -> str:
        """格式化为最终LLM的输入"""
        output = f"""# 上下文结构

## 🔥 核心相关消息 (完整保留)
"""
        
        for i, msg in enumerate(context["tier1_full"]):
            output += f"\n[消息{i+1}] {msg['content']}\n"
        
        if context["tier2_compressed"]:
            output += f"""
## 📚 相关背景消息 (压缩保留)
<compressed>
{context["tier2_compressed"]}
</compressed>
"""
        
        if context["tier3_index"]:
            output += f"""
## 📑 扩展参考索引 (可追溯)
"""
            for item in context["tier3_index"]:
                output += f"[{item['id']}] {item['title']} | #{item['topic']}\n"
        
        output += f"""
## 🌍 全局对话摘要
{context["global_summary"]}

---
用户当前问题: {context["query"]}
"""
        
        return output


# 测试代码
if __name__ == "__main__":
    # 生成测试数据
    def generate_test_data():
        messages = []
        
        react_topics = [
            "How to use useState hook in React?",
            "useEffect cleanup function best practices",
            "React component lifecycle methods",
            "Preventing unnecessary re-renders with React.memo",
            "Understanding useCallback and useMemo",
        ]
        
        python_topics = [
            "pandas DataFrame operations",
            "numpy array manipulation",
            "matplotlib plotting examples",
        ]
        
        for i in range(50):
            messages.append({
                "role": "user",
                "content": react_topics[i % len(react_topics)] + f" Example scenario {i}.",
                "topic": "react"
            })
        
        for i in range(30):
            messages.append({
                "role": "user",
                "content": python_topics[i % len(python_topics)] + f" Use case {i}.",
                "topic": "python"
            })
        
        return messages
    
    # 初始化
    builder = LayeredContextBuilder()
    messages = generate_test_data()
    
    # 构建聚类
    builder.build_clusters(messages, n_clusters=2)
    
    # 构建分层上下文
    query = "How can I optimize React rendering performance?"
    context = builder.build_context(query, messages, budget=300000)
    
    # 格式化输出
    formatted = builder.format_for_llm(context)
    
    print(f"\n{'='*80}")
    print("最终格式化输出（前500字符）")
    print(f"{'='*80}")
    print(formatted[:500] + "...")
    
    # 保存结果
    output_file = "D:/1m/context-matcher-test/reports/layered_context_example.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(formatted)
    
    print(f"\n✓ 完整输出已保存到: {output_file}")
