# tests/ml/test_model_loader.py
"""测试模型加载器"""

import pytest
import threading
import time
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from pathlib import Path

from datamind.core.ml.model_loader import ModelLoader
from datamind.core.ml.exceptions import ModelLoadException, UnsupportedFrameworkException
from datamind.core.domain.enums import ModelStatus


class TestModelLoader:
    """测试 ModelLoader 类"""

    def test_init(self):
        """测试初始化"""
        loader = ModelLoader()
        assert loader._loaded_models == {}
        assert loader._model_locks == {}
        assert loader._cache_ttl == 3600
        assert loader._max_concurrent_loads == 5
        assert loader._max_retries == 3

    def test_init_with_custom_params(self):
        """测试自定义参数初始化"""
        loader = ModelLoader(
            cache_ttl=1800,
            max_concurrent_loads=10,
            max_retries=5
        )
        assert loader._cache_ttl == 1800
        assert loader._max_concurrent_loads == 10
        assert loader._max_retries == 5

    def test_load_model_success(self, mock_db_session, mock_request_id):
        """测试成功加载模型"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.framework = "sklearn"
        mock_model.file_path = "/tmp/test_model.pkl"
        mock_model.status = ModelStatus.ACTIVE.value

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            with patch('pathlib.Path.exists', return_value=True):
                with patch('joblib.load', return_value=MagicMock()):
                    result = loader.load_model("MDL_123", "test_user", "127.0.0.1")

                    assert result is True
                    assert "MDL_123" in loader._loaded_models
                    assert loader._loaded_models["MDL_123"]["load_count"] == 1
                    assert loader._loaded_models["MDL_123"]["file_size_mb"] == 1.0

    def test_load_model_with_force_reload(self, mock_db_session):
        """测试强制重新加载模型"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.framework = "sklearn"
        mock_model.file_path = "/tmp/model.pkl"
        mock_model.status = ModelStatus.ACTIVE.value

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 1024 * 1024
            with patch('pathlib.Path.exists', return_value=True):
                with patch('joblib.load', return_value=MagicMock()):
                    # 第一次加载
                    loader.load_model("MDL_123")
                    assert loader._loaded_models["MDL_123"]["load_count"] == 1

                    # 强制重新加载
                    loader.load_model("MDL_123", force_reload=True)
                    assert loader._loaded_models["MDL_123"]["load_count"] == 2

    def test_load_model_with_retry(self, mock_db_session):
        """测试加载失败重试"""
        loader = ModelLoader(max_retries=3)

        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.framework = "sklearn"
        mock_model.file_path = "/tmp/model.pkl"
        mock_model.status = ModelStatus.ACTIVE.value

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        load_attempts = 0

        def failing_load(*args, **kwargs):
            nonlocal load_attempts
            load_attempts += 1
            if load_attempts < 3:
                raise IOError("加载失败")
            return MagicMock()

        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 1024 * 1024
            with patch('pathlib.Path.exists', return_value=True):
                with patch('joblib.load', side_effect=failing_load):
                    result = loader.load_model("MDL_123")
                    assert result is True
                    assert load_attempts == 3

    def test_load_model_not_active(self, mock_db_session):
        """测试加载未激活的模型"""
        loader = ModelLoader()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ModelLoadException) as exc:
            loader.load_model("MDL_123", "test_user")

        assert "模型不存在或未激活: MDL_123" in str(exc.value)

    def test_load_model_file_not_exist(self, mock_db_session):
        """测试模型文件不存在"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.file_path = "/tmp/not_exist.pkl"
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(ModelLoadException) as exc:
                loader.load_model("MDL_123", "test_user")

            assert "模型文件不存在" in str(exc.value)

    def test_load_model_unsupported_framework(self, mock_db_session):
        """测试不支持的框架"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.framework = "unsupported_framework"
        mock_model.file_path = "/tmp/model.pkl"
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(UnsupportedFrameworkException) as exc:
                loader.load_model("MDL_123", "test_user")

            assert "不支持的框架: unsupported_framework" in str(exc.value)

    def test_load_model_framework_not_installed(self, mock_db_session):
        """测试框架未安装"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.framework = "sklearn"
        mock_model.file_path = "/tmp/model.pkl"
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with patch('pathlib.Path.exists', return_value=True):
            with patch('joblib.load', side_effect=ImportError("sklearn未安装")):
                with pytest.raises(UnsupportedFrameworkException) as exc:
                    loader.load_model("MDL_123", "test_user")

                assert "sklearn未安装" in str(exc.value)

    def test_unload_model(self):
        """测试卸载模型"""
        loader = ModelLoader()

        mock_model = MagicMock()
        loader._loaded_models["MDL_123"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now(),
            'load_count': 1,
            'file_size_mb': 10.5
        }

        loader.unload_model("MDL_123", "test_user", "127.0.0.1")

        assert "MDL_123" not in loader._loaded_models

    def test_get_model(self):
        """测试获取已加载的模型"""
        loader = ModelLoader()

        mock_model_obj = MagicMock()
        loader._loaded_models["MDL_123"] = {
            'model': mock_model_obj,
            'metadata': MagicMock(),
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        model = loader.get_model("MDL_123")
        assert model == mock_model_obj

        model = loader.get_model("MDL_NOT_EXIST")
        assert model is None

    def test_get_model_with_refresh(self):
        """测试获取模型并刷新"""
        loader = ModelLoader()

        mock_model_obj = MagicMock()
        loader._loaded_models["MDL_123"] = {
            'model': mock_model_obj,
            'metadata': MagicMock(),
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        model = loader.get_model("MDL_123", refresh=True)
        assert model is None
        assert "MDL_123" not in loader._loaded_models

    def test_get_model_expired(self):
        """测试获取已过期的模型"""
        loader = ModelLoader(cache_ttl=1)

        mock_model_obj = MagicMock()
        loader._loaded_models["MDL_123"] = {
            'model': mock_model_obj,
            'metadata': MagicMock(),
            'loaded_at': datetime.now() - timedelta(seconds=2),
            'load_count': 1
        }

        model = loader.get_model("MDL_123")
        assert model is None

    def test_is_loaded(self):
        """测试检查模型是否已加载"""
        loader = ModelLoader()

        loader._loaded_models["MDL_123"] = {'model': MagicMock()}

        assert loader.is_loaded("MDL_123") is True
        assert loader.is_loaded("MDL_NOT_EXIST") is False

    def test_get_loaded_models(self):
        """测试获取所有已加载模型信息"""
        loader = ModelLoader()

        mock_model1 = MagicMock()
        mock_model1.model_name = "model1"
        mock_model1.model_version = "1.0.0"
        mock_model1.framework = "sklearn"

        mock_model2 = MagicMock()
        mock_model2.model_name = "model2"
        mock_model2.model_version = "2.0.0"
        mock_model2.framework = "xgboost"

        loader._loaded_models = {
            "MDL_1": {
                'model': MagicMock(),
                'metadata': mock_model1,
                'loaded_at': datetime(2024, 1, 1, 10, 0, 0),
                'load_count': 5,
                'file_size_mb': 10.5
            },
            "MDL_2": {
                'model': MagicMock(),
                'metadata': mock_model2,
                'loaded_at': datetime(2024, 1, 2, 11, 0, 0),
                'load_count': 3,
                'file_size_mb': 20.3
            }
        }

        loaded = loader.get_loaded_models()
        assert len(loaded) == 2

        model1_info = next(m for m in loaded if m['model_id'] == "MDL_1")
        assert model1_info['model_name'] == "model1"
        assert model1_info['model_version'] == "1.0.0"
        assert model1_info['framework'] == "sklearn"
        assert model1_info['load_count'] == 5
        assert model1_info['file_size_mb'] == 10.5

    def test_get_lock(self):
        """测试获取线程锁"""
        loader = ModelLoader()

        lock1 = loader.get_lock("MDL_123")
        assert hasattr(lock1, 'acquire')
        assert hasattr(lock1, 'release')
        assert "MDL_123" in loader._model_locks

        lock2 = loader.get_lock("MDL_123")
        assert lock1 is lock2

        lock3 = loader.get_lock("MDL_456")
        assert lock1 is not lock3

    def test_concurrent_load(self, mock_db_session, mock_request_id):
        """测试并发加载"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.framework = "sklearn"
        mock_model.file_path = "/tmp/model.pkl"
        mock_model.status = ModelStatus.ACTIVE.value

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        load_count = 0
        lock = threading.Lock()

        def mock_load(*args, **kwargs):
            nonlocal load_count
            time.sleep(0.1)
            with lock:
                load_count += 1
            return MagicMock()

        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value.st_size = 1024 * 1024
            with patch('pathlib.Path.exists', return_value=True):
                with patch('joblib.load', side_effect=mock_load):

                    def run():
                        loader.load_model("MDL_123", "test_user")

                    threads = [threading.Thread(target=run) for _ in range(5)]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()

                    assert load_count == 1
                    assert "MDL_123" in loader._loaded_models
                    assert loader._loaded_models["MDL_123"]["load_count"] == 1

    def test_warm_up_model(self):
        """测试模型预热"""
        loader = ModelLoader()

        mock_model_obj = MagicMock()
        mock_model = MagicMock()
        mock_model.framework = "sklearn"

        loader._loaded_models["MDL_123"] = {
            'model': mock_model_obj,
            'metadata': mock_model,
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        with patch('numpy.random.randn', return_value=MagicMock()):
            result = loader.warm_up_model("MDL_123")
            assert result is True
            mock_model_obj.predict.assert_called_once()

    def test_warm_up_model_not_loaded(self):
        """测试预热未加载的模型"""
        loader = ModelLoader()

        result = loader.warm_up_model("MDL_NOT_EXIST")
        assert result is False

    def test_get_memory_usage(self):
        """测试获取内存使用情况"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.model_name = "test_model"
        mock_model.framework = "sklearn"

        loader._loaded_models["MDL_123"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now(),
            'load_count': 2,
            'file_size_mb': 15.5
        }

        with patch('psutil.Process') as mock_process:
            mock_memory = MagicMock()
            mock_memory.rss = 1024 * 1024 * 100  # 100MB
            mock_process.return_value.memory_info.return_value = mock_memory

            with patch('pickle.dumps', return_value=b'x' * (10 * 1024 * 1024)):  # 10MB
                memory = loader.get_memory_usage()

                assert memory['total_models'] == 1
                assert memory['process_memory_mb'] == 100.0
                assert "MDL_123" in memory['models']
                assert memory['models']["MDL_123"]['model_name'] == "test_model"

    def test_health_check_healthy(self):
        """测试健康检查 - 健康状态"""
        loader = ModelLoader()

        mock_model = MagicMock()
        mock_model.model_name = "test_model"

        loader._loaded_models["MDL_123"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now(),
            'load_count': 1,
            'file_size_mb': 10.5
        }

        health = loader.health_check()
        assert health['status'] == 'healthy'
        assert health['loaded_models_count'] == 1
        assert len(health['models']) == 1
        assert health['models'][0]['model_id'] == "MDL_123"
        assert health['models'][0]['status'] == 'healthy'

    def test_health_check_expired(self):
        """测试健康检查 - 过期状态"""
        loader = ModelLoader(cache_ttl=1)

        mock_model = MagicMock()
        mock_model.model_name = "test_model"

        loader._loaded_models["MDL_123"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now() - timedelta(seconds=2),
            'load_count': 1,
            'file_size_mb': 10.5
        }

        health = loader.health_check()
        assert health['status'] == 'healthy'
        assert health['models'][0]['status'] == 'expired'

    def test_clear_expired_cache(self):
        """测试清除过期缓存"""
        loader = ModelLoader(cache_ttl=1)

        mock_model = MagicMock()

        # 未过期的模型
        loader._loaded_models["MDL_1"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now(),
            'load_count': 1
        }

        # 已过期的模型
        loader._loaded_models["MDL_2"] = {
            'model': MagicMock(),
            'metadata': mock_model,
            'loaded_at': datetime.now() - timedelta(seconds=2),
            'load_count': 1
        }

        cleared = loader.clear_expired_cache()
        assert cleared == 1
        assert "MDL_1" in loader._loaded_models
        assert "MDL_2" not in loader._loaded_models