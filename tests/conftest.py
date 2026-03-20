# tests/conftest.py
"""Pytest 共享 fixtures 和配置"""

import pytest
import joblib
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from datamind.core.db.models import ModelMetadata
from datamind.core.domain.enums import TaskType, ModelStatus
from datamind.core.ml.model_loader import ModelLoader


@pytest.fixture(autouse=True)
def mock_settings():
    """模拟设置"""
    with patch('datamind.config.get_settings') as m1, \
            patch('datamind.core.db.database.get_settings') as m2:
        mock_settings = MagicMock()

        # 模型设置
        mock_settings.model = MagicMock()
        mock_settings.model.models_path = "/tmp/test_models"
        mock_settings.model.max_size = 1024 * 1024 * 1024
        mock_settings.model.allowed_extensions = ['.pkl', '.json', '.txt', '.pt', '.h5', '.onnx', '.cbm', '.bin']

        # 数据库设置
        mock_settings.database = MagicMock()
        mock_settings.database.url = "postgresql://test"
        mock_settings.database.readonly_url = None
        mock_settings.database.pool_size = 5
        mock_settings.database.max_overflow = 10
        mock_settings.database.pool_timeout = 30
        mock_settings.database.pool_recycle = 3600
        mock_settings.database.echo = False

        # 应用设置
        mock_settings.app = MagicMock()
        mock_settings.app.app_name = "test_app"

        m1.return_value = mock_settings
        m2.return_value = mock_settings

        yield mock_settings


@pytest.fixture
def mock_db_session():
    """模拟数据库会话"""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.flush = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.rollback = MagicMock()
    mock_session.close = MagicMock()

    # 设置 query 链式调用
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_query.filter_by.return_value.first.return_value = None
    mock_query.filter_by.return_value.all.return_value = []
    mock_query.all.return_value = []
    mock_query.order_by.return_value = mock_query
    mock_session.query.return_value = mock_query

    mock_context = MagicMock()
    mock_context.__enter__.return_value = mock_session
    mock_context.__exit__.return_value = None

    mock_db_manager = MagicMock()
    mock_db_manager.session_scope.return_value = mock_context
    mock_db_manager.get_session.return_value = mock_session

    with patch('datamind.core.db.database.db_manager', mock_db_manager), \
            patch('datamind.core.db.database.get_db', return_value=mock_context):
        yield mock_session


@pytest.fixture
def fresh_model_loader():
    return ModelLoader()


@pytest.fixture
def mock_model_loader(fresh_model_loader):
    """模拟模型导入"""
    with patch('datamind.core.ml.inference.model_loader', fresh_model_loader):
        yield fresh_model_loader


@pytest.fixture
def mock_log_manager():
    """模拟日志管理器"""
    mock = MagicMock()
    mock.log_audit = MagicMock()
    mock.log_access = MagicMock()
    mock.log_performance = MagicMock()
    mock.get_request_id = MagicMock(return_value="test-request-id")
    return mock


@pytest.fixture
def mock_request_id():
    """模拟请求ID"""
    with patch('datamind.core.logging.context.get_request_id') as m:
        m.return_value = "test-request-id"
        yield "test-request-id"


@pytest.fixture
def mock_trace_id():
    """模拟 trace_id（链路追踪ID）"""
    with patch('datamind.core.logging.context.get_trace_id') as m:
        m.return_value = "test-trace-id"
        yield "test-trace-id"


@pytest.fixture
def mock_span_id():
    """模拟 span_id（调用层级ID）"""
    with patch('datamind.core.logging.context.get_span_id') as m:
        m.return_value = "test-span-id"
        yield "test-span-id"


@pytest.fixture
def sample_model_metadata():
    return ModelMetadata(
        model_id="MDL_20240315_ABCD1234",
        model_name="test_model",
        model_version="1.0.0",
        task_type=TaskType.SCORING.value,
        model_type="xgboost",
        framework="xgboost",
        file_path="/tmp/test_models/MDL_20240315_ABCD1234/versions/model_1.0.0.json",
        file_hash="abc123def456",
        file_size=1024,
        input_features=["age", "income", "credit_history"],
        output_schema={"score": "float"},
        status=ModelStatus.ACTIVE.value,
        is_production=False,
        created_by="test_user",
        created_at=datetime.now()
    )


@pytest.fixture
def temp_model_file():
    """创建临时 sklearn 模型"""
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
        from sklearn.linear_model import LogisticRegression
        import numpy as np

        X = np.random.randn(100, 3)
        y = (X[:, 0] + X[:, 1] > 0).astype(int)

        model = LogisticRegression()
        model.fit(X, y)

        joblib.dump(model, tmp.name)
        tmp_path = Path(tmp.name)

    yield tmp_path

    tmp_path.unlink(missing_ok=True)


@pytest.fixture
def sample_features():
    return {
        "age": 35,
        "income": 50000,
        "credit_history": 720
    }