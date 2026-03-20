# Datamind/datamind/api/middlewares/security.py

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

  IPWhitelistMiddleware: IP白名单中间件
     - 限制只有白名单内的IP可以访问
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

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time
from typing import Set
import hashlib
import hmac

from datamind.core.logging import log_manager, debug_print
from datamind.core.logging import context
from datamind.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    安全头中间件

    添加各种安全相关的 HTTP 响应头，增强应用安全性。
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

    只允许白名单中的 IP 地址访问，其他 IP 返回 403。
    """

    def __init__(self, app: ASGIApp, whitelist: Set[str] = None):
        """
        初始化 IP 白名单中间件

        参数:
            app: ASGI 应用
            whitelist: 白名单 IP 集合
        """
        super().__init__(app)
        self.whitelist = whitelist or set(settings.security.trusted_proxies)
        self.enabled = len(self.whitelist) > 0

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        client_ip = request.client.host if request.client else None

        if client_ip not in self.whitelist:
            request_id = context.get_request_id()

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

    限制请求体大小，防止恶意大请求消耗资源。
    """

    def __init__(self, app: ASGIApp, max_size: int = 10 * 1024 * 1024):  # 10MB
        """
        初始化请求大小限制中间件

        参数:
            app: ASGI 应用
            max_size: 最大请求体大小（字节），默认 10MB
        """
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

    验证请求的合法性，包括时间戳验证（防重放）和签名验证（防篡改）。
    """

    def __init__(self, app: ASGIApp, max_age: int = 300):  # 5分钟
        """
        初始化请求验证中间件

        参数:
            app: ASGI 应用
            max_age: 请求时间戳最大有效期（秒），默认 300 秒（5分钟）
        """
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
        if signature and settings.auth.api_key_enabled:
            await self._verify_signature(request, signature)

        return await call_next(request)

    async def _verify_signature(self, request: Request, signature: str):
        """验证请求签名

        使用 HMAC-SHA256 验证请求签名，防止请求被篡改。

        签名算法：
            message = method + path + timestamp + body
            signature = HMAC-SHA256(secret, message)
        """
        # 获取请求体
        body = await request.body()

        # 构建签名字符串
        method = request.method
        path = request.url.path
        timestamp = request.headers.get("X-Timestamp", "")

        message = f"{method}{path}{timestamp}{body.decode()}"

        # 计算期望签名
        expected = hmac.new(
            settings.auth.jwt_secret_key.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        # 安全比较签名（防止时序攻击）
        if not hmac.compare_digest(signature, expected):
            request_id = context.get_request_id()

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