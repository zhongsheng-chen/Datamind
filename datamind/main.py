# datamind/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from datamind.config import get_settings
from datamind.api.middlewares import (
    LoggingMiddleware,
    AuthenticationMiddleware,
    RateLimitMiddleware,
    APIVersionMiddleware,  # 新增版本中间件
    SecurityHeadersMiddleware
)
from datamind.api.routes import v1, v2  # 导入不同版本路由
from datamind.core.db.database import db_manager
from datamind.core.logging import log_manager

settings = get_settings()

# 创建应用
app = FastAPI(
    title="Datamind - 银行贷款模型部署平台",
    description="支持评分卡和反欺诈模型的部署平台",
    version=settings.app.version,
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置中间件（顺序很重要）
app.add_middleware(APIVersionMiddleware)  # 1. API版本检查（最先）
app.add_middleware(SecurityHeadersMiddleware)  # 2. 安全头
app.add_middleware(RateLimitMiddleware)  # 3. 限流
app.add_middleware(LoggingMiddleware)  # 4. 日志
app.add_middleware(AuthenticationMiddleware)  # 5. 认证

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由 - 支持多版本
app.include_router(v1.router)  # API v1
if "v2" in settings.api.supported_versions:
    app.include_router(v2.router)  # API v2（如果支持）


# 根路由 - 显示 API 版本信息
@app.get("/")
async def root():
    """根路由，返回 API 版本信息"""
    return {
        "name": "Datamind",
        "version": settings.app.version,
        "api": {
            "current_version": settings.api.api_version,
            "supported_versions": settings.api.supported_versions,
            "deprecated_versions": settings.api.deprecated_versions,
            "base_path": settings.api.prefix
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


# 版本信息端点
@app.get("/api/versions")
async def api_versions():
    """获取 API 版本信息"""
    return {
        "current": settings.api.api_version,
        "supported": settings.api.supported_versions,
        "deprecated": settings.api.deprecated_versions,
        "versions": [
            {
                "version": v,
                "status": "deprecated" if v in settings.api.deprecated_versions else "supported",
                "base_path": f"/api/{v}"
            }
            for v in settings.api.supported_versions
        ]
    }


# 启动事件
@app.on_event("startup")
async def startup():
    """应用启动时的初始化"""
    # 初始化数据库连接
    db_manager.initialize()

    # 初始化日志系统
    log_manager.initialize()

    # 打印启动信息
    print(f"\n{'=' * 60}")
    print(f"Datamind - 银行贷款模型部署平台")
    print(f"版本: {settings.app.version}")
    print(f"环境: {settings.app.env}")
    print(f"API 版本: {settings.api.api_version}")
    print(f"支持版本: {settings.api.supported_versions}")
    print(f"API 文档: http://{settings.api.host}:{settings.api.port}/docs")
    print(f"{'=' * 60}\n")


# 关闭事件
@app.on_event("shutdown")
async def shutdown():
    """应用关闭时的清理"""
    db_manager.cleanup()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.app.debug
    )