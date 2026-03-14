# datamind/api/middlewares/security.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from typing import Set, Optional
import hashlib
import hmac

from core.logging import log_manager, get_request_id
from config.settings import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件

    添加各种安全相关的HTTP头
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 添加安全头
        for header, value in self.security_headers.items():
            response.headers[header] = value

        return response


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    IP白名单中间件
    """

    def __init__(self, app: ASGIApp, whitelist: Set[str] = None):
        super().__init__(app)
        self.whitelist = whitelist or set(settings.TRUSTED_PROXIES)
        self.enabled = len(self.whitelist) > 0

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else None

        if client_ip not in self.whitelist:
            request_id = get_request_id()

            log_manager.log_audit(
                action="IP_BLOCKED",
                user_id="anonymous",
                ip_address=client_ip,
                details={
                    "path": request.url.path,
                    "method": request.method
                },
                request_id=request_id
            )

            raise HTTPException(status_code=403, detail="IP未授权")

        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    请求大小限制中间件
    """

    def __init__(self, app: ASGIApp, max_size: int = 10 * 1024 * 1024):  # 10MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        # 检查Content-Length
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_size:
            raise HTTPException(
                status_code=413,
                detail=f"请求体过大，最大允许 {self.max_size / 1024 / 1024}MB"
            )

        return await call_next(request)


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    请求验证中间件

    验证请求的合法性，如请求时间戳、签名等
    """

    def __init__(self, app: ASGIApp, max_age: int = 300):  # 5分钟
        super().__init__(app)
        self.max_age = max_age

    async def dispatch(self, request: Request, call_next):
        # 验证请求时间戳（防止重放攻击）
        timestamp = request.headers.get("X-Timestamp")
        if timestamp:
            try:
                request_time = int(timestamp)
                current_time = int(time.time())

                if abs(current_time - request_time) > self.max_age:
                    raise HTTPException(
                        status_code=400,
                        detail="请求时间戳无效或已过期"
                    )
            except ValueError:
                pass

        # 验证请求签名
        signature = request.headers.get("X-Signature")
        if signature and settings.API_KEY_ENABLED:
            await self._verify_signature(request, signature)

        return await call_next(request)

    async def _verify_signature(self, request: Request, signature: str):
        """验证请求签名"""
        # 获取请求体
        body = await request.body()

        # 构建签名字符串
        method = request.method
        path = request.url.path
        timestamp = request.headers.get("X-Timestamp", "")

        message = f"{method}{path}{timestamp}{body.decode()}".encode()

        # 计算期望签名
        expected = hmac.new(
            settings.JWT_SECRET_KEY.encode(),
            message,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            request_id = get_request_id()

            log_manager.log_audit(
                action="INVALID_SIGNATURE",
                user_id="anonymous",
                ip_address=request.client.host if request.client else None,
                details={
                    "path": request.url.path,
                    "method": request.method
                },
                request_id=request_id
            )

            raise HTTPException(status_code=400, detail="无效的请求签名")