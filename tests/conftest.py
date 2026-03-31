# tests/conftest.py
"""Pytest 共享 fixtures 和配置"""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from datamind.core.ml.model import ModelLoader
from datamind.core.ml.model import ModelRegistry
from datamind.core.ml.model import InferenceEngine
from datamind.core.domain.enums import TaskType, ModelStatus, Framework, ModelType


# ==================== 配置 fixtures ====================

@pytest.fixture(autouse=True)
def mock_settings():
    """模拟设置 - 所有测试自动使用"""
    with patch('datamind.config.get_settings') as m1, \
            patch('datamind.core.db.database.get_settings') as m2:
        mock_settings = MagicMock()

        # 应用设置
        mock_settings.app = MagicMock()
        mock_settings.app.app_name = "test_app"
        mock_settings.app.env = "test"
        mock_settings.app.debug = True

        # 模型设置
        mock_settings.model = MagicMock()
        mock_settings.model.models_path = "/tmp/test_models"
        mock_settings.model.max_size = 1024 * 1024 * 1024
        mock_settings.model.allowed_extensions = ['.pkl', '.json', '.txt', '.pt', '.h5', '.onnx', '.cbm', '.bin']

        # 数据库设置
        mock_settings.database = MagicMock()
        mock_settings.database.url = "postgresql://test:test@localhost:5432/test"
        mock_settings.database.readonly_url = None
        mock_settings.database.pool_size = 5
        mock_settings.database.max_overflow = 10
        mock_settings.database.pool_timeout = 30
        mock_settings.database.pool_recycle = 3600
        mock_settings.database.echo = False

        # 推理设置
        mock_settings.inference = MagicMock()
        mock_settings.inference.timeout = 30
        mock_settings.inference.cache_size = 100
        mock_settings.inference.cache_ttl = 3600

        # A/B测试设置
        mock_settings.ab_test = MagicMock()
        mock_settings.ab_test.enabled = True
        mock_settings.ab_test.redis_key_prefix = "ab_test:"
        mock_settings.ab_test.assignment_expiry = 86400

        m1.return_value = mock_settings
        m2.return_value = mock_settings

        yield mock_settings


# ==================== 数据库 fixtures ====================

@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    # 创建 mock_db_manager
    mock_db_manager = MagicMock()

    # 创建 mock session
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.flush = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.close = MagicMock()
    mock_session.delete = MagicMock()

    # 设置 query 链式调用
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.filter_by.return_value = mock_query
    mock_query.first.return_value = None
    mock_query.all.return_value = []
    mock_query.count.return_value = 0
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_session.query.return_value = mock_query

    # 设置 session_scope 上下文管理器
    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_session
    mock_context.__exit__.return_value = None
    mock_db_manager.session_scope.return_value = mock_context
    mock_db_manager.get_session.return_value = mock_session

    # 初始化 _scoped_sessions 字典
    mock_db_manager._scoped_sessions = {'default': MagicMock(return_value=mock_session)}
    mock_db_manager._engines = {'default': MagicMock()}
    mock_db_manager._initialized = True

    # 直接 mock get_db 函数，让它返回 mock_context
    with patch('datamind.core.db.database.get_db', return_value=mock_context), \
            patch('datamind.core.db.database.db_manager', mock_db_manager):
        yield mock_session


# ==================== BentoML fixtures ====================

@pytest.fixture
def mock_bentoml_for_loader():
    """模拟 BentoML 模块 - 专门用于 model_loader 测试"""
    with patch('datamind.core.ml.model_loader.bentoml') as mock_bentoml:
        # 配置 mock
        mock_bento_model = MagicMock()
        mock_bento_model.tag = MagicMock()
        mock_bento_model.tag.__str__.return_value = "test_model:latest"
        mock_bentoml.models.get.return_value = mock_bento_model

        # 模拟框架加载器
        mock_bentoml.sklearn.load_model.return_value = MagicMock()
        mock_bentoml.xgboost.load_model.return_value = MagicMock()
        mock_bentoml.lightgbm.load_model.return_value = MagicMock()
        mock_bentoml.catboost.load_model.return_value = MagicMock()
        mock_bentoml.pytorch.load_model.return_value = MagicMock()
        mock_bentoml.tensorflow.load_model.return_value = MagicMock()
        mock_bentoml.onnx.load_model.return_value = MagicMock()
        mock_bentoml.pickle.load_model.return_value = MagicMock()

        yield mock_bentoml


@pytest.fixture
def mock_bentoml_for_registry():
    """模拟 BentoML 模块 - 专门用于 model_registry 测试"""
    with patch('datamind.core.ml.model_registry.bentoml') as mock_bentoml:
        # 配置 mock
        mock_bentoml.models.delete = MagicMock()
        mock_bentoml.sklearn.save_model = MagicMock()
        mock_bentoml.xgboost.save_model = MagicMock()
        mock_bentoml.lightgbm.save_model = MagicMock()
        mock_bentoml.catboost.save_model = MagicMock()
        mock_bentoml.pytorch.save_model = MagicMock()
        mock_bentoml.tensorflow.save_model = MagicMock()
        mock_bentoml.onnx.save_model = MagicMock()
        mock_bentoml.pickle.save_model = MagicMock()

        yield mock_bentoml


# 为了向后兼容，保留原来的 mock_bentoml，但改为使用更安全的实现
@pytest.fixture
def mock_bentoml():
    """模拟 BentoML 模块 - 同时支持两个模块（安全版本）"""
    # 使用 patch 分别 mock 两个模块，如果某个模块不存在，则跳过
    with patch('datamind.core.ml.model_loader.bentoml', create=True) as mock_loader, \
            patch('datamind.core.ml.model_registry.bentoml', create=True) as mock_registry:
        # 配置 loader 的 mock
        mock_bento_model = MagicMock()
        mock_bento_model.tag = MagicMock()
        mock_bento_model.tag.__str__.return_value = "test_model:latest"
        mock_loader.models.get.return_value = mock_bento_model
        mock_loader.sklearn.load_model.return_value = MagicMock()
        mock_loader.xgboost.load_model.return_value = MagicMock()
        mock_loader.lightgbm.load_model.return_value = MagicMock()
        mock_loader.catboost.load_model.return_value = MagicMock()
        mock_loader.pytorch.load_model.return_value = MagicMock()
        mock_loader.tensorflow.load_model.return_value = MagicMock()
        mock_loader.onnx.load_model.return_value = MagicMock()
        mock_loader.pickle.load_model.return_value = MagicMock()

        # 配置 registry 的 mock
        mock_registry.models.delete = MagicMock()
        mock_registry.sklearn.save_model = MagicMock()
        mock_registry.xgboost.save_model = MagicMock()
        mock_registry.lightgbm.save_model = MagicMock()
        mock_registry.catboost.save_model = MagicMock()
        mock_registry.pytorch.save_model = MagicMock()
        mock_registry.tensorflow.save_model = MagicMock()
        mock_registry.onnx.save_model = MagicMock()
        mock_registry.pickle.save_model = MagicMock()

        yield {
            'loader': mock_loader,
            'registry': mock_registry
        }


# ==================== 模型元数据 fixtures ====================

@pytest.fixture
def sample_model_metadata():
    """示例模型元数据"""
    metadata = MagicMock()
    metadata.model_id = "MDL_20240315_ABCD1234"
    metadata.model_name = "test_model"
    metadata.model_version = "1.0.0"
    metadata.task_type = TaskType.SCORING.value
    metadata.model_type = ModelType.XGBOOST.value
    metadata.framework = Framework.XGBOOST.value
    metadata.input_features = ["age", "income", "credit_history"]
    metadata.output_schema = {"score": "float", "probability": "float"}
    metadata.file_path = "/tmp/test_models/model.pkl"
    metadata.file_hash = "abc123def456"
    metadata.file_size = 1024
    metadata.status = ModelStatus.ACTIVE.value
    metadata.is_production = True
    metadata.ab_test_group = None
    metadata.created_by = "test_user"
    metadata.created_at = datetime.now()
    metadata.updated_at = datetime.now()
    metadata.deployed_at = None
    metadata.description = "测试模型"
    metadata.tags = {"department": "risk", "version": "v1"}
    metadata.model_params = {"scorecard": {"base_score": 600, "pdo": 50}}
    metadata.metadata_json = {}
    return metadata


@pytest.fixture
def sample_fraud_metadata():
    """示例反欺诈模型元数据"""
    metadata = MagicMock()
    metadata.model_id = "MDL_20240315_EFGH5678"
    metadata.model_name = "fraud_model"
    metadata.model_version = "1.0.0"
    metadata.task_type = TaskType.FRAUD_DETECTION.value
    metadata.model_type = ModelType.RANDOM_FOREST.value
    metadata.framework = Framework.SKLEARN.value
    metadata.input_features = ["ip_risk", "device_risk", "amount", "velocity"]
    metadata.output_schema = {"fraud_probability": "float", "risk_score": "float"}
    metadata.file_path = "/tmp/test_models/fraud_model.pkl"
    metadata.file_hash = "xyz789abc123"
    metadata.file_size = 2048
    metadata.status = ModelStatus.ACTIVE.value
    metadata.is_production = True
    metadata.created_by = "test_user"
    metadata.created_at = datetime.now()
    return metadata


# ==================== 模型加载器 fixtures ====================

@pytest.fixture
def model_loader():
    """创建模型加载器实例"""
    return ModelLoader(cache_ttl=60, max_concurrent_loads=2, max_retries=2)


@pytest.fixture
def model_registry():
    """创建模型注册中心实例"""
    return ModelRegistry()


@pytest.fixture
def inference_engine():
    """创建推理引擎实例"""
    return InferenceEngine(cache_size=10, cache_ttl=60)


# ==================== 临时文件 fixtures ====================

@pytest.fixture
def temp_model_file():
    """创建临时模型文件"""
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
        import joblib
        import numpy as np
        from sklearn.linear_model import LogisticRegression

        X = np.random.randn(100, 3)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)
        model = LogisticRegression()
        model.fit(X, y)
        joblib.dump(model, tmp.name)
        tmp_path = Path(tmp.name)

    yield tmp_path

    if tmp_path.exists():
        tmp_path.unlink()


# ==================== 样本数据 fixtures ====================

@pytest.fixture
def sample_features():
    """示例特征数据"""
    return {
        "age": 35,
        "income": 50000,
        "credit_history": 720,
        "debt_ratio": 0.35,
        "employment_years": 5
    }


@pytest.fixture
def sample_fraud_features():
    """示例反欺诈特征数据"""
    return {
        "ip_risk": 0.8,
        "device_risk": 0.6,
        "amount": 10000,
        "velocity": 3,
        "transaction_hour": 14
    }


# ==================== 日志 fixtures ====================

@pytest.fixture
def mock_logging():
    """模拟日志模块"""
    with patch('datamind.core.logging.log_audit') as mock_audit, \
            patch('datamind.core.logging.log_performance') as mock_performance, \
            patch('datamind.core.logging.context.get_request_id', return_value="test-request-id"), \
            patch('datamind.core.logging.context.get_trace_id', return_value="test-trace-id"), \
            patch('datamind.core.logging.context.get_span_id', return_value="test-span-id"), \
            patch('datamind.core.logging.context.get_parent_span_id', return_value="test-parent-id"):
        yield {
            'audit': mock_audit,
            'performance': mock_performance
        }


# ==================== 上下文 fixtures ====================

@pytest.fixture
def mock_context():
    """模拟上下文"""
    with patch('datamind.core.logging.context.get_request_id', return_value="test-request-id"), \
            patch('datamind.core.logging.context.get_trace_id', return_value="test-trace-id"), \
            patch('datamind.core.logging.context.get_span_id', return_value="test-span-id"), \
            patch('datamind.core.logging.context.get_parent_span_id', return_value="test-parent-id"):
        yield