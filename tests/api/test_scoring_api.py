# tests/api/test_scoring_api.py
"""测试评分卡 API 路由"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime

from datamind.api.routes.scoring_api import router
from datamind.api.dependencies import get_current_user, get_model
from datamind.core.domain.enums import TaskType


class TestScoringAPI:
    """测试评分卡 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/scoring")
        return TestClient(app)

    @pytest.fixture
    def mock_current_user(self):
        """Mock 当前用户"""

        async def mock_user():
            return {
                "user_id": "test_user",
                "roles": ["user"],
                "permissions": ["predict"],
                "authenticated": True
            }

        return mock_user

    @pytest.fixture
    def mock_model(self):
        """Mock 模型"""
        mock = MagicMock()
        mock.predict.return_value = [0.05]
        return mock

    @patch('datamind.api.routes.scoring_api.get_model')
    @patch('datamind.api.routes.scoring_api.get_current_user')
    @patch('datamind.api.routes.scoring_api.inference_engine')
    def test_predict_scorecard_success(
            self, mock_inference, mock_current_user, mock_get_model, client
    ):
        """测试评分卡预测成功"""
        mock_current_user.return_value = {"user_id": "test_user", "roles": ["user"]}
        mock_get_model.return_value = MagicMock()

        mock_inference.predict_scorecard.return_value = {
            "default_probability": 0.05,
            "total_score": 720.5,
            "feature_scores": {"age": 35, "income": 50000},
            "model_id": "MDL_123",
            "model_version": "1.0.0",
            "application_id": "APP_001",
            "processing_time_ms": 45.2,
            "timestamp": datetime.now().isoformat()
        }

        response = client.post(
            "/api/v1/scoring/predict",
            json={
                "model_id": "MDL_123",
                "features": {"age": 35, "income": 50000},
                "application_id": "APP_001"
            },
            headers={"Authorization": "Bearer test_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_probability"] == 0.05
        assert data["total_score"] == 720.5
        assert data["model_id"] == "MDL_123"

    @patch('datamind.api.routes.scoring_api.inference_engine')
    def test_predict_scorecard_missing_features(self, mock_inference, client):
        """测试缺少特征"""
        response = client.post(
            "/api/v1/scoring/predict",
            json={
                "model_id": "MDL_123",
                "features": {},
                "application_id": "APP_001"
            },
            headers={"Authorization": "Bearer test_key"}
        )

        assert response.status_code == 422  # Validation error

    def test_predict_scorecard_unauthorized(self, client):
        """测试未认证"""
        response = client.post(
            "/api/v1/scoring/predict",
            json={
                "model_id": "MDL_123",
                "features": {"age": 35},
                "application_id": "APP_001"
            }
        )

        assert response.status_code == 401


class TestFraudAPI:
    """测试反欺诈 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi import FastAPI
        app = FastAPI()
        from datamind.api.routes.fraud_api import router
        app.include_router(router, prefix="/api/v1/fraud")
        return TestClient(app)

    @patch('datamind.api.routes.fraud_api.inference_engine')
    def test_predict_fraud_success(self, mock_inference, client):
        """测试反欺诈预测成功"""
        mock_inference.predict_fraud.return_value = {
            "fraud_probability": 0.12,
            "risk_score": 12.0,
            "risk_factors": [],
            "model_id": "MDL_456",
            "model_version": "1.0.0",
            "application_id": "APP_002",
            "processing_time_ms": 38.5,
            "timestamp": datetime.now().isoformat()
        }

        response = client.post(
            "/api/v1/fraud/predict",
            json={
                "model_id": "MDL_456",
                "features": {"amount": 10000, "ip_risk": 0.8},
                "application_id": "APP_002"
            },
            headers={"Authorization": "Bearer test_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["fraud_probability"] == 0.12
        assert data["risk_score"] == 12.0


class TestModelAPI:
    """测试模型管理 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi import FastAPI
        app = FastAPI()
        from datamind.api.routes.model_api import router
        app.include_router(router, prefix="/api/v1/models")
        return TestClient(app)

    @patch('datamind.api.routes.model_api.model_registry')
    @patch('datamind.api.routes.model_api.get_current_user')
    def test_list_models(self, mock_current_user, mock_registry, client):
        """测试列出模型"""
        mock_current_user.return_value = {"user_id": "admin", "roles": ["admin"]}
        mock_registry.list_models.return_value = [
            {
                "model_id": "MDL_123",
                "model_name": "test_model",
                "model_version": "1.0.0",
                "task_type": "scoring",
                "status": "active",
                "created_at": datetime.now().isoformat()
            }
        ]

        response = client.get(
            "/api/v1/models/",
            headers={"Authorization": "Bearer admin_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["model_id"] == "MDL_123"

    @patch('datamind.api.routes.model_api.model_registry')
    @patch('datamind.api.routes.model_api.get_current_user')
    def test_get_model_info(self, mock_current_user, mock_registry, client):
        """测试获取模型信息"""
        mock_current_user.return_value = {"user_id": "user", "roles": ["user"]}
        mock_registry.get_model_info.return_value = {
            "model_id": "MDL_123",
            "model_name": "test_model",
            "model_version": "1.0.0",
            "task_type": "scoring",
            "input_features": ["age", "income"],
            "status": "active"
        }

        response = client.get(
            "/api/v1/models/MDL_123",
            headers={"Authorization": "Bearer test_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == "MDL_123"
        assert data["model_name"] == "test_model"


class TestManagementAPI:
    """测试管理 API"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        from fastapi import FastAPI
        app = FastAPI()
        from datamind.api.routes.management_api import router
        app.include_router(router, prefix="/api/v1/management")
        return TestClient(app)

    @patch('datamind.api.routes.management_api.model_loader')
    @patch('datamind.api.routes.management_api.get_current_user')
    def test_get_cache_stats(self, mock_current_user, mock_loader, client):
        """测试获取缓存统计"""
        mock_current_user.return_value = {"user_id": "admin", "roles": ["admin"]}
        mock_loader.get_cache_stats.return_value = {
            "cache_size": 10,
            "cache_max_size": 100,
            "cache_ttl": 3600,
            "cache_hits": 100,
            "cache_misses": 50,
            "cache_hit_rate": 0.666
        }

        response = client.get(
            "/api/v1/management/cache/stats",
            headers={"Authorization": "Bearer admin_key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cache_size"] == 10
        assert data["cache_hit_rate"] == 0.666

    @patch('datamind.api.routes.management_api.model_loader')
    @patch('datamind.api.routes.management_api.get_current_user')
    def test_clear_cache(self, mock_current_user, mock_loader, client):
        """测试清除缓存"""
        mock_current_user.return_value = {"user_id": "admin", "roles": ["admin"]}

        response = client.post(
            "/api/v1/management/cache/clear",
            headers={"Authorization": "Bearer admin_key"}
        )

        assert response.status_code == 200
        mock_loader.clear_cache.assert_called_once()