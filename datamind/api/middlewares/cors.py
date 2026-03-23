# datamind/api/middlewares/cors.py

"""CORS 中间件

提供跨域资源共享（CORS）配置，允许前端应用访问 API。

功能特性：
  - 自定义允许的源（origins）
  - 自定义允许的方法（methods）
  - 自定义允许的请求头（headers）
  - 自定义暴露的响应头（expose_headers）
  - 支持凭证传递（credentials）
  - 预检请求缓存时间（max_age）
  - CORS 请求日志记录
  - 链路追踪支持
  - 从配置中心读取配置

默认配置：
  - allow_origins: ["*"]（允许所有源，生产环境建议限制）
  - allow_methods: GET、POST、PUT、DELETE、OPTIONS、PATCH
  - allow_headers: Content-Type、Authorization、X-Request-ID、X-API-Key、X-Application-ID
  - expose_headers: X-Request-ID、X-Process-Time-MS、X-RateLimit-Limit、X-RateLimit-Remaining、X-RateLimit-Reset
  - allow_credentials: True（允许携带凭证）
  - max_age: 600 秒（预检请求缓存时间）

CORS 响应头说明：
  - Access-Control-Allow-Origin: 允许的源
  - Access-Control-Allow-Credentials: 是否允许凭证
  - Access-Control-Allow-Methods: 允许的方法
  - Access-Control-Allow-Headers: 允许的请求头
  - Access-Control-Expose-Headers: 暴露的响应头
  - Access-Control-Max-Age: 预检请求缓存时间
"""

import time
import re
from typing import List, Optional, Dict, Any
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from datamind.core.domain.enums import AuditAction
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.config import get_settings
from datamind.config.settings import CORSConfig


class CustomCORSMiddleware(CORSMiddleware):
    """
    自定义CORS中间件

    扩展FastAPI的CORS中间件，添加自定义配置、日志记录和链路追踪。
    支持配置允许的源、方法、头信息等。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[CORSConfig] = None,
            allow_origins: Optional[List[str]] = None,
            allow_credentials: Optional[bool] = None,
            allow_methods: Optional[List[str]] = None,
            allow_headers: Optional[List[str]] = None,
            expose_headers: Optional[List[str]] = None,
            max_age: Optional[int] = None,
            allow_origin_regex: Optional[str] = None,
            log_cors_requests: Optional[bool] = None,
    ):
        """
        初始化 CORS 中间件

        参数:
            app: ASGI 应用
            config: CORS配置对象（优先级最高）
            allow_origins: 允许的源列表
            allow_credentials: 是否允许携带凭证
            allow_methods: 允许的 HTTP 方法
            allow_headers: 允许的请求头
            expose_headers: 暴露给前端的响应头
            max_age: 预检请求缓存时间（秒）
            allow_origin_regex: 允许的源正则表达式
            log_cors_requests: 是否记录 CORS 请求日志
        """
        # 加载配置
        settings = get_settings()
        self.config = config or settings.cors

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.allow_origins = allow_origins or self.config.cors_origins
        self.allow_credentials = allow_credentials if allow_credentials is not None else self.config.cors_allow_credentials
        self.allow_methods = allow_methods or self.config.cors_methods
        self.allow_headers = allow_headers or self.config.cors_headers
        self.expose_headers = expose_headers or self.config.cors_expose_headers
        self.max_age = max_age or self.config.cors_max_age
        self.log_cors_requests = log_cors_requests if log_cors_requests is not None else self.config.cors_log_requests

        # 生产环境安全检查：不允许通配符源
        if settings.app.env == "production" and "*" in self.allow_origins:
            debug_print(
                "CORS",
                "警告: 生产环境不允许使用通配符源 '*'，将使用空列表"
            )
            self.allow_origins = []

        # 编译源正则表达式（如果提供）
        self.allow_origin_regex_compiled = None
        if allow_origin_regex:
            try:
                self.allow_origin_regex_compiled = re.compile(allow_origin_regex)
            except re.error as e:
                debug_print("CORS", f"无效的正则表达式: {allow_origin_regex}, 错误: {e}")

        super().__init__(
            app=app,
            allow_origins=self.allow_origins,
            allow_credentials=self.allow_credentials,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            expose_headers=self.expose_headers,
            max_age=self.max_age,
            allow_origin_regex=allow_origin_regex
        )

    async def __call__(self, scope, receive, send):
        """处理请求，添加 CORS 日志和链路追踪"""
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)
        start_time = time.time()
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        # 获取请求信息
        origin = request.headers.get("origin", "")
        is_preflight = request.method == "OPTIONS" and "access-control-request-method" in request.headers

        # 检查源是否允许
        is_origin_allowed = self._is_origin_allowed(origin) if origin else False

        # 记录 CORS 请求日志
        if self.log_cors_requests:
            debug_print(
                "CORS",
                f"CORS请求: {request.method} {request.url.path} "
                f"origin={origin or 'none'}, "
                f"preflight={is_preflight}, "
                f"allowed={is_origin_allowed}"
            )

        # 自定义 send 函数来记录响应和添加追踪头
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # 记录 CORS 预检请求
                if self.log_cors_requests and is_preflight:
                    duration = (time.time() - start_time) * 1000
                    headers = message.get("headers", [])
                    headers_dict = {k.decode(): v.decode() for k, v in headers}
                    status_code = int(headers_dict.get("status", "200"))

                    log_audit(
                        action=AuditAction.CORS_PREFLIGHT.value,
                        user_id="anonymous",
                        ip_address=self._get_client_ip(request),
                        details={
                            "origin": origin,
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": status_code,
                            "duration_ms": round(duration, 2),
                            "is_origin_allowed": is_origin_allowed,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id,
                            "request_method": request.headers.get("access-control-request-method"),
                            "request_headers": request.headers.get("access-control-request-headers")
                        },
                        request_id=request_id
                    )

                # 记录被拒绝的 CORS 请求
                elif not is_origin_allowed and origin:
                    log_audit(
                        action=AuditAction.IP_BLOCKED.value,
                        user_id="anonymous",
                        ip_address=self._get_client_ip(request),
                        details={
                            "origin": origin,
                            "method": request.method,
                            "path": request.url.path,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

            await send(message)

        await self.app(scope, receive, send_wrapper)

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    def _is_origin_allowed(self, origin: str) -> bool:
        """检查源是否被允许"""
        # 如果允许所有源
        if "*" in self.allow_origins:
            return True

        # 检查精确匹配
        if origin in self.allow_origins:
            return True

        # 检查正则表达式匹配
        if self.allow_origin_regex_compiled:
            if self.allow_origin_regex_compiled.match(origin):
                return True

        return False


# datamind/api/middlewares/cors.py

class DevelopmentCORSMiddleware(CustomCORSMiddleware):
    """开发环境专用的 CORS 中间件，允许所有源"""

    def __init__(self, app: ASGIApp, **kwargs):
        settings = get_settings()
        config = settings.cors

        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'config'}

        super().__init__(
            app=app,
            config=config,
            allow_origins=["*"],
            allow_credentials=True,
            log_cors_requests=True,
            **filtered_kwargs
        )


class ProductionCORSMiddleware(CustomCORSMiddleware):
    """生产环境专用的 CORS 中间件，仅允许配置的源"""

    def __init__(self, app: ASGIApp, **kwargs):
        settings = get_settings()
        config = settings.cors

        filtered_kwargs = {k: v for k, v in kwargs.items() if k != 'config'}

        super().__init__(
            app=app,
            config=config,
            allow_origins=config.cors_origins,
            allow_credentials=config.cors_allow_credentials,
            log_cors_requests=config.cors_log_requests,
            **filtered_kwargs
        )


def setup_cors(
        app: ASGIApp,
        config: Optional[CORSConfig] = None,
        allow_origins: Optional[List[str]] = None,
        allow_credentials: Optional[bool] = None,
        log_cors_requests: Optional[bool] = None,
        use_env_config: bool = True
) -> None:
    """
    设置 CORS 中间件的便捷函数，自动根据环境选择配置

    参数:
        app: ASGI 应用
        config: CORS配置对象
        allow_origins: 允许的源列表，如果为 None 则根据环境自动选择
        allow_credentials: 是否允许携带凭证
        log_cors_requests: 是否记录 CORS 请求日志
        use_env_config: 是否使用环境配置
    """
    settings = get_settings()

    # 如果指定了 allow_origins，使用指定的
    if allow_origins is not None:
        app.add_middleware(
            CustomCORSMiddleware,
            config=config,
            allow_origins=allow_origins,
            allow_credentials=allow_credentials,
            log_cors_requests=log_cors_requests
        )
        return

    # 根据环境选择配置
    if settings.app.env == "production" and use_env_config:
        # 生产环境：使用生产环境中间件
        app.add_middleware(
            ProductionCORSMiddleware,
            config=config,
            allow_credentials=allow_credentials,
            log_cors_requests=log_cors_requests
        )
    else:
        # 开发/测试环境：使用开发环境中间件
        app.add_middleware(
            DevelopmentCORSMiddleware,
            config=config,
            allow_credentials=allow_credentials,
            log_cors_requests=log_cors_requests
        )


def get_cors_config() -> Dict[str, Any]:
    """
    获取 CORS 配置信息

    返回:
        dict: CORS 配置字典
    """
    settings = get_settings()

    return {
        "allow_origins": settings.cors.cors_origins,
        "allow_credentials": settings.cors.cors_allow_credentials,
        "allow_methods": settings.cors.cors_methods,
        "allow_headers": settings.cors.cors_headers,
        "expose_headers": settings.cors.cors_expose_headers,
        "max_age": settings.cors.cors_max_age,
        "log_requests": settings.cors.cors_log_requests
    }


def is_cors_preflight_request(request: Request) -> bool:
    """
    判断是否为 CORS 预检请求

    参数:
        request: FastAPI 请求对象

    返回:
        bool: 是否为预检请求
    """
    return (request.method == "OPTIONS" and
            "access-control-request-method" in request.headers)


def add_cors_headers(
        response_headers: Dict[str, str],
        config: Optional[CORSConfig] = None
) -> Dict[str, str]:
    """
    添加 CORS 响应头

    参数:
        response_headers: 响应头字典
        config: CORS配置对象

    返回:
        dict: 添加了 CORS 头的响应头字典
    """
    settings = get_settings()
    cors_config = config or settings.cors

    # 确定允许的源
    if "*" in cors_config.cors_origins:
        allow_origin = "*"
    else:
        allow_origin = ", ".join(cors_config.cors_origins) if cors_config.cors_origins else "*"

    # 添加 CORS 头
    cors_headers = {
        "Access-Control-Allow-Origin": allow_origin,
        "Access-Control-Allow-Credentials": str(cors_config.cors_allow_credentials).lower(),
        "Access-Control-Allow-Methods": ", ".join(cors_config.cors_methods),
        "Access-Control-Allow-Headers": ", ".join(cors_config.cors_headers),
        "Access-Control-Expose-Headers": ", ".join(cors_config.cors_expose_headers),
        "Access-Control-Max-Age": str(cors_config.cors_max_age)
    }

    response_headers.update(cors_headers)
    return response_headers


def validate_cors_config(config: Optional[CORSConfig] = None) -> List[str]:
    """
    验证 CORS 配置的安全性

    参数:
        config: CORS配置对象

    返回:
        List[str]: 验证警告列表
    """
    settings = get_settings()
    cors_config = config or settings.cors

    warnings = []

    # 检查通配符源
    if "*" in cors_config.cors_origins and cors_config.cors_allow_credentials:
        warnings.append(
            "安全警告: 当 allow_credentials=True 时使用通配符源 '*' 是不安全的，"
            "浏览器会拒绝此配置。建议指定具体的源列表。"
        )

    # 检查生产环境配置
    if settings.app.env == "production":
        if "*" in cors_config.cors_origins:
            warnings.append(
                "生产环境警告: 不应在生产环境使用通配符源 '*'，"
                "请配置具体的允许源列表"
            )

        if not cors_config.cors_origins:
            warnings.append(
                "生产环境警告: 未配置允许的源列表，CORS 将拒绝所有跨域请求"
            )

    return warnings