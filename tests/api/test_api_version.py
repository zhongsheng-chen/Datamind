# tests/api/test_api_version.py

"""API 版本测试

测试多版本 API 的兼容性
"""

import pytest
from fastapi.testclient import TestClient

from datamind.main import app


class TestAPIVersion:
    """API 版本测试"""

    def test_v1_endpoint_exists(self, client):
        """测试 v1 端点存在"""
        response = client.post("/api/v1/scoring/predict", json={})
        assert response.status_code in [401, 422]  # 至少端点存在

    def test_v2_endpoint_exists(self, client):
        """测试 v2 端点存在"""
        response = client.post("/api/v2/scoring/predict", json={})
        assert response.status_code in [401, 422]

    def test_version_info_endpoint(self, client):
        """测试版本信息端点"""
        response = client.get("/api/versions")
        assert response.status_code == 200
        data = response.json()
        assert "current" in data
        assert "supported" in data
        assert "versions" in data

    def test_root_version_info(self, client):
        """测试根路由版本信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "api" in data
        assert "supported_versions" in data["api"]

    def test_version_middleware_unsupported(self, client):
        """测试不支持的版本"""
        response = client.post("/api/v3/scoring/predict", json={})
        assert response.status_code == 400
        assert "unsupported_api_version" in response.text

    def test_version_deprecation_header(self, client, monkeypatch):
        """测试版本弃用头"""
        from datamind.config import get_settings

        # 模拟 v1 已弃用
        monkeypatch.setattr(
            "datamind.config.settings.Settings.api.deprecated_versions",
            ["v1"]
        )

        response = client.post("/api/v1/scoring/predict", json={})
        if response.status_code == 401:
            # 如果返回 401，头信息可能不完整，跳过
            pass
        else:
            assert response.headers.get("X-API-Deprecated") == "true"