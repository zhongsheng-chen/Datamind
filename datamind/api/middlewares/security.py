# datamind/api/middlewares/security.py

"""安全中间件

提供多种安全防护功能，包括安全头、IP白名单、请求大小限制、请求验证等。

中间件类型：
  SecurityHeadersMiddleware: 安全头中间件
     - 添加 X-Content-Type-Options: nosniff
     - 添加 X-Frame-Options: DENY
     - 添加 X-XSS-Protection: 1; mode=block
     - 添加 Strict-Transport-Security (HSTS)
     - 添加 Content-Security-Policy
     - 添加 Referrer-Policy
     - 添加 Permissions-Policy

  IPAccessMiddleware: IP访问控制中间件
     - 限制只有白名单内的IP可以访问
     - 支持 CIDR 表示法（如 192.168.1.0/24）
     - 记录被阻止的IP访问日志
     - 返回 403 Forbidden

  RequestSizeLimitMiddleware: 请求大小限制中间件
     - 限制请求体大小（默认 10MB）
     - 返回 413 Payload Too Large

  RequestValidationMiddleware: 请求验证中间件
     - 时间戳验证（防止重放攻击）
     - 请求签名验证（防止请求篡改）
     - 支持 HMAC-SHA256 签名

安全头说明：
  - X-Content-Type-Options: nosniff - 防止 MIME 类型嗅探
  - X-Frame-Options: DENY - 防止点击劫持
  - X-XSS-Protection: 1; mode=block - 启用 XSS 过滤
  - Strict-Transport-Security: HSTS 强制 HTTPS
  - Content-Security-Policy: 限制资源加载来源
  - Referrer-Policy: 控制 Referer 头信息
  - Permissions-Policy: 限制浏览器功能权限

请求签名验证流程：
  - 客户端计算签名：HMAC-SHA256(secret, method + path + timestamp + body)
  - 在请求头中添加 X-Timestamp 和 X-Signature
  - 服务端验证签名，防止请求被篡改
"""

import time
import hmac
import hashlib
import ipaddress
from typing import Set, Optional, List, Union, Callable, Any
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.config import (
    SecurityHeadersConfig,
    IPAccessConfig,
    RequestSizeConfig,
    RequestValidationConfig
)
from datamind.config import get_settings

logger = get_logger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件

    添加各种安全相关的 HTTP 响应头，增强应用安全性。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[SecurityHeadersConfig] = None,
            csp_policy: Optional[str] = None
    ):
        """
        初始化安全头中间件

        参数:
            app: ASGI 应用
            config: 安全头配置对象
            csp_policy: 自定义 CSP 策略，如果为 None 则使用默认策略
        """
        super().__init__(app)
        settings = get_settings()

        # 加载配置
        self.config = config or settings.security_headers

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.enabled = self.config.security_headers_enabled
        self.remove_server_header = self.config.remove_server_header
        self.csp_policy = csp_policy or self.config.csp_policy

        # 基础安全头
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

        # 根据环境添加 HSTS（生产环境强制 HTTPS）
        if settings.app.env == "production":
            self.security_headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        # 内容安全策略
        if self.csp_policy:
            self.security_headers["Content-Security-Policy"] = self.csp_policy
        else:
            # 默认 CSP 策略
            self.security_headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 添加安全头（如果启用）
        if self.enabled:
            for header, value in self.security_headers.items():
                response.headers[header] = value

        # 移除服务器信息
        if self.remove_server_header and 'server' in response.headers:
            del response.headers['server']

        return response


class IPAccessMiddleware(BaseHTTPMiddleware):
    """
    IP访问控制中间件

    支持白名单和黑名单，支持 CIDR 表示法。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[IPAccessConfig] = None,
            whitelist: Optional[Union[Set[str], List[str]]] = None,
            blacklist: Optional[Union[Set[str], List[str]]] = None,
            enable_whitelist: Optional[bool] = None,
            enable_blacklist: Optional[bool] = None
    ):
        """
        初始化 IP 访问控制中间件

        参数:
            app: ASGI 应用
            config: IP访问控制配置对象
            whitelist: 白名单 IP 集合（支持单个IP或CIDR）
            blacklist: 黑名单 IP 集合（支持单个IP或CIDR）
            enable_whitelist: 是否启用白名单
            enable_blacklist: 是否启用黑名单
        """
        super().__init__(app)
        settings = get_settings()

        # 加载配置
        self.config = config or settings.ip_access

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.whitelist_ips = whitelist if whitelist is not None else self.config.ip_whitelist
        self.blacklist_ips = blacklist if blacklist is not None else self.config.ip_blacklist
        self.enable_whitelist = enable_whitelist if enable_whitelist is not None else self.config.ip_whitelist_enabled
        self.enable_blacklist = enable_blacklist if enable_blacklist is not None else self.config.ip_blacklist_enabled

        # 初始化白名单网络对象
        self.whitelist_networks: Set[ipaddress._BaseNetwork] = set()
        for ip in self.whitelist_ips:
            try:
                # 支持 CIDR 表示法
                if '/' in ip:
                    self.whitelist_networks.add(ipaddress.ip_network(ip, strict=False))
                else:
                    self.whitelist_networks.add(ipaddress.ip_network(f"{ip}/32"))
            except ValueError as e:
                logger.debug("无效的IP白名单配置: %s, 错误: %s", ip, e)

        # 初始化黑名单网络对象
        self.blacklist_networks: Set[ipaddress._BaseNetwork] = set()
        for ip in self.blacklist_ips:
            try:
                if '/' in ip:
                    self.blacklist_networks.add(ipaddress.ip_network(ip, strict=False))
                else:
                    self.blacklist_networks.add(ipaddress.ip_network(f"{ip}/32"))
            except ValueError as e:
                logger.debug("无效的IP黑名单配置: %s, 错误: %s", ip, e)

        self.whitelist_enabled = self.enable_whitelist and len(self.whitelist_networks) > 0
        self.blacklist_enabled = self.enable_blacklist and len(self.blacklist_networks) > 0

    def _is_ip_allowed(self, ip_str: str) -> bool:
        """检查IP是否允许访问"""
        try:
            client_ip = ipaddress.ip_address(ip_str)

            # 检查黑名单（优先级更高）
            if self.blacklist_enabled:
                for network in self.blacklist_networks:
                    if client_ip in network:
                        return False

            # 检查白名单
            if self.whitelist_enabled:
                for network in self.whitelist_networks:
                    if client_ip in network:
                        return True
                return False

            # 如果没有启用白名单，默认允许
            return True

        except ValueError:
            # 无效的IP地址，拒绝访问
            return False

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        # 如果没有启用任何控制，直接放行
        if not self.whitelist_enabled and not self.blacklist_enabled:
            return await call_next(request)

        # 获取客户端真实IP
        client_ip = self._get_client_ip(request)

        # 检查IP是否允许访问
        if not self._is_ip_allowed(client_ip):
            request_id = context.get_request_id()
            trace_id = context.get_trace_id()
            span_id = context.get_span_id()
            parent_span_id = context.get_parent_span_id()

            log_audit(
                action=AuditAction.IP_BLOCKED.value,
                user_id="anonymous",
                ip_address=client_ip,
                details={
                    "path": request.url.path,
                    "method": request.method,
                    "user_agent": request.headers.get("user-agent"),
                    "whitelist_enabled": self.whitelist_enabled,
                    "blacklist_enabled": self.blacklist_enabled,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.debug(
                "IP被阻止: %s, 路径: %s %s",
                client_ip, request.method, request.url.path
            )

            raise HTTPException(
                status_code=403,
                detail="IP未授权访问"
            )

        return await call_next(request)


# 保留 IPWhitelistMiddleware 作为别名（向后兼容）
IPWhitelistMiddleware = IPAccessMiddleware


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    请求大小限制中间件

    限制请求体大小，防止恶意大请求消耗资源。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[RequestSizeConfig] = None,
            max_size: Optional[int] = None,
            exclude_paths: Optional[List[str]] = None
    ):
        """
        初始化请求大小限制中间件

        参数:
            app: ASGI 应用
            config: 请求大小限制配置对象
            max_size: 最大请求体大小（字节）
            exclude_paths: 排除大小限制的路径列表
        """
        super().__init__(app)
        settings = get_settings()

        # 加载配置
        self.config = config or settings.request_size

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.max_size = max_size if max_size is not None else self.config.max_request_size
        self.exclude_paths = exclude_paths or self.config.size_limit_exclude_paths
        self.max_size_mb = self.max_size / 1024 / 1024

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除大小限制"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    async def dispatch(self, request: Request, call_next):
        # 检查是否排除
        if self._should_exclude(request.url.path):
            return await call_next(request)

        # 检查 Content-Length
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size:
                    request_id = context.get_request_id()
                    trace_id = context.get_trace_id()
                    span_id = context.get_span_id()
                    parent_span_id = context.get_parent_span_id()

                    log_audit(
                        action=AuditAction.REQUEST_TOO_LARGE.value,
                        user_id="anonymous",
                        ip_address=self._get_client_ip(request),
                        details={
                            "path": request.url.path,
                            "method": request.method,
                            "size": size,
                            "max_size": self.max_size,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    raise HTTPException(
                        status_code=413,
                        detail=f"请求体过大，最大允许 {self.max_size_mb:.0f}MB"
                    )
            except ValueError:
                pass

        return await call_next(request)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    请求验证中间件

    验证请求的合法性，包括时间戳验证（防重放）和签名验证（防篡改）。
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[RequestValidationConfig] = None,
            enable_timestamp: Optional[bool] = None,
            enable_signature: Optional[bool] = None,
            timestamp_max_age: Optional[int] = None,
            exclude_paths: Optional[List[str]] = None
    ):
        """
        初始化请求验证中间件

        参数:
            app: ASGI 应用
            config: 请求验证配置对象
            enable_timestamp: 是否启用时间戳验证
            enable_signature: 是否启用签名验证
            timestamp_max_age: 时间戳最大有效期（秒）
            exclude_paths: 排除验证的路径列表
        """
        super().__init__(app)
        settings = get_settings()

        # 加载配置
        self.config = config or settings.request_validation

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.enable_timestamp = enable_timestamp if enable_timestamp is not None else self.config.enable_timestamp_validation
        self.enable_signature = enable_signature if enable_signature is not None else self.config.enable_signature_validation
        self.timestamp_max_age = timestamp_max_age if timestamp_max_age is not None else self.config.timestamp_max_age
        self.exclude_paths = exclude_paths or self.config.validation_exclude_paths
        self.settings = get_settings()

    def _should_exclude(self, path: str) -> bool:
        """检查是否应该排除验证"""
        for exclude_path in self.exclude_paths:
            if path.startswith(exclude_path):
                return True
        return False

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    async def dispatch(self, request: Request, call_next):
        # 检查是否排除
        if self._should_exclude(request.url.path):
            return await call_next(request)

        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        client_ip = self._get_client_ip(request)

        # 验证请求时间戳（防止重放攻击）
        if self.enable_timestamp:
            timestamp = request.headers.get("X-Timestamp")
            if timestamp:
                try:
                    request_time = int(timestamp)
                    current_time = int(time.time())

                    time_diff = abs(current_time - request_time)
                    if time_diff > self.timestamp_max_age:
                        log_audit(
                            action=AuditAction.INVALID_TIMESTAMP.value,
                            user_id="anonymous",
                            ip_address=client_ip,
                            details={
                                "path": request.url.path,
                                "method": request.method,
                                "timestamp": timestamp,
                                "current_time": current_time,
                                "age": time_diff,
                                "max_age": self.timestamp_max_age,
                                "trace_id": trace_id,
                                "span_id": span_id,
                                "parent_span_id": parent_span_id
                            },
                            request_id=request_id
                        )

                        raise HTTPException(
                            status_code=400,
                            detail=f"请求时间戳无效或已过期 (差值: {time_diff}秒)"
                        )
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail="无效的时间戳格式"
                    )
            elif self.enable_signature:
                # 如果启用签名验证但没有时间戳，拒绝请求
                raise HTTPException(
                    status_code=400,
                    detail="缺少 X-Timestamp 头"
                )

        # 验证请求签名
        if self.enable_signature:
            signature = request.headers.get("X-Signature")
            if not signature:
                raise HTTPException(
                    status_code=400,
                    detail="缺少 X-Signature 头"
                )

            await self._verify_signature(request, signature, client_ip, request_id, trace_id, span_id, parent_span_id)

        return await call_next(request)

    async def _verify_signature(
            self,
            request: Request,
            signature: str,
            client_ip: Optional[str],
            request_id: str,
            trace_id: str,
            span_id: str,
            parent_span_id: str
    ):
        """验证请求签名

        使用 HMAC-SHA256 验证请求签名，防止请求被篡改。

        签名算法：
            message = method + path + timestamp + body
            signature = HMAC-SHA256(secret, message)
        """
        try:
            # 获取请求体（需要确保可以多次读取）
            body_bytes = await request.body()
            body = body_bytes.decode('utf-8') if body_bytes else ""

            # 构建签名字符串
            method = request.method
            path = request.url.path
            timestamp = request.headers.get("X-Timestamp", "")

            message = f"{method}{path}{timestamp}{body}"

            # 计算期望签名
            expected = hmac.new(
                self.settings.auth.jwt_secret_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            # 安全比较签名（防止时序攻击）
            if not hmac.compare_digest(signature.lower(), expected.lower()):
                log_audit(
                    action=AuditAction.INVALID_SIGNATURE.value,
                    user_id="anonymous",
                    ip_address=client_ip,
                    details={
                        "path": request.url.path,
                        "method": request.method,
                        "signature": signature[:16] + "..." if signature else None,
                        "expected_prefix": expected[:16] + "...",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                logger.debug(
                    "无效签名: %s %s",
                    request.method, request.url.path
                )

                raise HTTPException(
                    status_code=400,
                    detail="无效的请求签名"
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.debug("签名验证失败: %s", e)
            raise HTTPException(
                status_code=400,
                detail="签名验证失败"
            )


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    组合安全中间件

    整合所有安全功能，简化配置。
    """

    def __init__(
            self,
            app: ASGIApp,
            enable_headers: Optional[bool] = None,
            enable_ip_access: Optional[bool] = None,
            enable_size_limit: bool = True,
            enable_timestamp_validation: Optional[bool] = None,
            enable_signature_validation: Optional[bool] = None,
            **kwargs
    ):
        super().__init__(app)
        settings = get_settings()

        # 保存配置
        self.enable_headers = enable_headers if enable_headers is not None else settings.security_headers.security_headers_enabled
        self.enable_ip_access = enable_ip_access if enable_ip_access is not None else (
                settings.ip_access.ip_whitelist_enabled or settings.ip_access.ip_blacklist_enabled
        )
        self.enable_size_limit = enable_size_limit
        self.enable_timestamp_validation = enable_timestamp_validation if enable_timestamp_validation is not None else settings.request_validation.enable_timestamp_validation
        self.enable_signature_validation = enable_signature_validation if enable_signature_validation is not None else settings.request_validation.enable_signature_validation

        # 存储 kwargs 供子中间件使用
        self.kwargs = kwargs

    async def dispatch(self, request: Request, call_next):
        # 构建中间件列表
        middlewares = []

        if self.enable_size_limit:
            middlewares.append(RequestSizeLimitMiddleware(self.app, **self.kwargs))

        if self.enable_timestamp_validation or self.enable_signature_validation:
            middlewares.append(
                RequestValidationMiddleware(
                    self.app,
                    enable_timestamp=self.enable_timestamp_validation,
                    enable_signature=self.enable_signature_validation,
                    **self.kwargs
                )
            )

        if self.enable_ip_access:
            middlewares.append(IPAccessMiddleware(self.app, **self.kwargs))

        if self.enable_headers:
            middlewares.append(SecurityHeadersMiddleware(self.app, **self.kwargs))

        # 如果没有中间件，直接处理请求
        if not middlewares:
            return await call_next(request)

        # 构建中间件链 - 使用递归方式
        async def process_chain(handlers: List[Any], req: Request, next_handler: Callable) -> Any:
            """递归处理中间件链"""
            if not handlers:
                return await next_handler(req)

            current = handlers[0]
            remaining = handlers[1:]

            # 创建下一个处理器的包装
            async def wrapper(r):
                return await process_chain(remaining, r, next_handler)

            return await current.dispatch(req, wrapper)

        # 执行中间件链
        return await process_chain(middlewares, request, call_next)


def setup_security_middleware(
        app: ASGIApp,
        **kwargs
) -> None:
    """
    设置安全中间件的便捷函数

    参数:
        app: ASGI 应用
        **kwargs: 传递给 SecurityMiddleware 的参数
    """
    app.add_middleware(SecurityMiddleware, **kwargs)