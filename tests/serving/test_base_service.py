# tests/serving/test_base_service.py

"""服务基类测试

测试 BaseModelService 的基础功能。
"""

import pytest
from unittest.mock import MagicMock, patch

from datamind.serving.base import BaseModelService


class TestBaseModelService:
    """服务基类测试"""

    @pytest.fixture
    def mock_model_loader(self):
        """Mock 模型加载器"""
        with patch('datamind.serving.base.model_loader') as mock:
            mock.is_loaded = MagicMock(return_value=True)
            mock.load_model = MagicMock(return_value=True)
            yield mock

    @pytest.fixture
    def mock_model_registry(self):
        """Mock 模型注册中心"""
        with patch('datamind.serving.base.model_registry') as mock:
            mock.list_models = MagicMock(return_value=[
                {'model_id': 'MDL_001', 'model_name': 'test_model'}
            ])
            yield mock

    def test_init_with_model_id(self, mock_model_loader):
        """测试使用指定模型ID初始化"""
        class TestService(BaseModelService):
            async def predict(self, request):
                return {}

        service = TestService(model_id="MDL_001")

        assert service.model_id == "MDL_001"
        mock_model_loader.load_model.assert_called_once_with("MDL_001", operator="system")

    def test_init_without_model_id(self, mock_model_loader, mock_model_registry):
        """测试不指定模型ID（使用生产模型）"""
        class TestService(BaseModelService):
            async def predict(self, request):
                return {}

        service = TestService()

        assert service.model_id == "MDL_001"
        mock_model_loader.load_model.assert_called_once_with("MDL_001", operator="system")

    def test_get_model_id_with_request(self):
        """测试获取模型ID（请求指定）"""
        class TestService(BaseModelService):
            async def predict(self, request):
                return {}

        service = TestService(model_id="default_model")
        result = service._get_model_id("request_model")

        assert result == "request_model"

    def test_get_model_id_without_request(self):
        """测试获取模型ID（使用默认）"""
        class TestService(BaseModelService):
            async def predict(self, request):
                return {}

        service = TestService(model_id="default_model")
        result = service._get_model_id(None)

        assert result == "default_model"

    def test_get_model_id_no_model(self):
        """测试没有模型ID"""
        class TestService(BaseModelService):
            async def predict(self, request):
                return {}

        service = TestService(model_id=None)

        with pytest.raises(ValueError) as exc:
            service._get_model_id(None)
        assert "未指定模型ID" in str(exc.value)