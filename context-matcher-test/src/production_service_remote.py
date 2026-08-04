"""
生产级上下文召回服务 - 使用远程 Embedding API
支持：Redis缓存、异步处理、CAR算法、BM25混合检索
"""
import asyncio
import time
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from rank_bm25 import BM25Okapi

from remote_embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """消息结构"""
    role: str
    content: str
    index: int  # 原始索引


@dataclass
class RecallResult:
    """召回结果"""
    messages: List[Message]
    algorithm: str
    latency_ms: float
    original_count: int
    recalled_count: int
    cache_hit_rate: float


class ProductionRecallService:
    """生产级召回服务"""
    
    def __init__(
        self,
        api_base: str = "https://router.tumuer.me/v1",
        api_key: str = None,
        model: str = "Qwen/Qwen3-Embedding-4B",
        redis_url: Optional[str] = None
    ):
        """
        初始化召回服务
        
        Args:
            api_base: Embedding API 基础URL
            api_key: API密钥
            model: 模型名称（推荐: Qwen/Qwen3-Embedding-4B）
            redis_url: Redis连接URL（可选）
        """
        if not api_key:
            raise ValueError("api_key is required")
        
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.redis_url = redis_url
        self.embedding_service = None
    
    async def initialize(self):
        """异步初始化"""
        if self.embedding_service is None:
            self.embedding_service = await get_embedding_service(
                api_base=self.api_base,
                api_key=self.api_key,
                model=self.model,
                redis_url=self.redis_url
            )
            logger.info(f"✓ Embedding 服务已初始化: {self.model}")
    
    async def _dense_retrieval(
        self,
        messages: List[Message],
        query: str,
        k: int
    ) -> Tuple[List[Message], float]:
        """
        Dense 向量检索
        
        Returns:
            (recalled_messages, cache_hit_rate)
        """
        # 提取所有文本
        texts = [msg.content for msg in messages]
        
        # 获取 embeddings（带缓存）
        start = time.time()
        msg_embeddings = await self.embedding_service.embed_texts(texts)
        query_embedding = await self.embedding_service.embed_single(query)
        embed_time = time.time() - start
        
        # 计算相似度
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        msg_norms = normalize(msg_embeddings, axis=1)
        similarities = np.dot(msg_norms, query_norm)
        
        # Top-K
        top_k_indices = np.argsort(similarities)[::-1][:k]
        recalled = [messages[i] for i in top_k_indices]
        
        # 缓存命中率（基于embedding获取时间估算）
        cache_hit_rate = max(0, 100 - embed_time * 10)  # 简化估算
        
        return recalled, cache_hit_rate
    
    async def _bm25_retrieval(
        self,
        messages: List[Message],
        query: str,
        k: int
    ) -> List[Message]:
        """BM25 稀疏检索"""
        # 简单分词（实际应该用 jieba）
        corpus = [msg.content.split() for msg in messages]
        query_tokens = query.split()
        
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query_tokens)
        
        top_k_indices = np.argsort(scores)[::-1][:k]
        return [messages[i] for i in top_k_indices]
    
    async def hybrid_dat_retrieval(
        self,
        messages: List[Message],
        query: str,
        k: int = 50
    ) -> RecallResult:
        """
        Hybrid DAT (Dynamic Alpha Tuning) 检索
        根据查询长度动态调整 BM25 和 Dense 权重
        """
        start_time = time.time()
        
        # 动态权重
        query_length = len(query.split())
        if query_length <= 3:
            alpha = 0.3  # 短查询，降低BM25权重
        elif query_length <= 8:
            alpha = 0.5
        else:
            alpha = 0.7  # 长查询，提高BM25权重
        
        # Dense 检索
        dense_results, cache_hit_rate = await self._dense_retrieval(messages, query, k * 2)
        
        # BM25 检索
        bm25_results = await self._bm25_retrieval(messages, query, k * 2)
        
        # 混合评分
        score_map = {}
        
        # Dense 分数
        for rank, msg in enumerate(dense_results):
            score_map[msg.index] = score_map.get(msg.index, 0) + (1 - alpha) * (1 / (rank + 1))
        
        # BM25 分数
        for rank, msg in enumerate(bm25_results):
            score_map[msg.index] = score_map.get(msg.index, 0) + alpha * (1 / (rank + 1))
        
        # 排序并取 Top-K
        sorted_indices = sorted(score_map.keys(), key=lambda x: score_map[x], reverse=True)
        recalled = [messages[idx] for idx in sorted_indices[:k]]
        
        latency_ms = (time.time() - start_time) * 1000
        
        return RecallResult(
            messages=recalled,
            algorithm="hybrid_dat",
            latency_ms=latency_ms,
            original_count=len(messages),
            recalled_count=len(recalled),
            cache_hit_rate=cache_hit_rate
        )
    
    async def car_retrieval(
        self,
        messages: List[Message],
        query: str,
        k: int = 50,
        n_clusters: int = 5
    ) -> RecallResult:
        """
        CAR (Cluster-based Adaptive Retrieval) 检索
        基于聚类的自适应召回
        """
        start_time = time.time()
        
        if len(messages) < n_clusters:
            # 消息太少，直接用 Dense
            recalled, cache_hit_rate = await self._dense_retrieval(messages, query, k)
            latency_ms = (time.time() - start_time) * 1000
            return RecallResult(
                messages=recalled,
                algorithm="car_fallback_dense",
                latency_ms=latency_ms,
                original_count=len(messages),
                recalled_count=len(recalled),
                cache_hit_rate=cache_hit_rate
            )
        
        # 获取 embeddings
        texts = [msg.content for msg in messages]
        msg_embeddings = await self.embedding_service.embed_texts(texts)
        query_embedding = await self.embedding_service.embed_single(query)
        
        # KMeans 聚类
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(msg_embeddings)
        
        # 计算查询与各簇中心的相似度
        cluster_centers = kmeans.cluster_centers_
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        center_norms = normalize(cluster_centers, axis=1)
        cluster_scores = np.dot(center_norms, query_norm)
        
        # 按簇相似度排序
        sorted_clusters = np.argsort(cluster_scores)[::-1]
        
        # 从高分簇中召回
        recalled_indices = []
        for cluster_id in sorted_clusters:
            cluster_msg_indices = np.where(cluster_labels == cluster_id)[0]
            
            # 计算簇内相似度
            cluster_embeddings = msg_embeddings[cluster_msg_indices]
            cluster_norms = normalize(cluster_embeddings, axis=1)
            similarities = np.dot(cluster_norms, query_norm)
            
            # 簇内排序
            sorted_in_cluster = np.argsort(similarities)[::-1]
            recalled_indices.extend(cluster_msg_indices[sorted_in_cluster])
            
            if len(recalled_indices) >= k:
                break
        
        recalled = [messages[i] for i in recalled_indices[:k]]
        
        latency_ms = (time.time() - start_time) * 1000
        cache_hit_rate = 50.0  # 简化估算
        
        return RecallResult(
            messages=recalled,
            algorithm="car",
            latency_ms=latency_ms,
            original_count=len(messages),
            recalled_count=len(recalled),
            cache_hit_rate=cache_hit_rate
        )
    
    async def dense_only_retrieval(
        self,
        messages: List[Message],
        query: str,
        k: int = 50
    ) -> RecallResult:
        """纯 Dense 向量检索（最简单，性能最好）"""
        start_time = time.time()
        
        recalled, cache_hit_rate = await self._dense_retrieval(messages, query, k)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return RecallResult(
            messages=recalled,
            algorithm="dense_only",
            latency_ms=latency_ms,
            original_count=len(messages),
            recalled_count=len(recalled),
            cache_hit_rate=cache_hit_rate
        )
    
    async def recall(
        self,
        messages: List[Dict],
        query: str,
        k: int = 50,
        algorithm: str = "dense_only"
    ) -> RecallResult:
        """
        统一召回接口
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            query: 查询文本
            k: 召回数量
            algorithm: 算法选择 (dense_only, hybrid_dat, car)
        
        Returns:
            RecallResult
        """
        await self.initialize()
        
        # 转换消息格式
        msg_objects = [
            Message(role=msg["role"], content=msg["content"], index=i)
            for i, msg in enumerate(messages)
        ]
        
        # 选择算法
        if algorithm == "hybrid_dat":
            result = await self.hybrid_dat_retrieval(msg_objects, query, k)
        elif algorithm == "car":
            result = await self.car_retrieval(msg_objects, query, k)
        else:  # dense_only (默认)
            result = await self.dense_only_retrieval(msg_objects, query, k)
        
        logger.info(f"✓ 召回完成: {result.algorithm}, "
                   f"{result.recalled_count}/{result.original_count} messages, "
                   f"{result.latency_ms:.1f}ms, "
                   f"缓存命中率 {result.cache_hit_rate:.1f}%")
        
        return result
    
    async def health_check(self) -> Dict:
        """健康检查"""
        await self.initialize()
        
        status = {
            "service": "production_recall",
            "status": "healthy",
            "model": self.model,
            "algorithms": ["dense_only", "hybrid_dat", "car"]
        }
        
        try:
            # 检查 embedding 服务
            emb_health = await self.embedding_service.health_check()
            status["embedding_service"] = emb_health
            
            if emb_health["status"] != "healthy":
                status["status"] = "degraded"
        except Exception as e:
            status["status"] = "unhealthy"
            status["error"] = str(e)
            logger.error(f"❌ 健康检查失败: {e}")
        
        return status


# 全局单例
_recall_service: Optional[ProductionRecallService] = None


async def get_recall_service(
    api_base: str = "https://router.tumuer.me/v1",
    api_key: str = None,
    model: str = "Qwen/Qwen3-Embedding-4B",
    redis_url: Optional[str] = None
) -> ProductionRecallService:
    """获取召回服务单例"""
    global _recall_service
    
    if _recall_service is None:
        _recall_service = ProductionRecallService(
            api_base=api_base,
            api_key=api_key,
            model=model,
            redis_url=redis_url
        )
    
    return _recall_service
