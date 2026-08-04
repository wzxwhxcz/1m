"""
FastAPI 服务器 - 使用远程 Embedding API
提供无状态召回接口
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import uvicorn
import logging
import os

from production_service_remote import get_recall_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Context Recall API",
    description="上下文召回服务 - 使用远程 Embedding API",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    """消息模型"""
    role: str = Field(..., description="角色 (user/assistant/system)")
    content: str = Field(..., description="消息内容")


class RecallRequest(BaseModel):
    """召回请求"""
    messages: List[Message] = Field(..., description="历史消息列表")
    query: str = Field(..., description="当前查询")
    k: int = Field(50, ge=1, le=200, description="召回数量")
    algorithm: str = Field("dense_only", description="算法选择 (dense_only/hybrid_dat/car)")


class RecallResponse(BaseModel):
    """召回响应"""
    recalled_messages: List[Message]
    algorithm: str
    latency_ms: float
    original_count: int
    recalled_count: int
    cache_hit_rate: float
    model: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str
    model: str
    algorithms: List[str]
    embedding_service: Optional[Dict] = None


# 环境变量配置
API_BASE = os.getenv("EMBEDDING_API_BASE", "https://router.tumuer.me/v1")
API_KEY = os.getenv("EMBEDDING_API_KEY")
if not API_KEY:
    raise ValueError("EMBEDDING_API_KEY environment variable is required")
MODEL = os.getenv("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-4B")
REDIS_URL = os.getenv("REDIS_URL", None)


@app.on_event("startup")
async def startup_event():
    """启动时初始化服务"""
    logger.info("🚀 启动 Context Recall API Server")
    logger.info(f"   Embedding API: {API_BASE}")
    logger.info(f"   Model: {MODEL}")
    logger.info(f"   Redis: {REDIS_URL or 'Memory Cache'}")
    
    # 预热服务
    try:
        service = await get_recall_service(
            api_base=API_BASE,
            api_key=API_KEY,
            model=MODEL,
            redis_url=REDIS_URL
        )
        await service.initialize()
        logger.info("✓ 服务初始化成功")
    except Exception as e:
        logger.error(f"❌ 服务初始化失败: {e}")


@app.get("/", response_model=Dict[str, str])
async def root():
    """根路径"""
    return {
        "service": "Context Recall API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    try:
        service = await get_recall_service(
            api_base=API_BASE,
            api_key=API_KEY,
            model=MODEL,
            redis_url=REDIS_URL
        )
        
        health = await service.health_check()
        return HealthResponse(**health, model=MODEL)
    
    except Exception as e:
        logger.error(f"❌ 健康检查失败: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/api/v1/recall", response_model=RecallResponse)
async def recall_messages(request: RecallRequest):
    """
    召回接口 - 从大量历史消息中召回最相关的内容
    
    支持三种算法:
    - dense_only: 纯向量检索（推荐，最快）
    - hybrid_dat: 混合检索 + 动态权重
    - car: 基于聚类的自适应召回
    """
    try:
        service = await get_recall_service(
            api_base=API_BASE,
            api_key=API_KEY,
            model=MODEL,
            redis_url=REDIS_URL
        )
        
        # 转换消息格式
        messages_dict = [msg.dict() for msg in request.messages]
        
        # 执行召回
        result = await service.recall(
            messages=messages_dict,
            query=request.query,
            k=request.k,
            algorithm=request.algorithm
        )
        
        # 转换回 Pydantic 模型
        recalled_messages = [
            Message(role=msg.role, content=msg.content)
            for msg in result.messages
        ]
        
        return RecallResponse(
            recalled_messages=recalled_messages,
            algorithm=result.algorithm,
            latency_ms=round(result.latency_ms, 2),
            original_count=result.original_count,
            recalled_count=result.recalled_count,
            cache_hit_rate=round(result.cache_hit_rate, 1),
            model=MODEL
        )
    
    except Exception as e:
        logger.error(f"❌ 召回失败: {e}")
        raise HTTPException(status_code=500, detail=f"Recall failed: {str(e)}")


@app.get("/api/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "models": [
            {
                "id": "Qwen/Qwen3-Embedding-4B",
                "name": "Qwen3 Embedding 4B",
                "dimension": 2560,
                "max_tokens": 32000,
                "languages": ["zh", "en"],
                "recommended": True
            },
            {
                "id": "Qwen/Qwen3-Embedding-8B",
                "name": "Qwen3 Embedding 8B",
                "dimension": 4096,
                "max_tokens": 32000,
                "languages": ["zh", "en"],
                "recommended": False
            },
            {
                "id": "jina-embeddings-v4",
                "name": "Jina Embeddings V4",
                "dimension": 2048,
                "max_tokens": 32000,
                "languages": ["zh", "en"],
                "recommended": False
            }
        ],
        "current": MODEL
    }


@app.get("/metrics")
async def metrics():
    """Prometheus 监控指标"""
    # 简化版指标
    return {
        "service": "context_recall",
        "status": "healthy",
        "model": MODEL
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "api_server_remote:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
