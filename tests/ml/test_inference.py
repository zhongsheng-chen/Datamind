# tests/ml/test_inference.py

"""测试推理引擎"""

import pytest
import numpy as np
import pandas as pd
import math
from unittest.mock import MagicMock, patch
from datetime import datetime

from datamind.core.ml.inference import InferenceEngine, LRUCache
from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.domain.enums import TaskType, AuditAction


class TestLRUCache:
    """测试 LRU 缓存"""

    def test_init(self):
        """测试初始化"""
        cache = LRUCache(max_size=10, ttl=60)
        assert cache.max_size == 10
        assert cache.ttl == 60
        assert cache.size() == 0

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        cache = LRUCache(max_size=2, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

    def test_lru_eviction(self):
        """测试 LRU 淘汰策略"""
        cache = LRUCache(max_size=2, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = LRUCache(max_size=10, ttl=1)
        cache.set("key1", "value1")

        assert cache.get("key1") == "value1"

        import time
        time.sleep(1.1)

        assert cache.get("key1") is None

    def test_clear(self):
        """测试清空缓存"""
        cache = LRUCache(max_size=10, ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.size() == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestProbabilityToScore:
    """测试概率转评分功能"""

    @pytest.fixture
    def inference_engine(self):
        """创建推理引擎实例"""
        return InferenceEngine(cache_size=10, cache_ttl=60)

    def test_convert_probability_to_score_higher_better(self, inference_engine):
        """测试 higher_better 方向的评分转换"""
        params = {
            'base_score': 600,
            'pdo': 50,
            'min_score': 300,
            'max_score': 900,
            'direction': 'higher_better'
        }

        score_low_risk = inference_engine._convert_probability_to_score(0.05, params)
        score_high_risk = inference_engine._convert_probability_to_score(0.95, params)

        assert score_low_risk > score_high_risk
        assert 300 <= score_low_risk <= 900
        assert 300 <= score_high_risk <= 900
        assert score_low_risk > 600
        assert score_high_risk < 600

    def test_convert_probability_to_score_lower_better(self, inference_engine):
        """测试 lower_better 方向的评分转换"""
        params = {
            'base_score': 600,
            'pdo': 50,
            'min_score': 300,
            'max_score': 900,
            'direction': 'lower_better'
        }

        score_low_risk = inference_engine._convert_probability_to_score(0.05, params)
        score_high_risk = inference_engine._convert_probability_to_score(0.95, params)

        assert score_low_risk < score_high_risk
        assert 300 <= score_low_risk <= 900
        assert 300 <= score_high_risk <= 900
        assert score_low_risk < 600
        assert score_high_risk > 600

    def test_convert_probability_to_score_boundary(self, inference_engine):
        """测试边界概率值"""
        params = {
            'base_score': 600,
            'pdo': 50,
            'min_score': 300,
            'max_score': 900,
            'direction': 'higher_better'
        }

        score_zero = inference_engine._convert_probability_to_score(0.000001, params)
        score_one = inference_engine._convert_probability_to_score(0.999999, params)

        assert 300 <= score_zero <= 900
        assert 300 <= score_one <= 900
        assert score_zero > score_one

    def test_convert_probability_to_score_default_params(self, inference_engine):
        """测试默认参数"""
        score = inference_engine._convert_probability_to_score(0.05)

        assert 300 <= score <= 900
        assert score > 600

    def test_convert_probability_to_score_custom_params(self, inference_engine):
        """测试自定义参数"""
        params = {
            'base_score': 500,
            'pdo': 40,
            'min_score': 200,
            'max_score': 800,
            'direction': 'higher_better'
        }

        score = inference_engine._convert_probability_to_score(0.05, params)

        assert 200 <= score <= 800


class TestFeatureValidation:
    """测试特征验证"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_validate_features_success(self, inference_engine):
        """测试特征验证成功"""
        features = {"feature1": 10, "feature2": 20}
        required = ["feature1", "feature2"]

        inference_engine._validate_features(features, required)

    def test_validate_features_missing(self, inference_engine):
        """测试特征缺失"""
        features = {"feature1": 10}
        required = ["feature1", "feature2"]

        with pytest.raises(ModelInferenceException) as exc:
            inference_engine._validate_features(features, required)

        assert "缺少必要特征" in str(exc.value)
        assert "feature2" in str(exc.value)


class TestInputPreparation:
    """测试输入准备"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_prepare_input(self, inference_engine):
        """测试输入准备"""
        features = {"feature2": 20, "feature1": 10}
        input_features = ["feature1", "feature2"]

        result = inference_engine._prepare_input(features, input_features)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["feature1", "feature2"]
        assert result.iloc[0]["feature1"] == 10
        assert result.iloc[0]["feature2"] == 20


class TestScorecardParsing:
    """测试评分卡结果解析"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_parse_scorecard_result_array(self, inference_engine):
        """测试解析数组结果"""
        raw_result = np.array([0.05])
        features = {"feature1": 10, "feature2": 20}

        result = inference_engine._parse_scorecard_result(
            raw_result, {}, features, {}
        )

        assert 'default_probability' in result
        assert 'total_score' in result
        assert 'feature_scores' in result
        assert result['default_probability'] == 0.05

    def test_parse_scorecard_result_scalar(self, inference_engine):
        """测试解析标量结果"""
        raw_result = 0.05
        features = {"feature1": 10}

        result = inference_engine._parse_scorecard_result(
            raw_result, {}, features, {}
        )

        assert result['default_probability'] == 0.05


class TestFraudParsing:
    """测试反欺诈结果解析"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_parse_fraud_result_low_risk(self, inference_engine):
        """测试低风险反欺诈结果"""
        raw_result = np.array([0.1])
        features = {"feature1": 10}

        result = inference_engine._parse_fraud_result(raw_result, {}, features)

        assert result['fraud_probability'] == 0.1
        assert result['risk_score'] == 10.0
        assert len(result['risk_factors']) == 0

    def test_parse_fraud_result_high_risk(self, inference_engine):
        """测试高风险反欺诈结果"""
        raw_result = 0.85
        features = {"feature1": 10}

        result = inference_engine._parse_fraud_result(raw_result, {}, features)

        assert result['fraud_probability'] == 0.85
        assert result['risk_score'] == 85.0
        assert len(result['risk_factors']) == 1
        assert result['risk_factors'][0]['factor'] == 'high_fraud_probability'


class TestFeatureImportance:
    """测试特征重要性计算"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_calculate_feature_importance_with_importances(self, inference_engine):
        """测试使用内置特征重要性"""
        model = MagicMock()
        model.feature_importances_ = np.array([0.5, 0.3, 0.2])

        input_data = pd.DataFrame([[1, 2, 3]], columns=['f1', 'f2', 'f3'])

        importance = inference_engine._calculate_feature_importance(
            model, input_data, 'xgboost', {}
        )

        assert len(importance) == 3
        assert importance['f1'] == 0.5
        assert importance['f2'] == 0.3
        assert importance['f3'] == 0.2

    def test_calculate_feature_importance_with_coef(self, inference_engine):
        """测试使用线性模型系数"""
        model = MagicMock()
        model.coef_ = np.array([2.0, 1.0, -1.0])

        input_data = pd.DataFrame([[1, 2, 3]], columns=['f1', 'f2', 'f3'])

        importance = inference_engine._calculate_feature_importance(
            model, input_data, 'sklearn', {}
        )

        expected_total = 2.0 + 1.0 + 1.0
        assert importance['f1'] == 2.0 / expected_total
        assert importance['f2'] == 1.0 / expected_total
        assert importance['f3'] == 1.0 / expected_total

    def test_calculate_feature_importance_fallback(self, inference_engine):
        """测试降级方案"""
        model = MagicMock()
        input_data = pd.DataFrame([[1, 2]], columns=['f1', 'f2'])
        model.predict.return_value = np.array([0.5])

        importance = inference_engine._calculate_feature_importance(
            model, input_data, 'unknown', {}
        )

        assert len(importance) == 2
        assert importance['f1'] == 0.5
        assert importance['f2'] == 0.5


class TestStatistics:
    """测试统计信息"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine()

    def test_update_stats_success(self, inference_engine):
        """测试成功统计更新"""
        inference_engine._update_stats(True, 100.5)

        stats = inference_engine.get_stats()
        assert stats['total_inferences'] == 1
        assert stats['success_inferences'] == 1
        assert stats['failed_inferences'] == 0
        assert stats['total_duration_ms'] == 100.5

    def test_update_stats_failure(self, inference_engine):
        """测试失败统计更新"""
        inference_engine._update_stats(False, 50.0)

        stats = inference_engine.get_stats()
        assert stats['total_inferences'] == 1
        assert stats['success_inferences'] == 0
        assert stats['failed_inferences'] == 1
        assert stats['total_duration_ms'] == 50.0

    def test_get_stats_with_averages(self, inference_engine):
        """测试获取统计平均值"""
        inference_engine._update_stats(True, 100.0)
        inference_engine._update_stats(True, 200.0)
        inference_engine._update_stats(False, 150.0)

        stats = inference_engine.get_stats()

        assert stats['total_inferences'] == 3
        assert stats['success_inferences'] == 2
        assert stats['failed_inferences'] == 1
        assert stats['avg_duration_ms'] == (100 + 200 + 150) / 3
        assert stats['success_rate'] == 2 / 3


class TestCache:
    """测试缓存功能"""

    @pytest.fixture
    def inference_engine(self):
        return InferenceEngine(cache_size=10, cache_ttl=60)

    def test_get_cache_key(self, inference_engine):
        """测试缓存键生成"""
        key1 = inference_engine._get_cache_key("model1", {"a": 1, "b": 2})
        key2 = inference_engine._get_cache_key("model1", {"b": 2, "a": 1})
        key3 = inference_engine._get_cache_key("model2", {"a": 1, "b": 2})

        assert key1 == key2
        assert key1 != key3

    def test_cache_hit_and_miss(self, inference_engine):
        """测试缓存命中与未命中"""
        cache_key = inference_engine._get_cache_key("model1", {"a": 1})

        assert inference_engine._cache.get(cache_key) is None

        inference_engine._cache.set(cache_key, {"result": "test"})

        assert inference_engine._cache.get(cache_key) is not None

    def test_cache_stats(self, inference_engine):
        """测试缓存统计"""
        inference_engine._stats['cache_hits'] = 10
        inference_engine._stats['cache_misses'] = 5

        stats = inference_engine.get_cache_stats()

        assert stats['cache_hits'] == 10
        assert stats['cache_misses'] == 5
        assert stats['cache_hit_rate'] == 10 / 15

    def test_clear_cache_specific_model(self, inference_engine):
        """测试清除特定模型的缓存"""
        inference_engine._cache.set("model1:hash1", {"result": 1})
        inference_engine._cache.set("model1:hash2", {"result": 2})
        inference_engine._cache.set("model2:hash1", {"result": 3})

        inference_engine.clear_cache("model1")

        assert inference_engine._cache.get("model1:hash1") is None
        assert inference_engine._cache.get("model1:hash2") is None
        assert inference_engine._cache.get("model2:hash1") is not None

    def test_clear_all_cache(self, inference_engine):
        """测试清除所有缓存"""
        inference_engine._cache.set("key1", "value1")
        inference_engine._cache.set("key2", "value2")

        inference_engine.clear_cache()

        assert inference_engine._cache.size() == 0


class TestBatchPrediction:
    """测试批量预测"""

    def test_batch_prediction_scoring(self):
        """测试批量评分卡预测"""
        inference_engine = InferenceEngine()

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.05, 0.10, 0.15])

        # 创建 mock 的 _loaded_models 字典
        mock_loaded = MagicMock()
        mock_metadata = MagicMock(
            task_type=TaskType.SCORING.value,
            input_features=['f1', 'f2'],
            model_version='1.0.0',
            framework='xgboost',
            model_params={'scorecard': {'base_score': 600, 'pdo': 50}}
        )
        mock_loaded.get.return_value = {'metadata': mock_metadata}

        with patch.object(model_loader, 'get_model', return_value=mock_model), \
                patch.object(model_loader, 'load_model', return_value=True), \
                patch.object(model_loader, '_loaded_models', mock_loaded):
            features_list = [
                {'f1': 10, 'f2': 20},
                {'f1': 15, 'f2': 25},
                {'f1': 20, 'f2': 30}
            ]
            app_ids = ['APP1', 'APP2', 'APP3']

            with patch('datamind.core.ml.inference.context.get_request_id', return_value='req-123'):
                with patch('datamind.core.ml.inference.log_audit'):
                    results = inference_engine.predict_batch(
                        model_id="MDL_123",
                        features_list=features_list,
                        application_ids=app_ids,
                        task_type="scoring"
                    )

            assert len(results) == 3
            for result in results:
                assert 'default_probability' in result
                assert 'total_score' in result

    def test_batch_prediction_partial_failure(self):
        """测试批量预测部分失败"""
        inference_engine = InferenceEngine()

        mock_model = MagicMock()
        # 第一个成功，第二个失败，第三个成功
        mock_model.predict.side_effect = [np.array([0.05]), Exception("预测失败"), np.array([0.15])]

        # 创建 mock 的 _loaded_models 字典
        mock_loaded = MagicMock()
        mock_metadata = MagicMock(
            task_type=TaskType.SCORING.value,
            input_features=['f1', 'f2'],
            model_version='1.0.0',
            framework='xgboost',
            model_params={}
        )
        mock_loaded.get.return_value = {'metadata': mock_metadata}

        with patch.object(model_loader, 'get_model', return_value=mock_model), \
                patch.object(model_loader, 'load_model', return_value=True), \
                patch.object(model_loader, '_loaded_models', mock_loaded):
            features_list = [
                {'f1': 10, 'f2': 20},
                {'f1': 15, 'f2': 25},
                {'f1': 20, 'f2': 30}
            ]
            app_ids = ['APP1', 'APP2', 'APP3']

            with patch('datamind.core.ml.inference.context.get_request_id', return_value='req-123'):
                with patch('datamind.core.ml.inference.log_audit'):
                    results = inference_engine.predict_batch(
                        model_id="MDL_123",
                        features_list=features_list,
                        application_ids=app_ids,
                        task_type="scoring"
                    )

            assert len(results) == 3
            assert 'default_probability' in results[0]
            assert 'error' in results[1]
            assert results[1]['success'] is False
            assert 'default_probability' in results[2]


class TestIntegration:
    """集成测试"""

    def test_full_scorecard_inference_flow(self):
        """测试完整的评分卡推理流程"""
        inference_engine = InferenceEngine()

        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([0.05])

        # 创建 mock 的 _loaded_models 字典
        mock_loaded = MagicMock()
        mock_metadata = MagicMock(
            task_type=TaskType.SCORING.value,
            input_features=['age', 'income'],
            model_version='1.0.0',
            framework='xgboost',
            model_params={
                'scorecard': {
                    'base_score': 600,
                    'pdo': 50,
                    'min_score': 300,
                    'max_score': 900,
                    'direction': 'higher_better'
                }
            }
        )
        mock_loaded.get.return_value = {'metadata': mock_metadata}

        with patch.object(model_loader, 'get_model', return_value=mock_model), \
                patch.object(model_loader, 'load_model', return_value=True), \
                patch.object(model_loader, '_loaded_models', mock_loaded):
            features = {'age': 35, 'income': 50000}

            with patch('datamind.core.ml.inference.context.get_request_id', return_value='req-123'):
                with patch('datamind.core.ml.inference.context.get_span_id', return_value='span-456'):
                    with patch('datamind.core.ml.inference.context.get_parent_span_id', return_value='parent-789'):
                        with patch('datamind.core.ml.inference.log_audit') as mock_audit:
                            result = inference_engine.predict_scorecard(
                                model_id="MDL_123",
                                features=features,
                                application_id="APP_001",
                                user_id="user_123",
                                ip_address="127.0.0.1"
                            )

            assert result['default_probability'] == 0.05
            assert 'total_score' in result
            assert result['model_id'] == "MDL_123"
            assert result['application_id'] == "APP_001"
            assert 'feature_importance' in result

            mock_audit.assert_called_once()
            call_args = mock_audit.call_args[1]
            assert call_args['action'] == AuditAction.MODEL_INFERENCE.value
            assert call_args['user_id'] == "user_123"
            assert call_args['details']['span_id'] == "span-456"
            assert call_args['details']['parent_span_id'] == "parent-789"