"""
远程 Embedding 服务客户端
使用外部 API 替代本地 sentence-transformers 模型
"""
import asyncio
import hashlib
import json
import time
from typing import List, Dict, Optional
import logging
import httpx
import numpy as np

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class RemoteEmbeddingService:
    """远程 Embedding 服务客户端"""
    
    def __init__(
        self,
        api_base: str = "https://router.tumuer.me/v1",
        api_key: str = None,
        model: str = "Qwen/Qwen3-Embedding-4B",
        redis_url: Optional[str] = None,
        cache_ttl: int = 3600
    ):
        """
        初始化远程 Embedding 服务
        
        Args:
            api_base: API 基础URL
            api_key: API密钥
            model: 模型名称
            redis_url: Redis连接URL（可选）
            cache_ttl: 缓存过期时间（秒）
        """
        if not api_key:
            raise ValueError("api_key is required")
        
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.cache_ttl = cache_ttl
        
        # HTTP客户端
        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=30.0
        )
        
        # Redis缓存
        self.redis_client = None
        self.memory_cache: Dict[str, np.ndarray] = {}
        
        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis_client = aioredis.from_url(redis_url, decode_responses=False)
                logger.info(f"✓ Redis 缓存已启用: {redis_url}")
            except Exception as e:
                logger.warning(f"⚠️  Redis 连接失败，使用内存缓存: {e}")
        else:
            logger.info("✓ 使用内存缓存模式")
    
    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        return f"emb:{self.model}:{hashlib.md5(text.encode()).hexdigest()}"
    
    async def _get_from_cache(self, cache_key: str) -> Optional[np.ndarray]:
        """从缓存获取 embedding"""
        # 尝试 Redis
        if self.redis_client:
            try:
                data = await self.redis_client.get(cache_key)
                if data:
                    return np.frombuffer(data, dtype=np.float32)
            except Exception as e:
                logger.warning(f"Redis 读取失败: {e}")
        
        # 回退到内存缓存
        return self.memory_cache.get(cache_key)
    
    async def _set_to_cache(self, cache_key: str, embedding: np.ndarray):
        """保存 embedding 到缓存"""
        # 保存到 Redis
        if self.redis_client:
            try:
                data = embedding.astype(np.float32).tobytes()
                await self.redis_client.setex(cache_key, self.cache_ttl, data)
            except Exception as e:
                logger.warning(f"Redis 写入失败: {e}")
        
        # 同时保存到内存（限制大小）
        if len(self.memory_cache) < 10000:
            self.memory_cache[cache_key] = embedding
    
    async def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        批量获取文本 embeddings
        
        Args:
            texts: 文本列表
            
        Returns:
            embeddings: (n_texts, dim) 的 numpy 数组
        """
        if not texts:
            return np.array([])
        
        embeddings = []
        texts_to_fetch = []
        fetch_indices = []
        
        # 检查缓存
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = await self._get_from_cache(cache_key)
            
            if cached is not None:
                embeddings.append((i, cached))
            else:
                texts_to_fetch.append(text)
                fetch_indices.append(i)
        
        # 批量调用 API
        if texts_to_fetch:
            start_time = time.time()
            
            try:
                response = await self.client.post(
                    "/embeddings",
                    json={
                        "model": self.model,
                        "input": texts_to_fetch,
                        "encoding_format": "float"
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                # 解析结果
                for idx, item in enumerate(result["data"]):
                    embedding = np.array(item["embedding"], dtype=np.float32)
                    original_idx = fetch_indices[idx]
                    embeddings.append((original_idx, embedding))
                    
                    # 缓存
                    cache_key = self._get_cache_key(texts_to_fetch[idx])
                    await self._set_to_cache(cache_key, embedding)
                
                elapsed = (time.time() - start_time) * 1000
                cache_hit_rate = (len(texts) - len(texts_to_fetch)) / len(texts) * 100
                logger.info(f"✓ Embeddings 获取成功: {len(texts_to_fetch)}/{len(texts)} 请求API, "
                           f"缓存命中率 {cache_hit_rate:.1f}%, 耗时 {elapsed:.1f}ms")
                
            except Exception as e:
                logger.error(f"❌ API 调用失败: {e}")
                raise
        
        # 按原始顺序排序
        embeddings.sort(key=lambda x: x[0])
        return np.array([emb for _, emb in embeddings])
    
    async def embed_single(self, text: str) -> np.ndarray:
        """获取单个文本的 embedding"""
        result = await self.embed_texts([text])
        return result[0] if len(result) > 0 else np.array([])
    
    async def get_embedding_dim(self) -> int:
        """获取 embedding 维度"""
        # 使用一个测试文本获取维度
        test_emb = await self.embed_single("test")
        return len(test_emb)
    
    async def health_check(self) -> Dict[str, any]:
        """健康检查"""
        status = {
            "service": "remote_embedding",
            "status": "healthy",
            "model": self.model,
            "api_base": self.api_base,
            "cache_backend": "redis" if self.redis_client else "memory",
            "memory_cache_size": len(self.memory_cache)
        }
        
        try:
            # 测试 API 连接
            start = time.time()
            await self.embed_single("health check test")
            latency = (time.time() - start) * 1000
            status["api_latency_ms"] = round(latency, 2)
            
            # 测试 Redis 连接
            if self.redis_client:
                await self.redis_client.ping()
                status["redis_status"] = "connected"
            
        except Exception as e:
            status["status"] = "degraded"
            status["error"] = str(e)
            logger.error(f"❌ 健康检查失败: {e}")
        
        return status
    
    async def close(self):
        """关闭连接"""
        await self.client.aclose()
        if self.redis_client:
            await self.redis_client.close()


# 单例模式
_embedding_service: Optional[RemoteEmbeddingService] = None


async def get_embedding_service(
    api_base: str = "https://router.tumuer.me/v1",
    api_key: str = None,
    model: str = "Qwen/Qwen3-Embedding-4B",
    redis_url: Optional[str] = None
) -> RemoteEmbeddingService:
    """获取全局 Embedding 服务单例"""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = RemoteEmbeddingService(
            api_base=api_base,
            api_key=api_key,
            model=model,
            redis_url=redis_url
        )
    
    return _embedding_service


# 测试代码
async def test_remote_embedding():
    """测试远程 Embedding 服务"""
    print("\n=== 测试远程 Embedding 服务 ===\n")
    
    service = await get_embedding_service()
    
    # 1. 测试单个文本
    print("1. 测试单个文本 embedding:")
    text = "这是一个测试句子"
    emb = await service.embed_single(text)
    print(f"   文本: {text}")
    print(f"   维度: {len(emb)}")
    print(f"   前10维: {emb[:10]}")
    
    # 2. 测试批量文本
    print("\n2. 测试批量文本 embedding:")
    texts = [
        "如何优化 React 性能？",
        "pandas DataFrame 聚合操作",
        "Docker 镜像优化技巧"
    ]
    embs = await service.embed_texts(texts)
    print(f"   文本数量: {len(texts)}")
    print(f"   Embeddings shape: {embs.shape}")
    
    # 3. 测试缓存（再次请求相同文本）
    print("\n3. 测试缓存效果:")
    start = time.time()
    embs2 = await service.embed_texts(texts)
    elapsed = (time.time() - start) * 1000
    print(f"   第二次请求耗时: {elapsed:.1f}ms (应该很快，因为有缓存)")
    print(f"   结果一致性: {np.allclose(embs, embs2)}")
    
    # 4. 健康检查
    print("\n4. 健康检查:")
    health = await service.health_check()
    print(f"   {json.dumps(health, indent=2, ensure_ascii=False)}")
    
    await service.close()
    print("\n=== 测试完成 ===\n")


if __name__ == "__main__":
    asyncio.run(test_remote_embedding())
