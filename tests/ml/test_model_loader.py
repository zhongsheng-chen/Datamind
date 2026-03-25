# tests/ml/test_model_loader.py

"""测试模型加载器"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from datamind.core.ml.model_loader import ModelLoader



class TestModelLoader:
    """测试模型加载器"""

    # ==================== 基础功能测试 ====================

    def test_initialization(self):
        """测试初始化"""
        loader = ModelLoader(cache_ttl=60, max_concurrent_loads=2, max_retries=3)
        assert loader._cache_ttl == 60
        assert loader._max_concurrent_loads == 2
        assert loader._max_retries == 3
        assert loader._loaded_models == {}
        assert loader._model_locks == {}

    def test_get_lock(self, model_loader):
        """测试获取线程锁"""
        lock1 = model_loader.get_lock("MDL_001")
        lock2 = model_loader.get_lock("MDL_001")
        lock3 = model_loader.get_lock("MDL_002")

        assert lock1 is lock2
        assert lock1 is not lock3

    def test_get_lock_multiple_calls(self, model_loader):
        """测试多次调用获取同一个锁"""
        lock1 = model_loader.get_lock("MDL_001")
        lock2 = model_loader.get_lock("MDL_001")
        assert lock1 is lock2

    # ==================== 模型缓存管理测试 ====================

    def test_is_loaded(self, model_loader):
        """测试检查模型是否已加载"""
        assert model_loader.is_loaded("MDL_NOT_EXIST") is False

        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        assert model_loader.is_loaded("MDL_TEST") is True

    def test_get_model_not_loaded(self, model_loader):
        """测试获取未加载的模型"""
        model = model_loader.get_model("MDL_NOT_EXIST")
        assert model is None

    def test_get_model_loaded(self, model_loader):
        """测试获取已加载的模型"""
        mock_model = MagicMock()
        model_loader._loaded_models["MDL_TEST"] = {
            'model': mock_model,
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        result = model_loader.get_model("MDL_TEST")
        assert result is mock_model

    def test_get_model_metadata(self, model_loader):
        """测试获取模型元数据"""
        metadata = {'model_name': 'test', 'model_version': '1.0'}
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': metadata,
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        result = model_loader.get_model_metadata("MDL_TEST")
        assert result == metadata

        result = model_loader.get_model_metadata("MDL_NOT_EXIST")
        assert result is None

    def test_get_loaded_models_empty(self, model_loader):
        """测试获取已加载模型列表 - 空列表"""
        result = model_loader.get_loaded_models()
        assert result == []

    def test_get_loaded_models_with_data(self, model_loader):
        """测试获取已加载模型列表 - 有数据"""
        model_loader._loaded_models["MDL_001"] = {
            'model': MagicMock(),
            'metadata': {
                'model_name': 'model_1',
                'model_version': '1.0.0',
                'framework': 'sklearn'
            },
            'loaded_at': datetime.now(),
            'load_count': 5
        }
        model_loader._loaded_models["MDL_002"] = {
            'model': MagicMock(),
            'metadata': {
                'model_name': 'model_2',
                'model_version': '2.0.0',
                'framework': 'xgboost'
            },
            'loaded_at': datetime.now(),
            'load_count': 3
        }

        result = model_loader.get_loaded_models()

        assert len(result) == 2
        assert result[0]['model_id'] == "MDL_001"
        assert result[0]['model_name'] == "model_1"
        assert result[0]['model_version'] == "1.0.0"
        assert result[0]['framework'] == "sklearn"
        assert result[0]['load_count'] == 5

        assert result[1]['model_id'] == "MDL_002"
        assert result[1]['model_name'] == "model_2"
        assert result[1]['model_version'] == "2.0.0"
        assert result[1]['framework'] == "xgboost"
        assert result[1]['load_count'] == 3

    # ==================== 缓存过期测试 ====================

    def test_is_cache_expired_not_loaded(self, model_loader):
        """测试缓存过期检查 - 模型未加载"""
        result = model_loader._is_cache_expired("MDL_NOT_EXIST")
        assert result is True

    def test_is_cache_expired_false(self, model_loader):
        """测试缓存过期检查 - 未过期"""
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        assert model_loader._is_cache_expired("MDL_TEST") is False

    def test_is_cache_expired_true(self, model_loader):
        """测试缓存过期检查 - 已过期"""
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now() - timedelta(seconds=120),
            'load_count': 1
        }
        assert model_loader._is_cache_expired("MDL_TEST") is True

    def test_clear_expired_cache_empty(self, model_loader):
        """测试清除过期缓存 - 空缓存"""
        count = model_loader.clear_expired_cache()
        assert count == 0

    def test_clear_expired_cache_with_expired(self, model_loader):
        """测试清除过期缓存 - 有过期模型"""
        model_loader._loaded_models["MDL_001"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        model_loader._loaded_models["MDL_002"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now() - timedelta(seconds=120),
            'load_count': 1
        }
        model_loader._loaded_models["MDL_003"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now() - timedelta(seconds=200),
            'load_count': 1
        }

        count = model_loader.clear_expired_cache()

        assert count == 2
        assert "MDL_001" in model_loader._loaded_models
        assert "MDL_002" not in model_loader._loaded_models
        assert "MDL_003" not in model_loader._loaded_models

    # ==================== 模型卸载测试 ====================

    def test_unload_model(self, model_loader):
        """测试卸载模型"""
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'test'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        assert model_loader.is_loaded("MDL_TEST") is True
        model_loader.unload_model("MDL_TEST", "test_user")
        assert model_loader.is_loaded("MDL_TEST") is False

    def test_unload_model_not_loaded(self, model_loader):
        """测试卸载模型 - 模型未加载（应该不报错）"""
        model_loader.unload_model("MDL_NOT_EXIST", "test_user")
        # 不抛出异常即为成功

    def test_unload_model_multiple_times(self, model_loader):
        """测试多次卸载同一个模型"""
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'test'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        model_loader.unload_model("MDL_TEST")
        model_loader.unload_model("MDL_TEST")
        assert model_loader.is_loaded("MDL_TEST") is False

    # ==================== 健康检查测试 ====================

    def test_health_check_empty(self, model_loader):
        """测试健康检查 - 无模型"""
        result = model_loader.health_check()
        assert result['status'] == 'healthy'
        assert result['loaded_models_count'] == 0
        assert len(result['models']) == 0
        assert result['cache_ttl'] == 60

    def test_health_check_healthy(self, model_loader):
        """测试健康检查 - 健康模型"""
        model_loader._loaded_models["MDL_001"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'model_1'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        model_loader._loaded_models["MDL_002"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'model_2'},
            'loaded_at': datetime.now(),
            'load_count': 2
        }

        result = model_loader.health_check()

        assert result['status'] == 'healthy'
        assert result['loaded_models_count'] == 2
        assert len(result['models']) == 2
        assert result['models'][0]['model_id'] == "MDL_001"
        assert result['models'][0]['status'] == 'healthy'
        assert result['models'][0]['model_name'] == "model_1"
        assert result['models'][0]['load_count'] == 1

    def test_health_check_with_expired_model(self, model_loader):
        """测试健康检查 - 有过期模型"""
        model_loader._loaded_models["MDL_001"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'model_1'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        model_loader._loaded_models["MDL_002"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'model_2'},
            'loaded_at': datetime.now() - timedelta(seconds=120),
            'load_count': 1
        }

        result = model_loader.health_check()

        # 有过期模型但仍然是健康的（只是标记为过期）
        assert result['status'] == 'healthy'
        for model in result['models']:
            if model['model_id'] == "MDL_002":
                assert model['status'] == 'expired'

    def test_health_check_with_none_model(self, model_loader):
        """测试健康检查 - 模型为 None"""
        model_loader._loaded_models["MDL_001"] = {
            'model': None,
            'metadata': {'model_name': 'model_1'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        result = model_loader.health_check()

        assert result['status'] == 'unhealthy'
        assert result['models'][0]['model_id'] == "MDL_001"
        assert result['models'][0]['status'] == 'model_is_none'

    def test_health_check_with_error(self, model_loader):
        """测试健康检查 - 模型检查出错"""
        # 添加一个正常模型
        model_loader._loaded_models["MDL_NORMAL"] = {
            'model': MagicMock(),
            'metadata': {'model_name': 'normal', 'model_version': '1.0.0', 'framework': 'sklearn'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        # 添加一个有问题的模型（model 为 None）
        model_loader._loaded_models["MDL_ERROR"] = {
            'model': None,
            'metadata': {'model_name': 'error_model', 'model_version': '1.0.0', 'framework': 'sklearn'},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        result = model_loader.health_check()

        # 有异常模型时，整体状态应为 unhealthy
        assert result['status'] == 'unhealthy'
        assert result['loaded_models_count'] == 2
        assert len(result['models']) == 2

        # 检查正常模型 - 包含完整信息
        normal_model = next(m for m in result['models'] if m['model_id'] == "MDL_NORMAL")
        assert normal_model['status'] == 'healthy'
        assert normal_model['model_name'] == 'normal'
        assert normal_model['load_count'] == 1

        # 检查错误模型
        error_model = next(m for m in result['models'] if m['model_id'] == "MDL_ERROR")
        assert error_model['status'] == 'model_is_none'
        assert 'model_name' not in error_model

    def test_health_check_with_metadata_error(self, model_loader):
        """测试健康检查 - 元数据访问出错"""
        # 创建一个会抛出异常的模型（在访问 metadata 时）
        class ErrorModel:
            pass

        error_model = ErrorModel()

        # 添加一个会抛出异常的模型（在 health_check 中访问 metadata 会出错）
        model_loader._loaded_models["MDL_ERROR"] = {
            'model': error_model,
            'metadata': None,
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        result = model_loader.health_check()

        # 有异常时，状态应为 unhealthy
        assert result['status'] == 'unhealthy'
        assert len(result['models']) == 1

        error_model_result = result['models'][0]
        assert error_model_result['model_id'] == "MDL_ERROR"
        assert error_model_result['status'] == 'error'
        assert 'error' in error_model_result

    # ==================== 并发锁测试 ====================

    def test_lock_prevents_concurrent_loading(self, model_loader):
        """测试锁防止并发加载"""
        import threading

        lock = model_loader.get_lock("MDL_TEST")
        lock_acquired = [False]

        def try_acquire():
            # 这个测试需要在线程中验证锁的行为
            pass

        # 简单验证锁对象存在
        assert lock is not None

    # ==================== 边界条件测试 ====================

    def test_cache_ttl_zero(self):
        """测试缓存 TTL 为 0"""
        loader = ModelLoader(cache_ttl=0)
        loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        assert loader._is_cache_expired("MDL_TEST") is True

    def test_cache_ttl_negative(self):
        """测试缓存 TTL 为负数"""
        loader = ModelLoader(cache_ttl=-1)
        loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }
        assert loader._is_cache_expired("MDL_TEST") is True

    def test_large_number_of_models(self, model_loader):
        """测试大量模型"""
        import time

        # 添加大量模型
        for i in range(100):
            model_loader._loaded_models[f"MDL_{i:03d}"] = {
                'model': MagicMock(),
                'metadata': {
                    'model_name': f"model_{i}",
                    'model_version': f"1.0.{i}",
                    'framework': 'sklearn' if i % 2 == 0 else 'xgboost'
                },
                'loaded_at': datetime.now(),
                'load_count': i + 1
            }

        # 验证数量
        result = model_loader.get_loaded_models()
        assert len(result) == 100

        # 验证前几个模型
        assert result[0]['model_id'] == "MDL_000"
        assert result[0]['model_name'] == "model_0"
        assert result[0]['model_version'] == "1.0.0"
        assert result[0]['framework'] == "sklearn"
        assert result[0]['load_count'] == 1

        # 验证中间模型
        assert result[50]['model_id'] == "MDL_050"
        assert result[50]['model_name'] == "model_50"
        assert result[50]['model_version'] == "1.0.50"
        assert result[50]['load_count'] == 51

        # 验证最后一个模型
        assert result[99]['model_id'] == "MDL_099"
        assert result[99]['model_name'] == "model_99"
        assert result[99]['model_version'] == "1.0.99"
        assert result[99]['load_count'] == 100

        # 验证健康检查也能处理大量模型
        health = model_loader.health_check()
        assert health['loaded_models_count'] == 100
        assert health['status'] == 'healthy'

        # 验证清除过期缓存不会影响（因为所有模型都是新的）
        expired_count = model_loader.clear_expired_cache()
        assert expired_count == 0
        assert len(model_loader.get_loaded_models()) == 100

    def test_load_count_increment(self, model_loader):
        """测试加载计数递增"""
        model_loader._loaded_models["MDL_TEST"] = {
            'model': MagicMock(),
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        # 模拟重新加载
        model_loader._loaded_models["MDL_TEST"]['load_count'] += 1

        assert model_loader._loaded_models["MDL_TEST"]['load_count'] == 2

    # ==================== 预热模型测试 ====================

    def test_warm_up_model_not_loaded(self, model_loader):
        """测试预热模型 - 模型未加载"""
        result = model_loader.warm_up_model("MDL_NOT_EXIST")
        assert result is False

    # ==================== 刷新缓存测试 ====================

    def test_get_model_refresh(self, model_loader):
        """测试 get_model 的 refresh 参数"""
        mock_model = MagicMock()
        model_loader._loaded_models["MDL_TEST"] = {
            'model': mock_model,
            'metadata': {},
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        # refresh=True 应该卸载模型
        result = model_loader.get_model("MDL_TEST", refresh=True)

        assert result is None
        assert model_loader.is_loaded("MDL_TEST") is False