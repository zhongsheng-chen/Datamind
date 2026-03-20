# tests/ml/test_model_registry.py
"""测试模型注册中心"""

import pytest
import io
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, patch

from datamind.core.ml.model_registry import ModelRegistry
from datamind.core.ml.exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException
)
from datamind.core.domain.enums import ModelStatus, AuditAction


# 测试辅助类（避免被 pytest 误认为是测试类）
class _TestModelConfig:
    def __init__(self, models_path, max_size=1024 * 1024 * 1024, allowed_extensions=None):
        self.models_path = models_path
        self.max_size = max_size
        if allowed_extensions is None:
            self.allowed_extensions = ['.pkl', '.json', '.txt', '.pt', '.h5', '.onnx', '.cbm', '.bin']


class _TestSettings:
    def __init__(self, model_config):
        self.model = model_config


class TestModelRegistry:
    """测试 ModelRegistry 类"""

    @pytest.fixture
    def temp_storage_path(self):
        """临时存储路径"""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def registry(self, temp_storage_path):
        """创建模型注册中心实例"""
        test_config = _TestModelConfig(models_path=str(temp_storage_path))
        test_settings = _TestSettings(model_config=test_config)

        registry = ModelRegistry(settings=test_settings)
        return registry

    @pytest.fixture
    def sample_model_file(self):
        """示例模型文件"""
        content = b"test model content"
        return io.BytesIO(content)

    @pytest.fixture
    def sample_scorecard_params(self):
        """示例评分卡参数"""
        return {
            'base_score': 600,
            'pdo': 50,
            'min_score': 300,
            'max_score': 900,
            'direction': 'higher_better'
        }

    @pytest.fixture
    def sample_risk_config(self):
        """示例风险配置"""
        return {
            'levels': {
                'low': {'min': 0, 'max': 0.3},
                'medium': {'min': 0.3, 'max': 0.7},
                'high': {'min': 0.7, 'max': 1}
            }
        }

    def test_init(self, registry, temp_storage_path):
        """测试初始化"""
        assert registry.storage_path == temp_storage_path
        assert registry.max_size == 1024 * 1024 * 1024
        assert '.pkl' in registry.allowed_extensions
        assert registry.storage_path.exists()

    def test_register_model_success(
            self, registry, mock_db_session, sample_model_file,
            sample_scorecard_params, mock_request_id
    ):
        """测试成功注册模型"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        model_id = registry.register_model(
            model_name="test_model",
            model_version="1.0.0",
            task_type="scoring",
            model_type="xgboost",
            framework="xgboost",
            input_features=["feature1", "feature2"],
            output_schema={"score": "float"},
            created_by="test_user",
            model_file=sample_model_file,
            description="测试模型",
            scorecard_params=sample_scorecard_params,
            ip_address="127.0.0.1"
        )

        assert model_id.startswith("MDL_")
        assert len(model_id) > 10

    def test_register_model_duplicate(
            self, registry, mock_db_session, sample_model_file
    ):
        """测试注册重复模型"""
        mock_model = MagicMock()
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        with pytest.raises(ModelAlreadyExistsException) as exc:
            registry.register_model(
                model_name="test_model",
                model_version="1.0.0",
                task_type="scoring",
                model_type="xgboost",
                framework="xgboost",
                input_features=["feature1"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file
            )

        assert "已存在" in str(exc.value)

    def test_register_model_invalid_scorecard_params(
            self, registry, mock_db_session, sample_model_file
    ):
        """测试注册模型时评分卡参数无效"""
        invalid_params = {
            'base_score': -100,
            'pdo': 50,
            'min_score': 300,
            'max_score': 900
        }

        with pytest.raises(ModelValidationException) as exc:
            registry.register_model(
                model_name="test_model",
                model_version="1.0.0",
                task_type="scoring",
                model_type="xgboost",
                framework="xgboost",
                input_features=["feature1"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file,
                scorecard_params=invalid_params
            )

        assert "base_score" in str(exc.value)

    def test_register_model_invalid_risk_config(
            self, registry, mock_db_session, sample_model_file
    ):
        """测试注册模型时风险配置无效"""
        invalid_config = {
            'levels': {
                'low': {'min': 0, 'max': 0.5},
                'high': {'min': 0.3, 'max': 1}
            }
        }

        with pytest.raises(ModelValidationException) as exc:
            registry.register_model(
                model_name="test_model",
                model_version="1.0.0",
                task_type="fraud_detection",
                model_type="xgboost",
                framework="xgboost",
                input_features=["feature1"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file,
                risk_config=invalid_config
            )

        assert "重叠" in str(exc.value)

    def test_activate_model_success(
            self, registry, mock_db_session, mock_request_id
    ):
        """测试成功激活模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.status = ModelStatus.INACTIVE.value
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.activate_model(
            model_id="MDL_123",
            operator="test_user",
            reason="测试激活",
            ip_address="127.0.0.1"
        )

        assert mock_model.status == ModelStatus.ACTIVE.value

    def test_activate_model_not_found(self, registry, mock_db_session):
        """测试激活不存在的模型"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ModelNotFoundException) as exc:
            registry.activate_model("MDL_NOT_EXIST", "test_user")

        assert "未找到" in str(exc.value)

    def test_deactivate_model_success(
            self, registry, mock_db_session, mock_request_id
    ):
        """测试成功停用模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.status = ModelStatus.ACTIVE.value
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.deactivate_model(
            model_id="MDL_123",
            operator="test_user",
            reason="测试停用",
            ip_address="127.0.0.1"
        )

        assert mock_model.status == ModelStatus.INACTIVE.value

    def test_promote_to_production_success(
            self, registry, mock_db_session, mock_request_id
    ):
        """测试提升为生产模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = "scoring"
        mock_model.is_production = False
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.promote_to_production(
            model_id="MDL_123",
            operator="test_user",
            reason="测试提升",
            ip_address="127.0.0.1"
        )

        assert mock_model.is_production is True

    def test_get_model_info_success(self, registry, mock_db_session):
        """测试获取模型信息"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = "scoring"
        mock_model.model_type = "xgboost"
        mock_model.framework = "xgboost"
        mock_model.file_path = "/tmp/model.pkl"
        mock_model.file_hash = "abc123"
        mock_model.file_size = 1024
        mock_model.input_features = ["feature1"]
        mock_model.output_schema = {"score": "float"}
        mock_model.model_params = {}
        mock_model.status = ModelStatus.ACTIVE.value
        mock_model.is_production = False
        mock_model.ab_test_group = None
        mock_model.created_by = "test_user"
        mock_model.created_at = datetime.now()
        mock_model.updated_at = datetime.now()
        mock_model.deployed_at = None
        mock_model.description = "测试模型"
        mock_model.tags = {}

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        info = registry.get_model_info("MDL_123")

        assert info is not None
        assert info['model_id'] == "MDL_123"
        assert info['model_name'] == "test_model"
        assert info['model_version'] == "1.0.0"

    def test_get_model_info_not_found(self, registry, mock_db_session):
        """测试获取不存在的模型信息"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        info = registry.get_model_info("MDL_NOT_EXIST")
        assert info is None

    def test_list_models(self, registry, mock_db_session):
        """测试列出模型"""
        mock_model1 = MagicMock()
        mock_model1.model_id = "MDL_1"
        mock_model1.model_name = "model1"
        mock_model1.model_version = "1.0.0"
        mock_model1.task_type = "scoring"
        mock_model1.model_type = "xgboost"
        mock_model1.framework = "xgboost"
        mock_model1.status = ModelStatus.ACTIVE.value
        mock_model1.is_production = True
        mock_model1.ab_test_group = None
        mock_model1.created_by = "user1"
        mock_model1.created_at = datetime.now()

        mock_model2 = MagicMock()
        mock_model2.model_id = "MDL_2"
        mock_model2.model_name = "model2"
        mock_model2.model_version = "2.0.0"
        mock_model2.task_type = "fraud_detection"
        mock_model2.model_type = "lightgbm"
        mock_model2.framework = "lightgbm"
        mock_model2.status = ModelStatus.INACTIVE.value
        mock_model2.is_production = False
        mock_model2.ab_test_group = None
        mock_model2.created_by = "user2"
        mock_model2.created_at = datetime.now()

        mock_db_session.query.return_value.filter_by.return_value.all.return_value = [mock_model1, mock_model2]
        mock_db_session.query.return_value.order_by.return_value.all.return_value = [mock_model1, mock_model2]

        models = registry.list_models()

        assert len(models) == 2
        assert models[0]['model_id'] == "MDL_1"
        assert models[1]['model_id'] == "MDL_2"

    def test_list_models_with_filters(self, registry, mock_db_session):
        """测试带筛选条件的列表"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_1"
        mock_model.model_name = "model1"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = "scoring"
        mock_model.model_type = "xgboost"
        mock_model.framework = "xgboost"
        mock_model.status = ModelStatus.ACTIVE.value
        mock_model.is_production = True
        mock_model.ab_test_group = None
        mock_model.created_by = "user1"
        mock_model.created_at = datetime.now()

        # 模拟查询链
        mock_query = mock_db_session.query.return_value
        mock_query.filter_by.return_value.filter_by.return_value.all.return_value = [mock_model]
        mock_query.filter_by.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_model]

        models = registry.list_models(task_type="scoring", status=ModelStatus.ACTIVE.value)

        assert len(models) == 1
        assert models[0]['task_type'] == "scoring"

    def test_get_model_history(self, registry, mock_db_session):
        """测试获取模型历史"""
        mock_history = MagicMock()
        mock_history.operation = AuditAction.CREATE.value
        mock_history.operator = "user1"
        mock_history.operation_time = datetime.now()
        mock_history.reason = None
        mock_history.details = {}

        mock_db_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_history]

        history = registry.get_model_history("MDL_123")

        assert len(history) == 1
        assert history[0]['operation'] == AuditAction.CREATE.value
        assert history[0]['operator'] == "user1"

    def test_get_model_params(self, registry, mock_db_session):
        """测试获取模型参数"""
        mock_model = MagicMock()
        mock_model.model_params = {
            'scorecard': {'base_score': 600},
            'risk_config': {'levels': {'low': {'min': 0, 'max': 0.3}}}
        }
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        params = registry.get_model_params("MDL_123")

        assert params is not None
        assert 'scorecard' in params
        assert params['scorecard']['base_score'] == 600
        assert 'risk_config' in params

    def test_update_model_params_success(
            self, registry, mock_db_session, sample_scorecard_params, mock_request_id
    ):
        """测试成功更新模型参数"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = "scoring"
        mock_model.model_params = {}
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.update_model_params(
            model_id="MDL_123",
            operator="test_user",
            scorecard_params=sample_scorecard_params,
            reason="测试更新",
            ip_address="127.0.0.1"
        )

        assert 'scorecard' in mock_model.model_params
        assert mock_model.model_params['scorecard']['base_score'] == 600

    def test_update_model_params_invalid_scorecard(
            self, registry, mock_db_session
    ):
        """测试更新无效的评分卡参数"""
        mock_model = MagicMock()
        mock_model.task_type = "scoring"
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        invalid_params = {'base_score': -100}

        with pytest.raises(ModelValidationException):
            registry.update_model_params(
                model_id="MDL_123",
                operator="test_user",
                scorecard_params=invalid_params
            )

    def test_save_model_file_success(self, registry, sample_model_file):
        """测试保存模型文件成功"""
        file_hash, file_size, file_path = registry._save_model_file(
            sample_model_file, "MDL_123", "1.0.0", "sklearn"
        )

        assert file_size > 0
        assert file_hash is not None
        assert file_path.exists()
        assert file_path.suffix == '.pkl'

    def test_save_model_file_creates_directory(self, registry, sample_model_file):
        """测试保存模型文件时创建目录"""
        file_path = registry.storage_path / "MDL_123" / "versions" / "model_1.0.0.pkl"
        assert not file_path.parent.exists()

        registry._save_model_file(sample_model_file, "MDL_123", "1.0.0", "sklearn")

        assert file_path.parent.exists()
        assert file_path.exists()

    def test_validate_model_file_success(self, registry, tmp_path):
        """测试验证模型文件成功"""
        file_path = tmp_path / "model.pkl"
        file_path.write_bytes(b"test content")

        registry._validate_model_file(file_path, "sklearn", "xgboost")

    def test_validate_model_file_not_exists(self, registry):
        """测试验证不存在的模型文件"""
        file_path = Path("/tmp/not_exists.pkl")

        with pytest.raises(ModelValidationException) as exc:
            registry._validate_model_file(file_path, "sklearn", "xgboost")

        assert "不存在" in str(exc.value)

    def test_validate_model_file_empty(self, registry, tmp_path):
        """测试验证空模型文件"""
        file_path = tmp_path / "empty.pkl"
        file_path.write_bytes(b"")

        with pytest.raises(ModelValidationException) as exc:
            registry._validate_model_file(file_path, "sklearn", "xgboost")

        assert "为空" in str(exc.value)

    def test_create_snapshot(self, registry, mock_db_session):
        """测试创建元数据快照"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_123"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = "scoring"
        mock_model.model_type = "xgboost"
        mock_model.framework = "xgboost"
        mock_model.input_features = ["feature1"]
        mock_model.output_schema = {"score": "float"}
        mock_model.created_by = "test_user"
        mock_model.created_at = datetime.now()

        snapshot = registry._create_snapshot(mock_model)

        assert snapshot['model_id'] == "MDL_123"
        assert snapshot['model_name'] == "test_model"
        assert snapshot['model_version'] == "1.0.0"
        assert snapshot['task_type'] == "scoring"