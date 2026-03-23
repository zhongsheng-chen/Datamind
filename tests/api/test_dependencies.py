# tests/api/test_dependencies.py

"""测试 API 依赖注入模块"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.testclient import TestClient
from typing import Any

from datamind.api.dependencies import (
    get_database,
    get_api_key,
    verify_api_key,
    verify_oauth2_token,
    get_current_user,
    require_admin,
    require_permission,
    get_model,
    get_model_metadata,
    get_ab_test_assignment,
    set_request_context,
    get_request_id,
    get_trace_id,
    get_span_id,
    get_parent_span_id,
    get_pagination_params,
    get_offset_limit,
    get_pagination_response,
    check_rate_limit,
    get_rate_limit_info,
    log_request,
    RateLimiter,
    PaginationParams
)
from datamind.core.logging import context
from datamind.core.domain.enums import ABTestStatus, UserRole


class TestGetAPIKey:
    """测试获取 API Key 函数"""

    def test_get_api_key_from_authorization_header(self):
        """测试从 Authorization header 获取 API Key"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}

        client = TestClient(app)
        response = client.get("/test", headers={"Authorization": "Bearer test_api_key_123"})

        assert response.status_code == 200
        assert response.json()["api_key"] == "test_api_key_123"

    def test_get_api_key_from_x_api_key_header(self):
        """测试从 X-API-Key header 获取 API Key"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}

        client = TestClient(app)
        response = client.get("/test", headers={"X-API-Key": "test_api_key_456"})

        assert response.status_code == 200
        assert response.json()["api_key"] == "test_api_key_456"

    def test_get_api_key_no_header(self):
        """测试无 API Key 头"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["api_key"] is None

    def test_get_api_key_prefers_authorization(self):
        """测试 Authorization 优先于 X-API-Key"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(api_key: str = Depends(get_api_key)):
            return {"api_key": api_key}

        client = TestClient(app)
        response = client.get("/test", headers={
            "Authorization": "Bearer test_api_key_123",
            "X-API-Key": "test_api_key_456"
        })

        assert response.status_code == 200
        assert response.json()["api_key"] == "test_api_key_123"


class TestVerifyAPIKey:
    """测试 API Key 验证"""

    @patch('datamind.api.dependencies.get_settings')
    def test_verify_api_key_missing(self, mock_settings):
        """测试缺失 API Key"""
        mock_settings.return_value.auth.api_key_enabled = True

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(verify_api_key)):
            return user

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 401
        assert "Missing API Key" in response.json()["detail"]

    @patch('datamind.api.dependencies.get_settings')
    def test_verify_api_key_disabled(self, mock_settings):
        """测试 API Key 认证禁用"""
        mock_settings.return_value.auth.api_key_enabled = False

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(verify_api_key)):
            return user

        client = TestClient(app)
        response = client.get("/test", headers={"Authorization": "Bearer any_key"})

        assert response.status_code == 200
        assert response.json()["user_id"] == "system"

    @patch('datamind.api.dependencies.get_settings')
    def test_verify_api_key_valid(self, mock_settings):
        """测试有效的 API Key"""
        mock_settings.return_value.auth.api_key_enabled = True

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(verify_api_key)):
            return user

        client = TestClient(app)

        # 直接 mock verify_api_key 依赖
        async def mock_verify_api_key():
            return {
                "api_key": "test_key",
                "user_id": "test_user",
                "username": "test_user",
                "roles": [UserRole.API_USER.value],
                "permissions": ["predict"],
                "authenticated": True
            }

        app.dependency_overrides[verify_api_key] = mock_verify_api_key

        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["user_id"] == "test_user"

        app.dependency_overrides.clear()


class TestGetCurrentUser:
    """测试获取当前用户"""

    def test_get_current_user(self):
        """测试获取当前用户"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(get_current_user)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user", "username": "test_user", "roles": [UserRole.API_USER.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["user_id"] == "test_user"

        app.dependency_overrides.clear()


class TestRequireAdmin:
    """测试管理员权限"""

    def test_require_admin_success(self):
        """测试管理员权限成功"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(require_admin)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "admin", "roles": [UserRole.ADMIN.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.log_audit')
    def test_require_admin_failed(self, mock_audit):
        """测试非管理员用户"""
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(require_admin)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "user", "roles": [UserRole.API_USER.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 403

        app.dependency_overrides.clear()


class TestRequirePermission:
    """测试权限检查"""

    def test_require_permission_admin(self):
        """测试管理员拥有所有权限"""
        app = FastAPI()

        async def permission_dep(user: dict = Depends(get_current_user)):
            return await require_permission("any_permission", user)

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(permission_dep)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "admin", "roles": [UserRole.ADMIN.value], "permissions": []}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()

    def test_require_permission_success(self):
        """测试拥有权限"""
        app = FastAPI()

        async def permission_dep(user: dict = Depends(get_current_user)):
            return await require_permission("predict", user)

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(permission_dep)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "user", "roles": [UserRole.API_USER.value], "permissions": ["predict"]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.log_audit')
    def test_require_permission_failed(self, mock_audit):
        """测试无权限"""
        app = FastAPI()

        async def permission_dep(user: dict = Depends(get_current_user)):
            return await require_permission("predict", user)

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(permission_dep)):
            return user

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "user", "roles": [UserRole.API_USER.value], "permissions": []}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 403

        app.dependency_overrides.clear()


class TestGetModel:
    """测试获取模型"""

    @patch('datamind.api.dependencies.model_loader')
    def test_get_model_loaded(self, mock_loader):
        """测试获取已加载的模型"""
        mock_model = MagicMock()
        mock_loader.get_model.return_value = mock_model

        app = FastAPI()

        @app.get("/test/{model_id}")
        async def test_endpoint(model: Any = Depends(get_model)):
            return {"loaded": True}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        # 创建 mock request 并注入
        async def mock_request():
            return MagicMock(headers={})

        app.dependency_overrides[Request] = mock_request

        response = client.get("/test/model_123")

        assert response.status_code == 200
        mock_loader.get_model.assert_called_with("model_123")

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.model_loader')
    def test_get_model_not_loaded_load_success(self, mock_loader):
        """测试模型未加载，加载成功"""
        mock_model = MagicMock()
        mock_loader.get_model.side_effect = [None, mock_model]
        mock_loader.load_model.return_value = True

        app = FastAPI()

        @app.get("/test/{model_id}")
        async def test_endpoint(model: Any = Depends(get_model)):
            return {"loaded": True}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        async def mock_request():
            return MagicMock(headers={})

        app.dependency_overrides[Request] = mock_request

        response = client.get("/test/model_123")

        assert response.status_code == 200
        mock_loader.load_model.assert_called_once()

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.model_loader')
    def test_get_model_load_failed(self, mock_loader):
        """测试模型加载失败 - 应该返回 404"""
        mock_loader.get_model.return_value = None
        mock_loader.load_model.return_value = False

        app = FastAPI()

        @app.get("/test/{model_id}")
        async def test_endpoint(model: Any = Depends(get_model)):
            return {"loaded": True}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        async def mock_request():
            return MagicMock(headers={})

        app.dependency_overrides[Request] = mock_request

        response = client.get("/test/model_123")

        assert response.status_code == 404
        assert "Model not found" in response.json()["detail"]

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.model_loader')
    def test_get_model_load_exception(self, mock_loader):
        """测试模型加载时抛出异常"""
        mock_loader.get_model.return_value = None
        mock_loader.load_model.side_effect = Exception("数据库连接失败")

        app = FastAPI()

        @app.get("/test/{model_id}")
        async def test_endpoint(model: Any = Depends(get_model)):
            return {"loaded": True}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        async def mock_request():
            return MagicMock(headers={})

        app.dependency_overrides[Request] = mock_request

        response = client.get("/test/model_123")

        assert response.status_code == 500
        assert "Failed to load model" in response.json()["detail"]

        app.dependency_overrides.clear()


class TestGetABTestAssignment:
    """测试 A/B 测试分配"""

    @patch('datamind.api.dependencies.ab_test_manager')
    @patch('datamind.api.dependencies.get_settings')
    def test_get_ab_test_assignment_success(self, mock_settings, mock_ab_manager):
        """测试成功获取 A/B 测试分配"""
        mock_settings.return_value.ab_test.enabled = True
        mock_ab_manager.get_assignment.return_value = {
            "test_id": "test_123",
            "group_name": "A",
            "model_id": "model_123",
            "in_test": True
        }

        app = FastAPI()

        @app.get("/test/{test_id}/{user_id}")
        async def test_endpoint(assignment: dict = Depends(get_ab_test_assignment)):
            return assignment

        client = TestClient(app)
        response = client.get("/test/test_123/user_123")

        assert response.status_code == 200
        assert response.json()["group_name"] == "A"

    @patch('datamind.api.dependencies.get_settings')
    def test_get_ab_test_assignment_disabled(self, mock_settings):
        """测试 A/B 测试禁用"""
        mock_settings.return_value.ab_test.enabled = False

        app = FastAPI()

        @app.get("/test/{test_id}/{user_id}")
        async def test_endpoint(assignment: dict = Depends(get_ab_test_assignment)):
            return assignment

        client = TestClient(app)
        response = client.get("/test/test_123/user_123")

        assert response.status_code == 200
        assert response.json()["in_test"] is False
        assert response.json()["group_name"] == "default"


class TestRequestContext:
    """测试请求上下文"""

    def test_set_request_context(self):
        """测试设置请求上下文"""
        app = FastAPI()

        @app.middleware("http")
        async def add_context(request: Request, call_next):
            await set_request_context(request)
            response = await call_next(request)
            return response

        @app.get("/test")
        async def test_endpoint(request: Request):
            return {
                "request_id": get_request_id(request),
                "trace_id": get_trace_id(request),
                "span_id": get_span_id(request),
                "parent_span_id": get_parent_span_id(request)
            }

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] is not None
        assert data["trace_id"] is not None
        assert data["span_id"] is not None
        assert "parent_span_id" in data

    def test_get_request_id(self):
        """测试获取请求ID"""
        request = MagicMock()
        request.state.request_id = "req-123"
        assert get_request_id(request) == "req-123"

    def test_get_trace_id(self):
        """测试获取 trace_id"""
        request = MagicMock()
        request.state.trace_id = "trace-456"
        assert get_trace_id(request) == "trace-456"

    def test_get_span_id(self):
        """测试获取 span_id"""
        request = MagicMock()
        request.state.span_id = "span-789"
        assert get_span_id(request) == "span-789"

    def test_get_parent_span_id(self):
        """测试获取 parent_span_id"""
        request = MagicMock()
        request.state.parent_span_id = "parent-123"
        assert get_parent_span_id(request) == "parent-123"


class TestPagination:
    """测试分页功能"""

    def test_get_pagination_params_default(self):
        """测试默认分页参数"""
        params = get_pagination_params()
        assert params.page == 1
        assert params.page_size == 20
        assert params.sort_by is None
        assert params.sort_order == "desc"

    def test_get_pagination_params_custom(self):
        """测试自定义分页参数"""
        params = get_pagination_params(page=2, page_size=50, sort_by="created_at", sort_order="asc")
        assert params.page == 2
        assert params.page_size == 50
        assert params.sort_by == "created_at"
        assert params.sort_order == "asc"

    def test_get_pagination_params_max_limit(self):
        """测试最大每页数量限制"""
        params = get_pagination_params(page_size=200)
        assert params.page_size == 100

    def test_get_offset_limit(self):
        """测试计算偏移量"""
        params = PaginationParams(page=2, page_size=20)
        offset, limit = get_offset_limit(params)
        assert offset == 20
        assert limit == 20

    def test_get_pagination_response(self):
        """测试构建分页响应"""
        items = [1, 2, 3]
        total = 100
        params = PaginationParams(page=2, page_size=20)

        response = get_pagination_response(items, total, params)

        assert response["items"] == items
        assert response["total"] == 100
        assert response["page"] == 2
        assert response["page_size"] == 20
        assert response["total_pages"] == 5
        assert response["has_next"] is True
        assert response["has_prev"] is True


class TestRateLimiter:
    """测试速率限制器"""

    @patch('datamind.api.dependencies.get_settings')
    def test_rate_limiter_memory_init(self, mock_settings):
        """测试内存限流器初始化"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        limiter = RateLimiter()
        assert limiter._use_redis is False

    @patch('datamind.api.dependencies.get_settings')
    def test_rate_limiter_check_within_limit(self, mock_settings):
        """测试未超过限制"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        limiter = RateLimiter()

        allowed, info = limiter._check_memory("test_key", limit=5, period=60)

        assert allowed is True
        assert info["limit"] == 5
        assert info["remaining"] == 4

    @patch('datamind.api.dependencies.get_settings')
    def test_rate_limiter_check_exceed_limit(self, mock_settings):
        """测试超过限制"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        limiter = RateLimiter()

        for _ in range(5):
            limiter._check_memory("test_key", limit=5, period=60)

        allowed, info = limiter._check_memory("test_key", limit=5, period=60)

        assert allowed is False
        assert info["remaining"] == 0

    @patch('datamind.api.dependencies.get_settings')
    def test_rate_limiter_reset(self, mock_settings):
        """测试重置限流器"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        limiter = RateLimiter()

        for _ in range(3):
            limiter._check_memory("test_key", limit=5, period=60)

        limiter.reset("test_key")
        allowed, _ = limiter._check_memory("test_key", limit=5, period=60)

        assert allowed is True


class TestCheckRateLimit:
    """测试速率限制检查"""

    @patch('datamind.api.dependencies.get_settings')
    @patch('datamind.api.dependencies._rate_limiter')
    def test_check_rate_limit_enabled(self, mock_limiter, mock_settings):
        """测试速率限制启用"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        mock_settings.return_value.rate_limit.rate_limit_default_limit = 100
        mock_settings.return_value.rate_limit.rate_limit_default_period = 60
        mock_limiter.check = AsyncMock(return_value=(True, {"limit": 100, "remaining": 99, "reset": 1234567890}))

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(check_rate_limit)):
            return {"status": "ok"}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user", "roles": [UserRole.API_USER.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.get_settings')
    @patch('datamind.api.dependencies._rate_limiter')
    def test_check_rate_limit_exceeded(self, mock_limiter, mock_settings):
        """测试超过速率限制"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        mock_settings.return_value.rate_limit.rate_limit_default_limit = 100
        mock_settings.return_value.rate_limit.rate_limit_default_period = 60
        mock_limiter.check = AsyncMock(return_value=(False, {"limit": 100, "remaining": 0, "reset": 1234567890}))

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(check_rate_limit)):
            return {"status": "ok"}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "test_user", "roles": [UserRole.API_USER.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        response = client.get("/test")

        assert response.status_code == 429

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.get_settings')
    def test_check_rate_limit_admin_role(self, mock_settings):
        """测试管理员角色的速率限制"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        mock_settings.return_value.rate_limit.rate_limit_admin_limit = 1000
        mock_settings.return_value.rate_limit.rate_limit_admin_period = 60

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(check_rate_limit)):
            return {"status": "ok"}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "admin", "roles": [UserRole.ADMIN.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        with patch('datamind.api.dependencies._rate_limiter') as mock_limiter:
            mock_limiter.check = AsyncMock(return_value=(True, {"limit": 1000, "remaining": 999, "reset": 1234567890}))
            response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()

    @patch('datamind.api.dependencies.get_settings')
    def test_check_rate_limit_developer_role(self, mock_settings):
        """测试开发者角色的速率限制"""
        mock_settings.return_value.rate_limit.rate_limit_enabled = True
        mock_settings.return_value.rate_limit.rate_limit_developer_limit = 500
        mock_settings.return_value.rate_limit.rate_limit_developer_period = 60

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(user: dict = Depends(check_rate_limit)):
            return {"status": "ok"}

        client = TestClient(app)

        async def mock_get_current_user():
            return {"user_id": "developer", "roles": [UserRole.DEVELOPER.value]}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        with patch('datamind.api.dependencies._rate_limiter') as mock_limiter:
            mock_limiter.check = AsyncMock(return_value=(True, {"limit": 500, "remaining": 499, "reset": 1234567890}))
            response = client.get("/test")

        assert response.status_code == 200

        app.dependency_overrides.clear()


class TestLogRequest:
    """测试请求日志"""

    @patch('datamind.api.dependencies.log_audit')
    def test_log_request(self, mock_audit):
        """测试记录请求日志"""
        app = FastAPI()

        @app.middleware("http")
        async def log_middleware(request: Request, call_next):
            log_request(request)
            return await call_next(request)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)

        response = client.get("/test")

        assert response.status_code == 200
        mock_audit.assert_called_once()