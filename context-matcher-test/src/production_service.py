"""
生产级上下文压缩服务
包含：Redis缓存、异步处理、监控告警、健康检查
"""
import asyncio
import json
import time
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
import logging
from enum import Enum

# 模拟Redis（生产环境需要安装 redis-py）
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️  redis-py未安装，使用内存缓存模式")


class CacheBackend(Enum):
    """缓存后端类型"""
    MEMORY = "memory"
    REDIS = "redis"


@dataclass
class PerformanceMetrics:
    """性能指标"""
    timestamp: float
    operation: str
    latency_ms: float
    cache_hit: bool
    error: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class HealthStatus:
    """健康状态"""
    status: str  # healthy, degraded, unhealthy
    uptime_seconds: float
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    cache_hit_rate: float
    last_error: Optional[str] = None
    
    def to_dict(self):
        return asdict(self)


class InMemoryCache:
    """内存缓存（用于开发/测试）"""
    
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.ttl = ttl
    
    async def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        if key in self.cache:
            value, expire_time = self.cache[key]
            if time.time() < expire_time:
                return value
            else:
                del self.cache[key]
        return None
    
    async def set(self, key: str, value: str, ex: int = None) -> bool:
        """设置缓存"""
        ttl = ex if ex else self.ttl
        self.cache[key] = (value, time.time() + ttl)
        return True
    
    async def exists(self, key: str) -> bool:
        """检查key是否存在"""
        result = await self.get(key)
        return result is not None
    
    async def delete(self, key: str) -> bool:
        """删除key"""
        if key in self.cache:
            del self.cache[key]
            return True
        return False
    
    def get_stats(self) -> Dict:
        """获取缓存统计"""
        active_keys = 0
        for key, (value, expire_time) in self.cache.items():
            if time.time() < expire_time:
                active_keys += 1
        
        return {
            "backend": "memory",
            "total_keys": len(self.cache),
            "active_keys": active_keys,
            "memory_usage_mb": 0  # 简化实现
        }


class RedisCache:
    """Redis缓存（生产环境）"""
    
    def __init__(self, host: str = "localhost", port: int = 6379, 
                 db: int = 0, ttl: int = 3600):
        self.host = host
        self.port = port
        self.db = db
        self.ttl = ttl
        self.redis = None
    
    async def connect(self):
        """连接Redis"""
        if not REDIS_AVAILABLE:
            raise RuntimeError("redis-py未安装，无法使用Redis缓存")
        
        self.redis = await aioredis.from_url(
            f"redis://{self.host}:{self.port}/{self.db}",
            encoding="utf-8",
            decode_responses=True
        )
    
    async def get(self, key: str) -> Optional[str]:
        """获取缓存"""
        return await self.redis.get(key)
    
    async def set(self, key: str, value: str, ex: int = None) -> bool:
        """设置缓存"""
        ttl = ex if ex else self.ttl
        return await self.redis.set(key, value, ex=ttl)
    
    async def exists(self, key: str) -> bool:
        """检查key是否存在"""
        return await self.redis.exists(key) > 0
    
    async def delete(self, key: str) -> bool:
        """删除key"""
        return await self.redis.delete(key) > 0
    
    async def get_stats(self) -> Dict:
        """获取Redis统计"""
        info = await self.redis.info()
        return {
            "backend": "redis",
            "total_keys": info.get("db0", {}).get("keys", 0),
            "memory_usage_mb": info.get("used_memory", 0) / 1024 / 1024,
            "connected_clients": info.get("connected_clients", 0)
        }
    
    async def close(self):
        """关闭连接"""
        if self.redis:
            await self.redis.close()


class MonitoringCollector:
    """监控指标收集器"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: List[PerformanceMetrics] = []
        self.max_metrics = max_metrics
        self.start_time = time.time()
        self.total_requests = 0
        self.total_errors = 0
        self.cache_hits = 0
        self.cache_misses = 0
    
    def record(self, metric: PerformanceMetrics):
        """记录指标"""
        self.metrics.append(metric)
        self.total_requests += 1
        
        if metric.error:
            self.total_errors += 1
        
        if metric.cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1
        
        # 限制内存使用
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics:]
    
    def get_health_status(self) -> HealthStatus:
        """获取健康状态"""
        uptime = time.time() - self.start_time
        error_rate = self.total_errors / self.total_requests if self.total_requests > 0 else 0
        
        recent_metrics = self.metrics[-100:] if len(self.metrics) > 0 else []
        avg_latency = np.mean([m.latency_ms for m in recent_metrics]) if recent_metrics else 0
        
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / cache_total if cache_total > 0 else 0
        
        last_error = None
        for m in reversed(self.metrics):
            if m.error:
                last_error = m.error
                break
        
        # 判断健康状态
        if error_rate > 0.1:
            status = "unhealthy"
        elif error_rate > 0.05 or avg_latency > 500:
            status = "degraded"
        else:
            status = "healthy"
        
        return HealthStatus(
            status=status,
            uptime_seconds=uptime,
            total_requests=self.total_requests,
            error_rate=error_rate,
            avg_latency_ms=avg_latency,
            cache_hit_rate=cache_hit_rate,
            last_error=last_error
        )
    
    def get_statistics(self, window_seconds: int = 60) -> Dict:
        """获取统计数据"""
        now = time.time()
        window_metrics = [m for m in self.metrics if now - m.timestamp <= window_seconds]
        
        if not window_metrics:
            return {
                "window_seconds": window_seconds,
                "request_count": 0,
                "avg_latency_ms": 0,
                "p95_latency_ms": 0,
                "p99_latency_ms": 0,
                "error_count": 0,
                "cache_hit_rate": 0
            }
        
        latencies = [m.latency_ms for m in window_metrics]
        errors = [m for m in window_metrics if m.error]
        cache_hits = [m for m in window_metrics if m.cache_hit]
        
        return {
            "window_seconds": window_seconds,
            "request_count": len(window_metrics),
            "avg_latency_ms": np.mean(latencies),
            "p95_latency_ms": np.percentile(latencies, 95),
            "p99_latency_ms": np.percentile(latencies, 99),
            "error_count": len(errors),
            "cache_hit_rate": len(cache_hits) / len(window_metrics) if window_metrics else 0
        }


class ProductionContextService:
    """生产级上下文压缩服务"""
    
    def __init__(self, 
                 cache_backend: CacheBackend = CacheBackend.MEMORY,
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 cache_ttl: int = 3600,
                 enable_monitoring: bool = True):
        
        # 配置
        self.cache_backend = cache_backend
        self.cache_ttl = cache_ttl
        self.enable_monitoring = enable_monitoring
        
        # 初始化缓存
        if cache_backend == CacheBackend.REDIS:
            self.cache = RedisCache(redis_host, redis_port, ttl=cache_ttl)
        else:
            self.cache = InMemoryCache(ttl=cache_ttl)
        
        # 监控
        self.monitor = MonitoringCollector() if enable_monitoring else None
        
        # CAR组件
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.cluster_labels = None
        self.cluster_centroids = None
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
        print("="*80)
        print("生产级上下文压缩服务已启动")
        print("="*80)
        print(f"✓ 缓存后端: {cache_backend.value}")
        print(f"✓ 缓存TTL: {cache_ttl}秒")
        print(f"✓ 监控: {'启用' if enable_monitoring else '禁用'}")
        print()
    
    async def initialize(self):
        """初始化服务（异步）"""
        if isinstance(self.cache, RedisCache):
            await self.cache.connect()
            print("✓ Redis连接成功")
    
    def _compute_cache_key(self, text: str, prefix: str = "emb") -> str:
        """计算缓存key"""
        hash_value = hashlib.md5(text.encode()).hexdigest()
        return f"{prefix}:{hash_value}"
    
    async def embed_cached(self, text: str) -> np.ndarray:
        """带缓存的向量化"""
        start = time.time()
        cache_key = self._compute_cache_key(text)
        
        # 尝试从缓存获取
        cached = await self.cache.get(cache_key)
        if cached:
            embedding = np.array(json.loads(cached))
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="embed_cached",
                    latency_ms=latency,
                    cache_hit=True
                ))
            
            return embedding
        
        # 缓存未命中，计算embedding
        try:
            embedding = self.embedding_model.encode(text, convert_to_numpy=True)
            
            # 保存到缓存
            await self.cache.set(cache_key, json.dumps(embedding.tolist()), ex=self.cache_ttl)
            
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="embed_cached",
                    latency_ms=latency,
                    cache_hit=False
                ))
            
            return embedding
        
        except Exception as e:
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="embed_cached",
                    latency_ms=latency,
                    cache_hit=False,
                    error=str(e)
                ))
            
            raise
    
    async def build_clusters_async(self, messages: List[Dict], n_clusters: int = 10):
        """异步构建聚类索引"""
        start = time.time()
        
        try:
            print(f"构建聚类索引 (n_clusters={n_clusters})...")
            
            # 并发获取embeddings
            tasks = [self.embed_cached(msg["content"]) for msg in messages]
            embeddings = await asyncio.gather(*tasks)
            
            embeddings = np.array(embeddings)
            embeddings_norm = normalize(embeddings)
            
            # K-Means聚类（CPU密集型，使用线程池）
            loop = asyncio.get_event_loop()
            kmeans = await loop.run_in_executor(
                None,
                lambda: KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit(embeddings_norm)
            )
            
            self.cluster_labels = kmeans.labels_
            self.cluster_centroids = kmeans.cluster_centers_
            
            latency = (time.time() - start) * 1000
            print(f"✓ 聚类完成: {n_clusters}个簇, 耗时 {latency:.1f}ms")
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="build_clusters",
                    latency_ms=latency,
                    cache_hit=False
                ))
        
        except Exception as e:
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="build_clusters",
                    latency_ms=latency,
                    cache_hit=False,
                    error=str(e)
                ))
            
            raise
    
    async def car_retrieval_async(self, query: str, messages: List[Dict], k: int = 100) -> Tuple[List[Tuple], float]:
        """异步CAR召回"""
        start = time.time()
        
        try:
            # 获取query embedding
            query_emb = await self.embed_cached(query)
            query_emb_norm = normalize(query_emb.reshape(1, -1))[0]
            
            # 计算簇得分
            cluster_scores = np.dot(self.cluster_centroids, query_emb_norm)
            top_clusters = np.argsort(cluster_scores)[::-1]
            
            # 并发获取所有消息的embeddings
            tasks = [self.embed_cached(msg["content"]) for msg in messages]
            message_embeddings = await asyncio.gather(*tasks)
            
            # 计算相似度
            results = []
            for cluster_id in top_clusters:
                cluster_mask = self.cluster_labels == cluster_id
                cluster_indices = np.where(cluster_mask)[0]
                
                for idx in cluster_indices:
                    msg = messages[idx]
                    msg_emb_norm = normalize(message_embeddings[idx].reshape(1, -1))[0]
                    similarity = float(np.dot(query_emb_norm, msg_emb_norm))
                    results.append((msg, similarity, idx))
            
            results.sort(key=lambda x: x[1], reverse=True)
            
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="car_retrieval",
                    latency_ms=latency,
                    cache_hit=False  # 整体操作不算cache_hit
                ))
            
            return results[:k], latency
        
        except Exception as e:
            latency = (time.time() - start) * 1000
            
            if self.monitor:
                self.monitor.record(PerformanceMetrics(
                    timestamp=time.time(),
                    operation="car_retrieval",
                    latency_ms=latency,
                    cache_hit=False,
                    error=str(e)
                ))
            
            raise
    
    def get_health(self) -> Dict:
        """获取健康状态"""
        if not self.monitor:
            return {"status": "unknown", "monitoring": "disabled"}
        
        health = self.monitor.get_health_status()
        return health.to_dict()
    
    def get_metrics(self, window_seconds: int = 60) -> Dict:
        """获取监控指标"""
        if not self.monitor:
            return {"monitoring": "disabled"}
        
        return self.monitor.get_statistics(window_seconds)
    
    async def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        if isinstance(self.cache, RedisCache):
            return await self.cache.get_stats()
        else:
            return self.cache.get_stats()
    
    async def shutdown(self):
        """关闭服务"""
        print("\n关闭服务...")
        
        if isinstance(self.cache, RedisCache):
            await self.cache.close()
            print("✓ Redis连接已关闭")
        
        if self.monitor:
            health = self.monitor.get_health_status()
            print(f"✓ 总请求数: {health.total_requests}")
            print(f"✓ 错误率: {health.error_rate*100:.2f}%")
            print(f"✓ 缓存命中率: {health.cache_hit_rate*100:.2f}%")
        
        print("✓ 服务已关闭")


# 使用示例
async def main():
    """示例：如何使用生产级服务"""
    
    # 初始化服务
    service = ProductionContextService(
        cache_backend=CacheBackend.MEMORY,  # 生产环境使用 CacheBackend.REDIS
        cache_ttl=3600,
        enable_monitoring=True
    )
    
    await service.initialize()
    
    # 模拟数据
    messages = [
        {"content": f"React message {i}", "topic": "react"} for i in range(100)
    ] + [
        {"content": f"Python message {i}", "topic": "python"} for i in range(100)
    ]
    
    # 构建聚类
    await service.build_clusters_async(messages, n_clusters=5)
    
    # 执行多次查询（测试缓存）
    for i in range(5):
        query = "How to use React hooks?"
        results, latency = await service.car_retrieval_async(query, messages, k=50)
        print(f"查询 {i+1}: 召回 {len(results)} 条, 耗时 {latency:.1f}ms")
    
    # 获取健康状态
    health = service.get_health()
    print(f"\n健康状态: {json.dumps(health, indent=2)}")
    
    # 获取监控指标
    metrics = service.get_metrics(window_seconds=60)
    print(f"\n监控指标: {json.dumps(metrics, indent=2)}")
    
    # 获取缓存统计
    cache_stats = await service.get_cache_stats()
    print(f"\n缓存统计: {json.dumps(cache_stats, indent=2)}")
    
    # 关闭服务
    await service.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
