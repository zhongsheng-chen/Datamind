# datamind/main.py
"""
Datamind - 银行贷款模型部署平台
主应用入口
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from datamind.api import api_router
from datamind.api.middlewares import (
    setup_cors,
    setup_logging_middleware,
    setup_rate_limit_middleware,
    setup_performance_middleware,
    setup_database_performance_middleware,
    setup_security_middleware,
    AuthenticationMiddleware,
    APIVersionMiddleware,
    APIVersionCompatibilityMiddleware,
)
from datamind.core.logging import log_manager, context, bootstrap
from datamind.core.db.database import db_manager, init_db
from datamind.core.ml.model import get_model_loader
from datamind.config import get_settings

# 获取配置
settings = get_settings()

# 安装启动日志缓存
bootstrap.install_bootstrap_logger()
bootstrap.bootstrap_info("Datamind 正在启动...")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    应用生命周期管理
    """
    # 启动时执行
    bootstrap.bootstrap_info("初始化日志系统...")
    log_manager.initialize(settings.logging)

    bootstrap.bootstrap_info("初始化数据库连接...")
    db_manager.initialize()

    bootstrap.bootstrap_info("创建数据库表结构...")
    init_db()

    bootstrap.bootstrap_info("初始化模型加载器...")
    model_loader = get_model_loader()
    bootstrap.bootstrap_info(f"模型加载器初始化完成，缓存TTL: {model_loader._cache_ttl}秒")

    bootstrap.bootstrap_info("初始化推理引擎...")
    from datamind.core.ml.model import get_inference_engine
    inference_engine = get_inference_engine()
    bootstrap.bootstrap_info(f"推理引擎初始化完成，缓存大小: {inference_engine._cache._max_size}")

    bootstrap.bootstrap_info("=" * 60)
    bootstrap.bootstrap_info(f"Datamind v{settings.app.version} 启动成功")
    bootstrap.bootstrap_info(f"环境: {settings.app.env}")
    bootstrap.bootstrap_info(f"API 文档: http://{settings.api.host}:{settings.api.port}/docs")
    bootstrap.bootstrap_info(f"API 前缀: {settings.api.prefix}")
    bootstrap.bootstrap_info("=" * 60)

    yield

    # 关闭时执行
    bootstrap.bootstrap_info("正在关闭 Datamind...")

    # 停止日志管理器
    log_manager.cleanup()

    bootstrap.bootstrap_info("Datamind 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="Datamind API",
    description="银行贷款模型部署平台 - 支持评分卡模型和反欺诈模型",
    version=settings.app.version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ==================== 中间件配置 ====================

# 日志中间件（最先执行，记录请求信息）
setup_logging_middleware(app)

# 认证中间件
app.add_middleware(
    AuthenticationMiddleware,
    exclude_paths=["/health", "/metrics", "/docs", "/redoc", "/openapi.json", "/static"],
)

# API 版本管理中间件
app.add_middleware(APIVersionMiddleware)
app.add_middleware(APIVersionCompatibilityMiddleware)

# 限流中间件
setup_rate_limit_middleware(app)

# CORS 中间件
setup_cors(app)

# 安全中间件
setup_security_middleware(app)

# 性能监控中间件
setup_performance_middleware(app)

# 数据库性能监控中间件
setup_database_performance_middleware(app)


# ==================== 异常处理 ====================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 异常处理"""
    request_id = context.get_request_id()

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            },
            "request_id": request_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求验证异常处理"""
    request_id = context.get_request_id()

    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "details": {"errors": errors},
            },
            "request_id": request_id,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    request_id = context.get_request_id()

    log_manager.log_audit(
        action="UNHANDLED_EXCEPTION",
        user_id="system",
        ip_address=request.client.host if request.client else None,
        details={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc),
            "error_type": type(exc).__name__,
            "request_id": request_id,
        },
        request_id=request_id,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后重试",
            },
            "request_id": request_id,
        },
    )


# ==================== 健康检查 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "datamind",
        "version": settings.app.version,
        "environment": settings.app.env,
        "timestamp": log_manager.get_current_time().isoformat(),
    }


@app.get("/metrics")
async def metrics():
    """监控指标（Prometheus格式）"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/ready")
async def readiness_check():
    """就绪检查"""
    # 检查数据库连接
    db_health = db_manager.check_health()
    if db_health["status"] != "healthy":
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "database not ready"},
        )

    # 检查是否有模型加载
    model_loader = get_model_loader()
    loaded_models = model_loader.get_loaded_models()
    if not loaded_models and settings.app.env == "production":
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "no models loaded"},
        )

    return {"status": "ready"}


# ==================== 注册路由 ====================

app.include_router(api_router, prefix=settings.api.prefix)


# ==================== 启动脚本 ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "datamind.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.app.debug,
        log_level="debug" if settings.app.debug else "info",
    )