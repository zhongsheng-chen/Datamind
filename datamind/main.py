# Datamind/datamind/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uuid
from datetime import datetime, timedelta
from sqlalchemy import func

from datamind.config import LoggingConfig
from datamind.config import settings
from datamind.core import log_manager, set_request_id, get_request_id
from datamind.core import db_manager, init_db, get_db
from datamind.core import ModelMetadata, ApiCallLog, AuditLog
from datamind.core import model_registry, model_loader
from datamind.api import api_router

# 导入中间件
from datamind.api import (
    AuthenticationMiddleware,
    LoggingMiddleware,
    RateLimitMiddleware,
    CustomCORSMiddleware,
    SecurityHeadersMiddleware,
    IPWhitelistMiddleware,
    RequestSizeLimitMiddleware,
    PerformanceMiddleware,
    SlowRequestMiddleware,
    RequestValidationMiddleware
)

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    root_path=settings.API_ROOT_PATH
)

# 设置模板和静态文件
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==================== 中间件注册（顺序很重要） ====================

# 1. 安全相关中间件（最外层）
app.add_middleware(
    CustomCORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SecurityHeadersMiddleware)

if settings.TRUSTED_PROXIES:
    app.add_middleware(IPWhitelistMiddleware, whitelist=set(settings.TRUSTED_PROXIES))

app.add_middleware(RequestSizeLimitMiddleware, max_size=10 * 1024 * 1024)  # 10MB

# 2. 请求验证中间件
app.add_middleware(RequestValidationMiddleware, max_age=300)  # 5分钟

# 3. 性能监控中间件
app.add_middleware(PerformanceMiddleware, enable_detailed=settings.DEBUG)
app.add_middleware(SlowRequestMiddleware, slow_threshold=1000)  # 1秒

# 4. 认证和限流中间件
app.add_middleware(
    AuthenticationMiddleware,
    exclude_paths=[
        "/health",
        "/api/docs",
        "/api/redoc",
        "/openapi.json",
        "/ui",
        "/static",
        "/"
    ],
    public_paths=[
        "/api/v1/auth/login",
        "/api/v1/auth/register"
    ]
)

# 5. 限流中间件（需要认证信息）
if settings.RATE_LIMIT_ENABLED:
    # 可以在这里初始化Redis客户端
    # redis_client = redis.from_url(settings.REDIS_URL)
    app.add_middleware(
        RateLimitMiddleware,
        # redis_client=redis_client,
        default_limit=settings.RATE_LIMIT_REQUESTS,
        default_period=settings.RATE_LIMIT_PERIOD,
        exclude_paths=["/health", "/metrics", "/static", "/ui"]
    )

# 6. 日志中间件（最内层，记录所有信息）
app.add_middleware(
    LoggingMiddleware,
    exclude_paths=["/health", "/metrics", "/static", "/favicon.ico"],
    log_request_body=settings.DEBUG,
    log_response_body=False,
    mask_sensitive_data=True
)

# ==================== 注册API路由 ====================

app.include_router(api_router, prefix=settings.API_PREFIX)


# ==================== 请求ID中间件（保留，因为其他中间件依赖它） ====================

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """请求ID中间件 - 必须在最前面执行"""
    # 生成或获取请求ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_id(request_id)

    # 处理请求
    response = await call_next(request)

    # 添加请求ID到响应头
    response.headers["X-Request-ID"] = request_id

    return response


# ==================== 生命周期事件 ====================

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    # 初始化日志配置
    log_config = LoggingConfig.load()
    log_manager.initialize(log_config)

    # 记录启动审计日志
    log_manager.log_audit(
        action="SYSTEM_STARTUP",
        user_id="system",
        ip_address="localhost",
        details={
            "version": settings.VERSION,
            "env": settings.ENV,
            "debug": settings.DEBUG,
            "middlewares": [
                "CORS", "Security", "IPWhitelist", "RequestSize",
                "RequestValidation", "Performance", "SlowRequest",
                "Authentication", "RateLimit", "Logging"
            ]
        }
    )

    # 初始化数据库
    db_manager.initialize(
        database_url=settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_recycle=settings.DB_POOL_RECYCLE,
        echo=settings.DB_ECHO
    )
    init_db()

    # 加载生产模型
    await load_production_models()

    # 打印启动信息
    print(f"""
    ╔════════════════════════════════════════════════════════════╗
    ║     Datamind 模型部署平台 v{settings.VERSION}                           ║
    ╠════════════════════════════════════════════════════════════╣
    ║ 环境: {settings.ENV:<52} ║
    ║ 调试模式: {str(settings.DEBUG):<50} ║
    ║ 认证: {'✅' if settings.API_KEY_ENABLED else '❌':<20} 限流: {'✅' if settings.RATE_LIMIT_ENABLED else '❌':<20} ║
    ║ API地址: http://{settings.API_HOST}:{settings.API_PORT}{settings.API_PREFIX:<30} ║
    ║ 文档地址: http://{settings.API_HOST}:{settings.API_PORT}/api/docs           ║
    ║ UI地址:  http://{settings.API_HOST}:{settings.API_PORT}/ui                 ║
    ╚════════════════════════════════════════════════════════════╝
    """)


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理"""
    log_manager.log_audit(
        action="SYSTEM_SHUTDOWN",
        user_id="system",
        ip_address="localhost"
    )

    db_manager.dispose_all()
    log_manager.cleanup()


async def load_production_models():
    """加载生产环境的模型"""
    try:
        # 获取所有生产模型
        production_models = model_registry.list_models(is_production=True)

        for model in production_models:
            try:
                model_loader.load_model(
                    model_id=model['model_id'],
                    operator="system",
                    ip_address="localhost"
                )
                log_manager.log_audit(
                    action="MODEL_AUTO_LOAD",
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "model_id": model['model_id'],
                        "model_name": model['model_name'],
                        "model_version": model['model_version']
                    }
                )
            except Exception as e:
                log_manager.log_audit(
                    action="MODEL_AUTO_LOAD_FAILED",
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "model_id": model['model_id'],
                        "error": str(e)
                    },
                    reason=str(e)
                )

        print(f"已加载 {len(production_models)} 个生产模型")

    except Exception as e:
        log_manager.log_audit(
            action="MODEL_AUTO_LOAD_ERROR",
            user_id="system",
            ip_address="localhost",
            details={"error": str(e)},
            reason=str(e)
        )


# ==================== UI 路由 ====================

@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui_index(request: Request):
    """UI首页 - 仪表盘"""
    request_id = get_request_id()

    try:
        with get_db() as session:
            # 模型统计
            total_models = session.query(func.count(ModelMetadata.id)).scalar() or 0
            active_models = session.query(func.count(ModelMetadata.id)).filter_by(status='active').scalar() or 0
            production_models = session.query(func.count(ModelMetadata.id)).filter_by(is_production=True).scalar() or 0

            # 今日调用
            today = datetime.now().date()
            today_calls = session.query(func.count(ApiCallLog.id)).filter(
                func.date(ApiCallLog.created_at) == today
            ).scalar() or 0

            success_calls = session.query(func.count(ApiCallLog.id)).filter(
                func.date(ApiCallLog.created_at) == today,
                ApiCallLog.status_code == 200
            ).scalar() or 0

            failed_calls = today_calls - success_calls

            # 平均响应时间
            avg_response = session.query(func.avg(ApiCallLog.processing_time_ms)).filter(
                func.date(ApiCallLog.created_at) == today
            ).scalar() or 0

            # 近7天调用趋势
            dates = []
            scoring_calls = []
            fraud_calls = []

            for i in range(6, -1, -1):
                date = today - timedelta(days=i)
                dates.append(date.strftime('%m-%d'))

                scoring = session.query(func.count(ApiCallLog.id)).filter(
                    func.date(ApiCallLog.created_at) == date,
                    ApiCallLog.task_type == 'scoring'
                ).scalar() or 0
                scoring_calls.append(scoring)

                fraud = session.query(func.count(ApiCallLog.id)).filter(
                    func.date(ApiCallLog.created_at) == date,
                    ApiCallLog.task_type == 'fraud_detection'
                ).scalar() or 0
                fraud_calls.append(fraud)

            # 最近注册的模型
            recent_models = session.query(ModelMetadata).order_by(
                ModelMetadata.created_at.desc()
            ).limit(5).all()

            # 最近审计日志
            recent_audit = session.query(AuditLog).order_by(
                AuditLog.created_at.desc()
            ).limit(5).all()

            # 模型类型分布
            model_types = []
            for model_type in ['decision_tree', 'random_forest', 'xgboost', 'lightgbm', 'logistic_regression']:
                count = session.query(func.count(ModelMetadata.id)).filter_by(model_type=model_type).scalar() or 0
                if count > 0:
                    model_types.append({
                        'name': model_type,
                        'value': count
                    })

        stats = {
            'total_models': total_models,
            'active_models': active_models,
            'production_models': production_models,
            'today_calls': today_calls,
            'success_calls': success_calls,
            'failed_calls': failed_calls,
            'avg_response': round(avg_response, 2) if avg_response else 0,
            'p95_response': round(avg_response * 1.5, 2) if avg_response else 0,  # 简化计算
            'loaded_models': len(model_loader.get_loaded_models()),
            'memory_usage': len(model_loader.get_loaded_models()) * 100  # 估算
        }

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "env": settings.ENV,
                "version": settings.VERSION,
                "current_user": request.state.user.get('username', 'admin') if hasattr(request.state,
                                                                                       'user') else 'admin',
                "request_id": request_id,
                "stats": stats,
                "recent_models": recent_models,
                "recent_audit": recent_audit,
                "call_dates": dates,
                "scoring_calls": scoring_calls,
                "fraud_calls": fraud_calls,
                "model_types": model_types
            }
        )
    except Exception as e:
        log_manager.log_audit(
            action="UI_INDEX_ERROR",
            user_id="system",
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
            request_id=request_id
        )
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e),
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": request_id
            }
        )


@app.get("/ui/models", response_class=HTMLResponse, include_in_schema=False)
async def ui_models(request: Request):
    """模型列表页面"""
    request_id = get_request_id()

    try:
        models = model_registry.list_models()

        # 添加加载状态
        for model in models:
            model['is_loaded'] = model_loader.is_loaded(model['model_id'])

        return templates.TemplateResponse(
            "models.html",
            {
                "request": request,
                "env": settings.ENV,
                "version": settings.VERSION,
                "current_user": request.state.user.get('username', 'admin') if hasattr(request.state,
                                                                                       'user') else 'admin',
                "request_id": request_id,
                "models": models
            }
        )
    except Exception as e:
        log_manager.log_audit(
            action="UI_MODELS_ERROR",
            user_id="system",
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
            request_id=request_id
        )
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e),
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": request_id
            }
        )


@app.get("/ui/models/{model_id}", response_class=HTMLResponse, include_in_schema=False)
async def ui_model_detail(request: Request, model_id: str):
    """模型详情页面"""
    request_id = get_request_id()

    try:
        model_info = model_registry.get_model_info(model_id)
        history = model_registry.get_model_history(model_id)

        if not model_info:
            return templates.TemplateResponse(
                "404.html",
                {
                    "request": request,
                    "message": f"模型 {model_id} 不存在",
                    "env": settings.ENV,
                    "version": settings.VERSION,
                    "request_id": request_id
                }
            )

        model_info['is_loaded'] = model_loader.is_loaded(model_id)

        return templates.TemplateResponse(
            "model_detail.html",
            {
                "request": request,
                "env": settings.ENV,
                "version": settings.VERSION,
                "current_user": request.state.user.get('username', 'admin') if hasattr(request.state,
                                                                                       'user') else 'admin',
                "request_id": request_id,
                "model": model_info,
                "history": history
            }
        )
    except Exception as e:
        log_manager.log_audit(
            action="UI_MODEL_DETAIL_ERROR",
            user_id="system",
            ip_address=request.client.host if request.client else None,
            details={"model_id": model_id, "error": str(e)},
            request_id=request_id
        )
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e),
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": request_id
            }
        )


@app.get("/ui/register", response_class=HTMLResponse, include_in_schema=False)
async def ui_register(request: Request):
    """模型注册页面"""
    request_id = get_request_id()

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "env": settings.ENV,
            "version": settings.VERSION,
            "current_user": request.state.user.get('username', 'admin') if hasattr(request.state, 'user') else 'admin',
            "request_id": request_id
        }
    )


@app.get("/ui/deployments", response_class=HTMLResponse, include_in_schema=False)
async def ui_deployments(request: Request):
    """部署管理页面"""
    request_id = get_request_id()

    try:
        # 获取所有激活的模型作为可部署选项
        with get_db() as session:
            active_models = session.query(ModelMetadata).filter_by(
                status='active'
            ).order_by(ModelMetadata.created_at.desc()).all()

        return templates.TemplateResponse(
            "deployments.html",
            {
                "request": request,
                "env": settings.ENV,
                "version": settings.VERSION,
                "current_user": request.state.user.get('username', 'admin') if hasattr(request.state,
                                                                                       'user') else 'admin',
                "request_id": request_id,
                "models": active_models
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e),
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": request_id
            }
        )


@app.get("/ui/audit", response_class=HTMLResponse, include_in_schema=False)
async def ui_audit(request: Request):
    """审计日志页面"""
    request_id = get_request_id()

    try:
        with get_db() as session:
            # 获取最近的审计日志
            logs = session.query(AuditLog).order_by(
                AuditLog.created_at.desc()
            ).limit(100).all()

        return templates.TemplateResponse(
            "audit.html",
            {
                "request": request,
                "env": settings.ENV,
                "version": settings.VERSION,
                "current_user": request.state.user.get('username', 'admin') if hasattr(request.state,
                                                                                       'user') else 'admin',
                "request_id": request_id,
                "logs": logs
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e),
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": request_id
            }
        )


# ==================== API 路由 ====================

@app.get("/health")
async def health_check(request: Request):
    """健康检查"""
    db_health = db_manager.check_health()

    # 获取内存中加载的模型
    loaded_models = model_loader.get_loaded_models()

    return {
        "status": "healthy",
        "timestamp": log_manager.get_current_time().isoformat(),
        "database": db_health,
        "models": {
            "loaded": len(loaded_models),
            "list": [m['model_id'] for m in loaded_models]
        },
        "version": settings.VERSION,
        "env": settings.ENV,
        "request_id": get_request_id(),
        "client_ip": request.client.host if request.client else None
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "env": settings.ENV,
        "docs": "/api/docs",
        "health": "/health",
        "ui": "/ui",
        "request_id": get_request_id()
    }


@app.get("/config/info")
async def config_info(request: Request):
    """配置信息（仅调试模式）"""
    if not settings.DEBUG:
        return {"error": "Only available in debug mode"}

    # 返回非敏感配置信息
    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.VERSION,
            "env": settings.ENV,
            "debug": settings.DEBUG
        },
        "api": {
            "host": settings.API_HOST,
            "port": settings.API_PORT,
            "prefix": settings.API_PREFIX
        },
        "database": {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "echo": settings.DB_ECHO
        },
        "logging": {
            "level": settings.LOG_LEVEL,
            "format": settings.LOG_FORMAT,
            "path": settings.LOG_PATH
        },
        "security": {
            "api_key_enabled": settings.API_KEY_ENABLED,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "cors_origins": settings.CORS_ORIGINS
        },
        "request_id": get_request_id(),
        "client_ip": request.client.host if request.client else None
    }


# ==================== 错误处理 ====================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """404错误处理"""
    if request.url.path.startswith("/ui"):
        return templates.TemplateResponse(
            "404.html",
            {
                "request": request,
                "message": "页面未找到",
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": get_request_id()
            },
            status_code=404
        )
    return {"error": "Not Found", "request_id": get_request_id()}


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """500错误处理"""
    log_manager.log_audit(
        action="INTERNAL_SERVER_ERROR",
        user_id=request.state.user.get('id', 'anonymous') if hasattr(request.state, 'user') else 'anonymous',
        ip_address=request.client.host if request.client else None,
        details={
            "path": request.url.path,
            "method": request.method,
            "error": str(exc)
        },
        request_id=get_request_id()
    )

    if request.url.path.startswith("/ui"):
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": "服务器内部错误",
                "env": settings.ENV,
                "version": settings.VERSION,
                "request_id": get_request_id()
            },
            status_code=500
        )
    return {"error": "Internal Server Error", "request_id": get_request_id()}