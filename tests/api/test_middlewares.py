# tests/api/test_middlewares.py

"""中间件模块完整测试

测试所有中间件的核心功能：
  - LoggingMiddleware: 日志记录、请求ID生成、敏感数据脱敏
  - RateLimitMiddleware: 限流、不同角色限流、IP限流
  - CORSMiddleware: CORS预检请求、实际请求、配置验证
  - SecurityHeadersMiddleware: 安全头、CSP策略
  - AuthenticationMiddleware: JWT认证、API Key认证、Basic Auth
  - IPAccessMiddleware: IP白名单、黑名单
  - RequestSizeLimitMiddleware: 请求大小限制
  - RequestValidationMiddleware: 时间戳验证、签名验证
  - PerformanceMiddleware: 性能监控
  - SecurityMiddleware: 组合安全中间件
"""

import pytest
import time
import asyncio
import json
import base64
import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware

from datamind.api.middlewares import (
    LoggingMiddleware,
    RateLimitMiddleware,
    IPRateLimitMiddleware,
    UserRateLimitMiddleware,
    CustomCORSMiddleware,
    DevelopmentCORSMiddleware,
    ProductionCORSMiddleware,
    setup_cors,
    get_cors_config,
    SecurityHeadersMiddleware,
    IPAccessMiddleware,
    RequestSizeLimitMiddleware,
    RequestValidationMiddleware,
    SecurityMiddleware,
    AuthenticationMiddleware,
    create_jwt_token,
    verify_jwt_token,
    PerformanceMiddleware,
    SlowRequestMiddleware,
)
from datamind.config import get_settings
from datamind.config.settings import RateLimitConfig, CORSConfig, PerformanceConfig
from datamind.core.domain.enums import UserRole


# ==================== Fixtures ====================

@pytest.fixture
def app():
    """创建测试应用"""
    return FastAPI()


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return TestClient(app)


@pytest.fixture
def jwt_token():
    """创建测试JWT token"""
    return create_jwt_token(
        user_id="test_user_123",
        username="testuser",
        roles=[UserRole.API_USER.value],
        permissions=["predict"]
    )


# ==================== LoggingMiddleware 测试 ====================

class TestLoggingMiddleware:
    """测试日志中间件"""

    def test_logging_middleware_basic(self, app, client):
        """测试基本日志记录"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(LoggingMiddleware, log_request_body=False, log_headers=False)

        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["message"] == "ok"

    def test_logging_middleware_with_request_id(self, app, client):
        """测试请求ID生成"""

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": getattr(request.state, "request_id", None)}

        app.add_middleware(LoggingMiddleware)

        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["request_id"] is not None

    def test_logging_middleware_exclude_paths(self, app, client):
        """测试排除路径"""

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        app.add_middleware(LoggingMiddleware, exclude_paths=["/health"])

        response = client.get("/health")
        assert response.status_code == 200

    def test_logging_middleware_with_body(self, app, client):
        """测试请求体记录"""

        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}

        app.add_middleware(LoggingMiddleware, log_request_body=True, max_body_size=1024)

        response = client.post("/test", json={"key": "value"})
        assert response.status_code == 200


# ==================== RateLimitMiddleware 测试 ====================

class TestRateLimitMiddleware:
    """测试速率限制中间件"""

    def test_rate_limit_middleware_basic(self, app, client):
        """测试基本限流功能"""
        from fastapi.exceptions import HTTPException

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            RateLimitMiddleware,
            default_limit=2,
            default_period=60,
            use_redis=False,
            enabled=True
        )

        # 前两次请求成功
        response1 = client.get("/test")
        assert response1.status_code == 200
        response2 = client.get("/test")
        assert response2.status_code == 200

        # 第三次请求被限流
        with pytest.raises(HTTPException) as exc_info:
            client.get("/test")
        assert exc_info.value.status_code == 429

    def test_rate_limit_middleware_with_headers(self, app, client):
        """测试限流响应头"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            RateLimitMiddleware,
            default_limit=5,
            default_period=60,
            use_redis=False,
            enabled=True
        )

        response = client.get("/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "5"
        assert response.headers["X-RateLimit-Remaining"] == "4"

    def test_rate_limit_middleware_different_limits(self, app, client):
        """测试不同角色的限流"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        config = RateLimitConfig()
        config.rate_limit_enabled = True
        config.rate_limit_default_limit = 100
        config.rate_limit_admin_limit = 1000

        app.add_middleware(
            RateLimitMiddleware,
            config=config,
            use_redis=False
        )

        response = client.get("/test")
        assert response.status_code == 200

    def test_ip_rate_limit_middleware(self, app, client):
        """测试IP限流中间件"""
        from fastapi.exceptions import HTTPException

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            IPRateLimitMiddleware,
            default_limit=1,
            default_period=60,
            use_redis=False,
            enabled=True
        )

        response1 = client.get("/test")
        assert response1.status_code == 200

        with pytest.raises(HTTPException) as exc_info:
            client.get("/test")
        assert exc_info.value.status_code == 429


# ==================== CORS 中间件测试 ====================

class TestCORSMiddleware:
    """测试 CORS 中间件"""

    def test_cors_middleware_preflight(self, app, client):
        """测试 CORS 预检请求"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"]
        )

        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers

    def test_cors_middleware_actual_request(self, app, client):
        """测试 CORS 实际请求"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True
        )

        response = client.get(
            "/test",
            headers={"Origin": "http://localhost:3000"}
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_setup_cors_function(self, app, client):
        """测试 setup_cors 便捷函数"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=["*"],
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"]
        )

        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )

        assert response.status_code == 200

    def test_get_cors_config(self):
        """测试获取 CORS 配置"""
        config = get_cors_config()
        assert "allow_origins" in config
        assert "allow_credentials" in config


# ==================== SecurityHeadersMiddleware 测试 ====================

class TestSecurityHeadersMiddleware:
    """测试安全头中间件"""

    def test_security_headers_middleware(self, app, client):
        """测试安全头添加"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)

        response = client.get("/test")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert response.headers.get("Referrer-Policy") is not None

    def test_security_headers_with_csp(self, app, client):
        """测试自定义 CSP 策略"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy="default-src 'self'"
        )

        response = client.get("/test")
        assert response.headers.get("Content-Security-Policy") == "default-src 'self'"


# ==================== IPAccessMiddleware 测试 ====================

class TestIPAccessMiddleware:
    """测试 IP 访问控制中间件"""

    def test_ip_whitelist_allowed(self, app, client):
        """测试 IP 白名单允许访问"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            IPAccessMiddleware,
            whitelist=["127.0.0.1"],
            enable_whitelist=True
        )

        response = client.get("/test", headers={"X-Forwarded-For": "127.0.0.1"})
        assert response.status_code == 200

    def test_ip_whitelist_denied(self, app, client):
        """测试 IP 白名单拒绝访问"""
        from fastapi.exceptions import HTTPException

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            IPAccessMiddleware,
            whitelist=["192.168.1.0/24"],
            enable_whitelist=True
        )

        with pytest.raises(HTTPException) as exc_info:
            client.get("/test")
        assert exc_info.value.status_code == 403

    def test_ip_blacklist_denied(self, app, client):
        """测试 IP 黑名单拒绝访问"""
        from fastapi.exceptions import HTTPException

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            IPAccessMiddleware,
            blacklist=["127.0.0.1"],
            enable_blacklist=True
        )

        with pytest.raises(HTTPException) as exc_info:
            client.get("/test", headers={"X-Forwarded-For": "127.0.0.1"})
        assert exc_info.value.status_code == 403


# ==================== RequestSizeLimitMiddleware 测试 ====================

class TestRequestSizeLimitMiddleware:
    """测试请求大小限制中间件"""

    def test_request_size_limit_within_limit(self, app, client):
        """测试请求大小在限制内"""

        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}

        app.add_middleware(RequestSizeLimitMiddleware, max_size=1024)

        response = client.post("/test", json={"key": "value"})
        assert response.status_code == 200

    def test_request_size_limit_exceeded(self, app, client):
        """测试请求大小超过限制"""
        from fastapi.exceptions import HTTPException

        @app.post("/test")
        async def test_endpoint(data: dict):
            return {"received": data}

        app.add_middleware(RequestSizeLimitMiddleware, max_size=100)

        large_data = {"key": "x" * 200}

        with pytest.raises(HTTPException) as exc_info:
            client.post("/test", json=large_data)
        assert exc_info.value.status_code == 413

    def test_request_size_limit_exclude_paths(self, app, client):
        """测试排除路径"""

        @app.post("/upload")
        async def upload_endpoint(data: dict):
            return {"received": data}

        app.add_middleware(
            RequestSizeLimitMiddleware,
            max_size=10,
            exclude_paths=["/upload"]
        )

        large_data = {"key": "x" * 100}
        response = client.post("/upload", json=large_data)
        assert response.status_code == 200


# ==================== AuthenticationMiddleware 测试 ====================

class TestAuthenticationMiddleware:
    """测试认证中间件"""

    def test_auth_middleware_exclude_paths(self, app, client):
        """测试排除路径不需要认证"""

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        app.add_middleware(AuthenticationMiddleware)

        response = client.get("/health")
        assert response.status_code == 200

    def test_auth_middleware_missing_token(self, app, client):
        """测试缺失 token 返回 401"""
        from fastapi.exceptions import HTTPException

        @app.get("/protected")
        async def protected_endpoint():
            return {"message": "protected"}

        app.add_middleware(AuthenticationMiddleware)

        with pytest.raises(HTTPException) as exc_info:
            client.get("/protected")
        assert exc_info.value.status_code == 401

    def test_jwt_token_creation_and_verification(self):
        """测试 JWT token 创建和验证"""
        token = create_jwt_token(
            user_id="user_123",
            username="testuser",
            roles=[UserRole.ADMIN.value],
            permissions=["*"]
        )
        assert token is not None

        verified = verify_jwt_token(token)
        assert verified["valid"] is True
        assert verified["user_id"] == "user_123"
        assert verified["username"] == "testuser"

    def test_jwt_token_expired(self):
        """测试过期 token"""
        token = create_jwt_token(
            user_id="user_123",
            username="testuser",
            roles=[UserRole.API_USER.value],
            expires_delta=timedelta(seconds=-1)
        )

        verified = verify_jwt_token(token)
        assert verified["valid"] is False
        assert "过期" in verified["reason"]


# ==================== PerformanceMiddleware 测试 ====================

class TestPerformanceMiddleware:
    """测试性能监控中间件"""

    def test_performance_middleware_basic(self, app, client):
        """测试基本性能监控"""

        @app.get("/test")
        async def test_endpoint():
            await asyncio.sleep(0.01)
            return {"message": "ok"}

        app.add_middleware(
            PerformanceMiddleware,
            enable_detailed=True,
            sample_rate=1.0
        )

        response = client.get("/test")
        assert response.status_code == 200

    def test_slow_request_middleware(self, app, client):
        """测试慢请求监控"""

        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.2)
            return {"message": "slow"}

        app.add_middleware(SlowRequestMiddleware, slow_threshold=100)

        response = client.get("/slow")
        assert response.status_code == 200

    def test_performance_middleware_sample_rate(self, app, client):
        """测试采样率"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            PerformanceMiddleware,
            sample_rate=0.5
        )

        response = client.get("/test")
        assert response.status_code == 200


# ==================== SecurityMiddleware 组合测试 ====================

class TestSecurityMiddleware:
    """测试组合安全中间件"""

    def test_security_middleware_basic(self, app, client):
        """测试组合安全中间件基本功能"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(SecurityMiddleware)

        response = client.get("/test")
        assert response.status_code == 200
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_security_middleware_with_options(self, app, client):
        """测试带选项的组合安全中间件"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            SecurityMiddleware,
            enable_headers=True,
            enable_ip_access=False,
            enable_size_limit=True,
            enable_timestamp_validation=False
        )

        response = client.get("/test")
        assert response.status_code == 200


# ==================== RequestValidationMiddleware 测试 ====================

class TestRequestValidationMiddleware:
    """测试请求验证中间件"""

    def test_timestamp_validation(self, app, client):
        """测试时间戳验证"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            RequestValidationMiddleware,
            enable_timestamp=True,
            timestamp_max_age=60
        )

        current_timestamp = int(time.time())
        response = client.get(
            "/test",
            headers={"X-Timestamp": str(current_timestamp)}
        )
        assert response.status_code == 200

    def test_expired_timestamp(self, app, client):
        """测试过期时间戳"""
        from fastapi.exceptions import HTTPException

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(
            RequestValidationMiddleware,
            enable_timestamp=True,
            timestamp_max_age=10
        )

        expired_timestamp = int(time.time()) - 100

        with pytest.raises(HTTPException) as exc_info:
            client.get(
                "/test",
                headers={"X-Timestamp": str(expired_timestamp)}
            )
        assert exc_info.value.status_code == 400


# ==================== 集成测试 ====================

class TestMiddlewareIntegration:
    """中间件集成测试"""

    def test_multiple_middlewares(self, app, client):
        """测试多个中间件协同工作"""

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(
            RateLimitMiddleware,
            default_limit=10,
            default_period=60,
            use_redis=False,
            enabled=True
        )
        app.add_middleware(LoggingMiddleware, log_request_body=False)

        response = client.get("/test")
        assert response.status_code == 200
        assert "X-Content-Type-Options" in response.headers
        assert "X-RateLimit-Limit" in response.headers

    def test_cors_with_authentication(self, app, client):
        """测试 CORS 和认证中间件组合"""
        from fastapi.exceptions import HTTPException

        @app.get("/protected")
        async def protected_endpoint():
            return {"message": "protected"}

        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["*"]
        )
        app.add_middleware(AuthenticationMiddleware)

        # CORS 预检请求 - 不需要认证
        response = client.options(
            "/protected",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code == 200

        # 实际请求需要认证
        with pytest.raises(HTTPException) as exc_info:
            client.get(
                "/protected",
                headers={"Origin": "http://localhost:3000"}
            )
        assert exc_info.value.status_code == 401


# ==================== 异常测试 ====================

class TestExceptionHandling:
    """异常处理测试"""

    def test_middleware_exception_propagation(self, app, client):
        """测试中间件异常传播"""

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=500, detail="Internal Error")

        app.add_middleware(LoggingMiddleware)

        response = client.get("/error")
        assert response.status_code == 500