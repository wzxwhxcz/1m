"""
FastAPI生产服务器
提供REST API接口，支持健康检查、监控指标、上下文压缩
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import asyncio
import uvicorn
from src.production_service import (
    ProductionContextService, 
    CacheBackend,
    HealthStatus,
    PerformanceMetrics
)

# FastAPI应用
app = FastAPI(
    title="1M→400K Context Compression API",
    description="生产级上下文压缩服务，支持CAR算法、Redis缓存、监控告警",
    version="1.0.0"
)

# 全局服务实例
service: Optional[ProductionContextService] = None
message_store: Dict[str, List[Dict]] = {}  # 简化的消息存储


# ============ Pydantic模型 ============

class Message(BaseModel):
    """消息模型"""
    content: str = Field(..., description="消息内容")
    role: str = Field(default="user", description="角色: user/assistant")
    topic: Optional[str] = Field(None, description="话题标签")
    timestamp: Optional[str] = Field(None, description="时间戳")


class BuildClusterRequest(BaseModel):
    """构建聚类请求"""
    session_id: str = Field(..., description="会话ID")
    messages: List[Message] = Field(..., description="消息列表")
    n_clusters: int = Field(default=10, ge=2, le=50, description="聚类数量")


class RetrievalRequest(BaseModel):
    """召回请求"""
    session_id: str = Field(..., description="会话ID")
    query: str = Field(..., description="查询文本")
    k: int = Field(default=100, ge=1, le=500, description="召回数量")


class RetrievalResponse(BaseModel):
    """召回响应"""
    session_id: str
    query: str
    results: List[Dict]
    latency_ms: float
    cache_hit_rate: float


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    uptime_seconds: float
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    cache_hit_rate: float
    last_error: Optional[str]


class MetricsResponse(BaseModel):
    """监控指标响应"""
    window_seconds: int
    request_count: int
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_count: int
    cache_hit_rate: float


class RecallRequest(BaseModel):
    """无状态召回请求（新版API）"""
    messages: List[Message] = Field(..., description="完整消息列表")
    query: str = Field(..., description="当前查询")
    k: int = Field(default=50, ge=1, le=500, description="召回数量")
    algorithm: str = Field(default="car", description="算法类型: car/dense/hybrid")
    n_clusters: int = Field(default=10, ge=2, le=50, description="聚类数量（仅CAR算法使用）")


class RecallResponse(BaseModel):
    """无状态召回响应（新版API）"""
    recalled_messages: List[Dict]
    original_count: int
    recalled_count: int
    latency_ms: float
    algorithm_used: str
    cache_hit_rate: float


# ============ 生命周期事件 ============

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    global service
    
    print("\n" + "="*80)
    print("启动 1M→400K Context Compression API 服务")
    print("="*80)
    
    service = ProductionContextService(
        cache_backend=CacheBackend.MEMORY,  # 生产环境改为 CacheBackend.REDIS
        cache_ttl=3600,
        enable_monitoring=True
    )
    
    await service.initialize()
    
    print("✓ 服务启动成功")
    print("="*80 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    global service
    
    if service:
        await service.shutdown()


# ============ API端点 ============

@app.get("/", tags=["Root"])
async def root():
    """根路径"""
    return {
        "service": "1M→400K Context Compression API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "metrics": "/metrics",
            "recall": "/api/v1/recall",
            "build_clusters": "/api/v1/clusters/build",
            "retrieve": "/api/v1/retrieve",
            "docs": "/docs"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
async def health_check():
    """
    健康检查
    
    返回服务的健康状态、运行时间、错误率等指标
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    health = service.get_health()
    return health


@app.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
async def get_metrics(window_seconds: int = 60):
    """
    获取监控指标
    
    - **window_seconds**: 时间窗口（秒），默认60秒
    
    返回指定时间窗口内的请求统计、延迟分布、错误率等
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    metrics = service.get_metrics(window_seconds)
    return metrics


@app.get("/cache/stats", tags=["Monitoring"])
async def get_cache_stats():
    """
    获取缓存统计
    
    返回缓存后端类型、键数量、内存使用等信息
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    stats = await service.get_cache_stats()
    return stats


@app.post("/api/v1/clusters/build", tags=["Clustering"])
async def build_clusters(request: BuildClusterRequest, background_tasks: BackgroundTasks):
    """
    构建聚类索引
    
    - **session_id**: 会话ID，用于标识不同的消息集合
    - **messages**: 消息列表
    - **n_clusters**: 聚类数量（2-50）
    
    异步构建聚类索引，加速后续召回
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    # 保存消息
    message_store[request.session_id] = [msg.dict() for msg in request.messages]
    
    # 构建聚类
    try:
        await service.build_clusters_async(
            message_store[request.session_id],
            n_clusters=request.n_clusters
        )
        
        return {
            "session_id": request.session_id,
            "message_count": len(request.messages),
            "n_clusters": request.n_clusters,
            "status": "success"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聚类失败: {str(e)}")


@app.post("/api/v1/retrieve", response_model=RetrievalResponse, tags=["Retrieval"])
async def retrieve_context(request: RetrievalRequest):
    """
    召回相关上下文
    
    - **session_id**: 会话ID
    - **query**: 查询文本
    - **k**: 召回数量（1-500）
    
    使用CAR算法从历史消息中召回最相关的k条消息
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    # 检查会话是否存在
    if request.session_id not in message_store:
        raise HTTPException(status_code=404, detail=f"会话 {request.session_id} 不存在，请先调用 /api/v1/clusters/build")
    
    messages = message_store[request.session_id]
    
    # 检查是否已构建聚类
    if service.cluster_labels is None:
        raise HTTPException(status_code=400, detail="聚类索引未构建，请先调用 /api/v1/clusters/build")
    
    try:
        # CAR召回
        results, latency = await service.car_retrieval_async(
            request.query,
            messages,
            k=request.k
        )
        
        # 格式化结果
        formatted_results = []
        for msg, score, idx in results:
            formatted_results.append({
                "index": int(idx),
                "content": msg["content"],
                "topic": msg.get("topic"),
                "similarity": float(score),
                "role": msg.get("role", "user")
            })
        
        # 获取缓存命中率
        health = service.get_health()
        
        return RetrievalResponse(
            session_id=request.session_id,
            query=request.query,
            results=formatted_results,
            latency_ms=latency,
            cache_hit_rate=health["cache_hit_rate"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"召回失败: {str(e)}")


@app.post("/api/v1/recall", response_model=RecallResponse, tags=["Retrieval"])
async def recall_messages(request: RecallRequest):
    """
    无状态召回接口（推荐使用）
    
    - **messages**: 完整消息列表
    - **query**: 当前查询
    - **k**: 召回数量（1-500）
    - **algorithm**: 算法类型（car/dense/hybrid）
    - **n_clusters**: 聚类数量（仅CAR使用）
    
    一步式无状态召回，无需预先构建聚类
    """
    if not service:
        raise HTTPException(status_code=503, detail="服务未初始化")
    
    import time
    start_time = time.time()
    
    try:
        # 转换消息格式
        messages_dict = [msg.dict() for msg in request.messages]
        
        # 根据算法类型执行召回
        if request.algorithm == "car":
            # CAR算法：构建聚类 + 召回
            await service.build_clusters_async(messages_dict, n_clusters=request.n_clusters)
            results, _ = await service.car_retrieval_async(request.query, messages_dict, k=request.k)
            
        elif request.algorithm == "dense":
            # Dense Only：纯向量检索
            query_emb = await service.embed_cached(request.query)
            msg_embeddings = []
            for msg in messages_dict:
                emb = await service.embed_cached(msg["content"])
                msg_embeddings.append(emb)
            
            # 计算相似度
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            
            similarities = cosine_similarity([query_emb], msg_embeddings)[0]
            top_indices = np.argsort(similarities)[::-1][:request.k]
            
            results = [
                (messages_dict[idx], float(similarities[idx]), int(idx))
                for idx in top_indices
            ]
            
        else:
            raise HTTPException(status_code=400, detail=f"不支持的算法: {request.algorithm}")
        
        # 格式化结果
        recalled_messages = []
        for msg, score, idx in results:
            recalled_messages.append({
                "index": int(idx),
                "content": msg["content"],
                "role": msg.get("role", "user"),
                "topic": msg.get("topic"),
                "similarity": float(score)
            })
        
        # 计算延迟
        latency_ms = (time.time() - start_time) * 1000
        
        # 获取缓存命中率
        health = service.get_health()
        
        return RecallResponse(
            recalled_messages=recalled_messages,
            original_count=len(request.messages),
            recalled_count=len(recalled_messages),
            latency_ms=latency_ms,
            algorithm_used=request.algorithm,
            cache_hit_rate=health["cache_hit_rate"]
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"召回失败: {str(e)}")


@app.delete("/api/v1/sessions/{session_id}", tags=["Session Management"])
async def delete_session(session_id: str):
    """
    删除会话
    
    删除指定会话的消息和聚类索引
    """
    if session_id in message_store:
        del message_store[session_id]
        return {"session_id": session_id, "status": "deleted"}
    else:
        raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")


@app.get("/api/v1/sessions", tags=["Session Management"])
async def list_sessions():
    """
    列出所有会话
    
    返回当前存储的所有会话ID和消息数量
    """
    sessions = []
    for session_id, messages in message_store.items():
        sessions.append({
            "session_id": session_id,
            "message_count": len(messages)
        })
    
    return {"sessions": sessions, "total": len(sessions)}


# ============ 错误处理 ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )


# ============ 启动服务器 ============

if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
