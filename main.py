from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.storage import storage_manager
from app.db import neo4j_client, milvus_client
from app.api.routes import analysis, history, chat

# 配置日志
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # Startup
    logger.info("Starting up application...")

    # Neo4j 连接（可选）
    try:
        await neo4j_client.connect()
        logger.info("Neo4j connected successfully")
    except Exception as e:
        logger.warning(f"Neo4j connection failed (optional): {e}")

    # Milvus 连接（可选）
    try:
        milvus_client.connect()
        milvus_client.create_collection_if_not_exists()
        logger.info("Milvus connected successfully")
    except Exception as e:
        logger.warning(f"Milvus connection failed (optional): {e}")

    logger.info("Application startup complete (external services are optional)")
    yield

    # Shutdown
    logger.info("Shutting down application...")
    try:
        await neo4j_client.close()
        logger.info("Neo4j closed")
    except Exception as e:
        logger.warning(f"Error closing Neo4j: {e}")

    try:
        milvus_client.disconnect()
        logger.info("Milvus closed")
    except Exception as e:
        logger.warning(f"Error closing Milvus: {e}")


# 创建 FastAPI 应用
app = FastAPI(
    title="数据库故障分析系统 API",
    description="基于本体技术的数据库故障根因分析系统",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置 - 添加前端可能的所有端口
cors_origins = list(settings.cors_origins)
frontend_ports = [5173, 5174, 5175, 5176]
for port in frontend_ports:
    url = f"http://localhost:{port}"
    if url not in cors_origins:
        cors_origins.append(url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": settings.environment}


# 注册路由
app.include_router(analysis.router)
app.include_router(history.router)
app.include_router(chat.router)


# 主入口
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.log_level.lower(),
        reload=settings.debug,
    )
