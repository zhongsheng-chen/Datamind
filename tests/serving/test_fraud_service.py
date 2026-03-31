# tests/serving/test_fraud_service.py

"""反欺诈服务测试

测试 FraudService 的各项功能，包括预测、健康检查等。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from datamind.serving.fraud_service import FraudService
from datamind.core.common.exceptions import ModelNotFoundException, ModelInferenceException


class TestFraudService:
    """反欺诈服务测试类"""

    @pytest.fixture
    def mock_inference_engine(self):
        """Mock 推理引擎"""
        with patch('datamind.serving.base.inference_engine') as mock:
            mock.predict_fraud = AsyncMock(return_value={
                'fraud_probability': 0.12,
                'risk_score': 12.0,
                'risk_factors': [{'factor': 'high_amount', 'value': 10000, 'weight': 0.8}],
                'model_id': 'MDL_002',
                'model_version': '1.0.0',
                'timestamp': datetime.now().isoformat(),
                'processing_time_ms': 6.2,
                'from_cache': False
            })
            yield mock

    @pytest.fixture
    def mock_model_loader(self):
        """Mock 模型加载器"""
        with patch('datamind.serving.base.model_loader') as mock:
            mock.is_loaded = MagicMock(return_value=True)
            mock.load_model = MagicMock(return_value=True)
            yield mock

    @pytest.fixture
    def service(self, mock_inference_engine, mock_model_loader):
        """创建反欺诈服务实例"""
        service = FraudService()
        service.engine = mock_inference_engine
        yield service

    @pytest.mark.asyncio
    async def test_predict_success(self, service, mock_inference_engine):
        """测试成功预测"""
        request = {
            "application_id": "APP_001",
            "features": {"amount": 10000, "ip_risk": 0.8},
            "model_id": "MDL_002"
        }

        response = await service.predict(request)

        assert response['probability'] == 0.12
        assert response['risk_score'] == 12.0
        assert len(response['risk_factors']) == 1
        assert response['risk_factors'][0]['factor'] == 'high_amount'
        assert response['model_id'] == 'MDL_002'
        assert response['application_id'] == 'APP_001'
        assert 'processing_time_ms' in response

        mock_inference_engine.predict_fraud.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_without_model_id(self, service, mock_inference_engine):
        """测试不指定模型ID（使用默认模型）"""
        request = {
            "application_id": "APP_001",
            "features": {"amount": 10000, "ip_risk": 0.8}
        }

        response = await service.predict(request)

        assert response['model_id'] == 'MDL_002'
        mock_inference_engine.predict_fraud.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_missing_application_id(self, service):
        """测试缺少 application_id"""
        request = {
            "features": {"amount": 10000, "ip_risk": 0.8}
        }

        with pytest.raises(ValueError) as exc:
            await service.predict(request)
        assert "application_id" in str(exc.value)

    @pytest.mark.asyncio
    async def test_predict_missing_features(self, service):
        """测试缺少 features"""
        request = {
            "application_id": "APP_001"
        }

        with pytest.raises(ValueError) as exc:
            await service.predict(request)
        assert "features" in str(exc.value)

    @pytest.mark.asyncio
    async def test_predict_model_not_found(self, service, mock_inference_engine):
        """测试模型不存在"""
        mock_inference_engine.predict_fraud.side_effect = ModelNotFoundException("模型不存在")

        request = {
            "application_id": "APP_001",
            "features": {"amount": 10000, "ip_risk": 0.8},
            "model_id": "INVALID"
        }

        with pytest.raises(ModelNotFoundException):
            await service.predict(request)

    @pytest.mark.asyncio
    async def test_predict_inference_error(self, service, mock_inference_engine):
        """测试推理错误"""
        mock_inference_engine.predict_fraud.side_effect = ModelInferenceException("推理失败")

        request = {
            "application_id": "APP_001",
            "features": {"amount": 10000, "ip_risk": 0.8},
            "model_id": "MDL_002"
        }

        with pytest.raises(ModelInferenceException):
            await service.predict(request)

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """测试健康检查"""
        response = await service.health()

        assert response['status'] == 'healthy' or response['status'] == 'degraded'
        assert 'model_id' in response
        assert response['service'] == 'fraud_service'
        assert response['version'] == '1.0.0'

    @pytest.mark.asyncio
    async def test_predict_with_cache_hit(self, service, mock_inference_engine):
        """测试缓存命中"""
        mock_inference_engine.predict_fraud.return_value['from_cache'] = True

        request = {
            "application_id": "APP_001",
            "features": {"amount": 10000, "ip_risk": 0.8},
            "model_id": "MDL_002"
        }

        response = await service.predict(request)

        assert response['from_cache'] is True