# tests/core/ml/test_inference.py

"""测试推理引擎"""

import pytest
import time
import numpy as np
from unittest.mock import patch, MagicMock

from datamind.core.ml.model import InferenceEngine, LRUCache
from datamind.core.common.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.domain.enums import TaskType


class TestLRUCache:
    """测试 LRU 缓存"""

    def test_set_and_get(self):
        """测试设置和获取"""
        cache = LRUCache(max_size=3, ttl=3600)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") is None

    def test_max_size(self):
        """测试最大容量"""
        cache = LRUCache(max_size=2, ttl=3600)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # key1 应该被淘汰
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_lru_eviction(self):
        """测试 LRU 淘汰策略"""
        cache = LRUCache(max_size=2, ttl=3600)

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.get("key1")  # 访问 key1，使其成为最近使用
        cache.set("key3", "value3")

        # key2 应该被淘汰
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"

    def test_ttl_expiration(self):
        """测试 TTL 过期"""
        cache = LRUCache(max_size=3, ttl=1)

        cache.set("key1", "value1")
        time.sleep(1.1)

        assert cache.get("key1") is None

    def test_clear(self):
        """测试清空缓存"""
        cache = LRUCache(max_size=3, ttl=3600)

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0


class TestInferenceEngine:
    """测试推理引擎"""

    @pytest.fixture
    def engine(self):
        """创建推理引擎实例"""
        return InferenceEngine(cache_size=10, cache_ttl=3600)

    @pytest.fixture
    def mock_model(self):
        """模拟模型"""
        model = MagicMock()
        model.predict.return_value = np.array([0.05])  # 5% 违约概率
        return model

    @pytest.fixture
    def mock_model_metadata(self):
        """模拟模型元数据"""
        return {
            'model_id': 'MDL_TEST',
            'model_name': 'test_model',
            'model_version': '1.0.0',
            'task_type': TaskType.SCORING.value,
            'framework': 'sklearn',
            'input_features': ['age', 'income', 'debt_ratio'],
            'output_schema': {'score': 'float'},
            'model_params': {
                'scorecard': {
                    'base_score': 600,
                    'pdo': 50,
                    'min_score': 300,
                    'max_score': 900,
                    'direction': 'lower_better'
                }
            }
        }

    @patch('datamind.core.ml.inference.model_loader')
    @patch('datamind.core.ml.inference.get_db')
    def test_predict_scorecard_success(
        self, mock_get_db, mock_model_loader, engine, mock_model, mock_model_metadata
    ):
        """测试评分卡预测 - 成功"""
        # 模拟模型加载器
        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': mock_model_metadata}
        }
        mock_model_loader.load_model.return_value = True

        # 模拟数据库
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        # 执行预测
        result = engine.predict_scorecard(
            model_id="MDL_TEST",
            features={"age": 35, "income": 50000, "debt_ratio": 0.35},
            application_id="APP_001",
            user_id="test_user"
        )

        # 验证结果
        assert result['model_id'] == "MDL_TEST"
        assert result['application_id'] == "APP_001"
        assert 'total_score' in result
        assert 'default_probability' in result
        assert 'feature_scores' in result
        assert result['from_cache'] is False

        # 验证模型预测被调用
        mock_model.predict.assert_called_once()

        # 验证数据库日志被添加
        mock_session.add.assert_called()
        mock_session.commit.assert_called()

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_scorecard_model_not_loaded(
        self, mock_model_loader, engine, mock_model, mock_model_metadata
    ):
        """测试评分卡预测 - 模型未加载，自动加载"""
        # 第一次获取模型返回 None，触发加载
        mock_model_loader.get_model.side_effect = [None, mock_model]
        mock_model_loader.load_model.return_value = True
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': mock_model_metadata}
        }

        # 模拟数据库
        with patch('datamind.core.ml.inference.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_session

            result = engine.predict_scorecard(
                model_id="MDL_TEST",
                features={"age": 35, "income": 50000},
                application_id="APP_001"
            )

        assert result is not None
        mock_model_loader.load_model.assert_called_once()

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_scorecard_model_not_found(self, mock_model_loader, engine):
        """测试评分卡预测 - 模型不存在"""
        mock_model_loader.get_model.return_value = None
        mock_model_loader.load_model.return_value = False

        with pytest.raises(ModelNotFoundException):
            engine.predict_scorecard(
                model_id="MDL_NOT_EXIST",
                features={"age": 35},
                application_id="APP_001"
            )

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_scorecard_missing_features(self, mock_model_loader, engine, mock_model, mock_model_metadata):
        """测试评分卡预测 - 缺少特征"""
        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': mock_model_metadata}
        }

        with pytest.raises(ModelInferenceException) as exc_info:
            engine.predict_scorecard(
                model_id="MDL_TEST",
                features={"age": 35},  # 缺少 income 和 debt_ratio
                application_id="APP_001"
            )
        assert "缺少必要特征" in str(exc_info.value)

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_scorecard_wrong_task_type(self, mock_model_loader, engine, mock_model):
        """测试评分卡预测 - 任务类型不匹配"""
        metadata = {
            'task_type': TaskType.FRAUD_DETECTION.value,  # 错误的任务类型
            'input_features': ['age', 'income']
        }
        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': metadata}
        }

        with pytest.raises(ModelInferenceException) as exc_info:
            engine.predict_scorecard(
                model_id="MDL_TEST",
                features={"age": 35, "income": 50000},
                application_id="APP_001"
            )
        assert "模型类型不匹配" in str(exc_info.value)

    @patch('datamind.core.ml.inference.model_loader')
    @patch('datamind.core.ml.inference.get_db')
    def test_predict_scorecard_with_cache(
        self, mock_get_db, mock_model_loader, engine, mock_model, mock_model_metadata
    ):
        """测试评分卡预测 - 使用缓存"""
        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': mock_model_metadata}
        }
        mock_model_loader.load_model.return_value = True

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        features = {"age": 35, "income": 50000, "debt_ratio": 0.35}

        # 第一次预测
        result1 = engine.predict_scorecard(
            model_id="MDL_TEST",
            features=features,
            application_id="APP_001",
            use_cache=True
        )

        # 第二次预测（应该命中缓存）
        result2 = engine.predict_scorecard(
            model_id="MDL_TEST",
            features=features,
            application_id="APP_001",
            use_cache=True
        )

        assert result1['from_cache'] is False
        assert result2['from_cache'] is True
        assert result1['total_score'] == result2['total_score']

        # 验证模型只被调用一次
        assert mock_model.predict.call_count == 1

    @patch('datamind.core.ml.inference.model_loader')
    @patch('datamind.core.ml.inference.get_db')
    def test_predict_fraud_success(
        self, mock_get_db, mock_model_loader, engine, mock_model
    ):
        """测试反欺诈预测 - 成功"""
        metadata = {
            'model_id': 'MDL_FRAUD',
            'model_version': '1.0.0',
            'task_type': TaskType.FRAUD_DETECTION.value,
            'framework': 'sklearn',
            'input_features': ['ip_risk', 'device_risk', 'amount']
        }

        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_FRAUD': {'metadata': metadata}
        }

        mock_model.predict.return_value = np.array([0.85])  # 85% 欺诈概率

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        result = engine.predict_fraud(
            model_id="MDL_FRAUD",
            features={"ip_risk": 0.8, "device_risk": 0.9, "amount": 10000},
            application_id="APP_001"
        )

        assert result['fraud_probability'] == 0.85
        assert result['risk_score'] == 85.0
        assert len(result['risk_factors']) > 0
        assert result['risk_factors'][0]['factor'] == 'high_fraud_probability'

    @patch('datamind.core.ml.inference.model_loader')
    @patch('datamind.core.ml.inference.get_db')
    def test_predict_batch_success(
        self, mock_get_db, mock_model_loader, engine, mock_model, mock_model_metadata
    ):
        """测试批量预测 - 成功"""
        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': mock_model_metadata}
        }

        mock_model.predict.return_value = np.array([0.05])

        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        features_list = [
            {"age": 35, "income": 50000, "debt_ratio": 0.35},
            {"age": 45, "income": 80000, "debt_ratio": 0.25},
            {"age": 25, "income": 30000, "debt_ratio": 0.45}
        ]
        application_ids = ["APP_001", "APP_002", "APP_003"]

        results = engine.predict_batch(
            model_id="MDL_TEST",
            features_list=features_list,
            application_ids=application_ids,
            task_type=TaskType.SCORING.value
        )

        assert len(results) == 3
        for result in results:
            assert 'total_score' in result
            assert 'default_probability' in result

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_batch_length_mismatch(self, mock_model_loader, engine):
        """测试批量预测 - 长度不匹配"""
        with pytest.raises(ValueError) as exc_info:
            engine.predict_batch(
                model_id="MDL_TEST",
                features_list=[{"age": 35}],
                application_ids=["APP_001", "APP_002"],
                task_type=TaskType.SCORING.value
            )
        assert "长度必须一致" in str(exc_info.value)

    def test_update_stats(self, engine):
        """测试更新统计信息"""
        engine._update_stats(True, 100)
        engine._update_stats(True, 150)
        engine._update_stats(False, 50)

        stats = engine.get_stats()

        assert stats['total_inferences'] == 3
        assert stats['success_inferences'] == 2
        assert stats['failed_inferences'] == 1
        assert stats['total_duration_ms'] == 300
        assert stats['avg_duration_ms'] == 100.0
        assert stats['success_rate'] == 2/3

    def test_clear_cache(self, engine):
        """测试清除缓存"""
        # 添加缓存
        engine._cache.set("key1", "value1")
        engine._cache.set("key2", "value2")

        assert engine._cache.size() == 2

        engine.clear_cache()

        assert engine._cache.size() == 0

    def test_clear_cache_by_model_id(self, engine):
        """测试按模型ID清除缓存"""
        engine._cache.set("MDL_001:hash1", "value1")
        engine._cache.set("MDL_001:hash2", "value2")
        engine._cache.set("MDL_002:hash3", "value3")

        assert engine._cache.size() == 3

        engine.clear_cache(model_id="MDL_001")

        assert engine._cache.size() == 1
        assert engine._cache.get("MDL_002:hash3") == "value3"

    def test_get_cache_stats(self, engine):
        """测试获取缓存统计"""
        engine._stats['cache_hits'] = 10
        engine._stats['cache_misses'] = 40

        # 添加一些缓存项
        engine._cache.set("key1", "value1")
        engine._cache.set("key2", "value2")

        stats = engine.get_cache_stats()

        assert stats['cache_size'] == 2
        assert stats['cache_max_size'] == 10
        assert stats['cache_ttl'] == 3600
        assert stats['cache_hits'] == 10
        assert stats['cache_misses'] == 40
        assert stats['cache_hit_rate'] == 0.2

    @patch('datamind.core.ml.inference.model_loader')
    def test_predict_scorecard_with_scorecard_params(
        self, mock_model_loader, engine, mock_model
    ):
        """测试评分卡预测 - 使用自定义评分卡参数"""
        metadata = {
            'model_id': 'MDL_TEST',
            'model_version': '1.0.0',
            'task_type': TaskType.SCORING.value,
            'framework': 'sklearn',
            'input_features': ['age'],
            'model_params': {
                'scorecard': {
                    'base_score': 700,
                    'pdo': 60,
                    'min_score': 400,
                    'max_score': 800,
                    'direction': 'higher_better'
                }
            }
        }

        mock_model_loader.get_model.return_value = mock_model
        mock_model_loader._loaded_models = {
            'MDL_TEST': {'metadata': metadata}
        }

        # 模拟预测结果
        mock_model.predict.return_value = np.array([0.1])  # 10% 违约概率

        with patch('datamind.core.ml.inference.get_db') as mock_get_db:
            mock_session = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_session

            result = engine.predict_scorecard(
                model_id="MDL_TEST",
                features={"age": 35},
                application_id="APP_001"
            )

            # 验证评分计算
            # higher_better 模式：score = base_score - (pdo/log(2)) * log(odds)
            assert result['total_score'] > 0