# tests/serving/test_scoring_service.py

"""评分卡服务测试

测试 ScoringService 的各项功能，包括预测、健康检查等。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from datamind.serving.scoring_service import ScoringService
from datamind.core.common.exceptions import ModelNotFoundException, ModelInferenceException


class TestScoringService:
    """评分卡服务测试类"""

    @pytest.fixture
    def mock_inference_engine(self):
        """Mock 推理引擎"""
        with patch('datamind.serving.base.inference_engine') as mock:
            # 配置 mock 返回值
            mock.predict_scorecard = AsyncMock(return_value={
                'total_score': 685.42,
                'default_probability': 0.023,
                'feature_scores': {'age': 85.2, 'income': 120.5},
                'model_id': 'MDL_001',
                'model_version': '1.0.0',
                'timestamp': datetime.now().isoformat(),
                'processing_time_ms': 8.5,
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
    def mock_ab_test_manager(self):
        """Mock A/B测试管理器"""
        with patch('datamind.serving.scoring_service.ab_test_manager') as mock:
            mock.get_assignment = MagicMock(return_value={
                'in_test': True,
                'model_id': 'MDL_002',
                'test_id': 'ABT_001',
                'group_name': 'A'
            })
            yield mock

    @pytest.fixture
    def service(self, mock_inference_engine, mock_model_loader):
        """创建评分卡服务实例"""
        with patch('datamind.serving.base.get_settings') as mock_settings:
            mock_settings.return_value.ab_test.enabled = True
            service = ScoringService()
            service.engine = mock_inference_engine
            yield service

    @pytest.mark.asyncio
    async def test_predict_success(self, service, mock_inference_engine):
        """测试成功预测"""
        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000},
            "model_id": "MDL_001"
        }

        response = await service.predict(request)

        assert response['score'] == 685.42
        assert response['probability'] == 0.023
        assert 'feature_contributions' in response
        assert response['model_id'] == 'MDL_001'
        assert response['application_id'] == 'APP_001'
        assert 'processing_time_ms' in response
        assert response['from_cache'] is False

        mock_inference_engine.predict_scorecard.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_without_model_id(self, service, mock_inference_engine):
        """测试不指定模型ID（使用默认模型）"""
        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000}
        }

        response = await service.predict(request)

        assert response['model_id'] == 'MDL_001'
        mock_inference_engine.predict_scorecard.assert_called_once()

    @pytest.mark.asyncio
    async def test_predict_with_ab_test(self, service, mock_inference_engine, mock_ab_test_manager):
        """测试 A/B 测试分流"""
        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000},
            "ab_test_id": "ABT_001"
        }

        response = await service.predict(request)

        # 验证使用了 A/B 测试分配的模型
        mock_ab_test_manager.get_assignment.assert_called_once_with(
            test_id="ABT_001",
            user_id="APP_001"
        )

        # 验证预测使用了正确的模型ID
        call_args = mock_inference_engine.predict_scorecard.call_args[1]
        assert call_args['model_id'] == 'MDL_002'

        # 验证响应包含 A/B 测试信息
        assert 'ab_test_info' in response
        assert response['ab_test_info']['test_id'] == 'ABT_001'
        assert response['ab_test_info']['group_name'] == 'A'

    @pytest.mark.asyncio
    async def test_predict_missing_application_id(self, service):
        """测试缺少 application_id"""
        request = {
            "features": {"age": 35, "income": 50000}
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
        mock_inference_engine.predict_scorecard.side_effect = ModelNotFoundException("模型不存在")

        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000},
            "model_id": "INVALID"
        }

        with pytest.raises(ModelNotFoundException):
            await service.predict(request)

    @pytest.mark.asyncio
    async def test_predict_inference_error(self, service, mock_inference_engine):
        """测试推理错误"""
        mock_inference_engine.predict_scorecard.side_effect = ModelInferenceException("推理失败")

        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000},
            "model_id": "MDL_001"
        }

        with pytest.raises(ModelInferenceException):
            await service.predict(request)

    @pytest.mark.asyncio
    async def test_health_check(self, service):
        """测试健康检查"""
        response = await service.health()

        assert response['status'] == 'healthy' or response['status'] == 'degraded'
        assert 'model_id' in response
        assert response['service'] == 'scoring_service'
        assert response['version'] == '1.0.0'

    @pytest.mark.asyncio
    async def test_predict_with_cache_hit(self, service, mock_inference_engine):
        """测试缓存命中"""
        mock_inference_engine.predict_scorecard.return_value['from_cache'] = True

        request = {
            "application_id": "APP_001",
            "features": {"age": 35, "income": 50000},
            "model_id": "MDL_001"
        }

        response = await service.predict(request)

        assert response['from_cache'] is True