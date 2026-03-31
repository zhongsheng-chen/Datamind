# tests/ml/test_model_registry_integration.py

"""模型注册中心集成测试 - 使用 conftest 的 fixtures"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from io import BytesIO
import pickle

from datamind.core.ml.model import ModelRegistry
from datamind.core.common.exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
)
from datamind.core.domain.enums import ModelStatus, TaskType, ModelType, Framework


class TestModelRegistryIntegration:
    """模型注册中心集成测试"""

    @pytest.fixture
    def registry(self):
        """创建模型注册中心实例"""
        return ModelRegistry()

    @pytest.fixture
    def sample_model_file(self):
        """创建示例模型文件"""
        model_data = {"test": "model", "version": "1.0"}
        file_obj = BytesIO()
        pickle.dump(model_data, file_obj)
        file_obj.seek(0)
        return file_obj

    @pytest.fixture
    def sample_scorecard_params(self):
        """示例评分卡参数"""
        return {
            "base_score": 600,
            "pdo": 50,
            "min_score": 300,
            "max_score": 900,
            "direction": "lower_better"
        }

    @pytest.fixture
    def sample_risk_config(self):
        """示例风险配置"""
        return {
            "levels": {
                "low": {"max": 0.3},
                "medium": {"min": 0.3, "max": 0.6},
                "high": {"min": 0.6}
            }
        }

    # ==================== 注册模型测试 ====================

    def test_register_model_success(
        self, registry, sample_model_file, sample_scorecard_params,
        mock_db_session, mock_bentoml_for_registry
    ):
        """测试注册模型 - 成功"""
        # 设置 mock_db_session
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        # 设置 mock_bentoml_for_registry
        mock_bento_model = MagicMock()
        mock_bento_model.tag = MagicMock()
        mock_bento_model.tag.__str__.return_value = "test_model:latest"
        mock_bento_model.version = "latest"
        mock_bentoml_for_registry.xgboost.save_model.return_value = mock_bento_model

        # 注册模型
        model_id = registry.register_model(
            model_name="test_model",
            model_version="1.0.0",
            task_type=TaskType.SCORING.value,
            model_type=ModelType.XGBOOST.value,
            framework=Framework.XGBOOST.value,
            input_features=["age", "income"],
            output_schema={"score": "float"},
            created_by="test_user",
            model_file=sample_model_file,
            description="测试模型",
            scorecard_params=sample_scorecard_params
        )

        # 验证
        assert model_id.startswith("MDL_")
        assert len(model_id) > 10
        mock_bentoml_for_registry.xgboost.save_model.assert_called_once()
        assert mock_db_session.add.call_count >= 2
        mock_db_session.commit.assert_called()

    def test_register_fraud_model_success(
        self, registry, sample_model_file, sample_risk_config,
        mock_db_session, mock_bentoml_for_registry
    ):
        """测试注册反欺诈模型 - 成功"""
        # 设置 mock_db_session
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        # 设置 mock_bentoml_for_registry
        mock_bento_model = MagicMock()
        mock_bento_model.tag = MagicMock()
        mock_bento_model.tag.__str__.return_value = "fraud_model:latest"
        mock_bento_model.version = "latest"
        mock_bentoml_for_registry.sklearn.save_model.return_value = mock_bento_model

        # 注册模型
        model_id = registry.register_model(
            model_name="fraud_model",
            model_version="1.0.0",
            task_type=TaskType.FRAUD_DETECTION.value,
            model_type=ModelType.RANDOM_FOREST.value,
            framework=Framework.SKLEARN.value,
            input_features=["ip_risk", "device_risk", "amount"],
            output_schema={"fraud_probability": "float"},
            created_by="test_user",
            model_file=sample_model_file,
            description="反欺诈模型",
            risk_config=sample_risk_config
        )

        # 验证
        assert model_id.startswith("MDL_")
        mock_bentoml_for_registry.sklearn.save_model.assert_called_once()
        mock_db_session.commit.assert_called()

    def test_register_model_already_exists(
        self, registry, sample_model_file, mock_db_session
    ):
        """测试注册模型 - 模型已存在"""
        # 设置 mock_db_session 返回已存在模型
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        with pytest.raises(ModelAlreadyExistsException):
            registry.register_model(
                model_name="existing_model",
                model_version="1.0.0",
                task_type=TaskType.SCORING.value,
                model_type=ModelType.XGBOOST.value,
                framework=Framework.XGBOOST.value,
                input_features=["age"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file
            )

    def test_register_model_empty_input_features(
        self, registry, sample_model_file, mock_db_session, mock_bentoml_for_registry
    ):
        """测试注册模型 - 空输入特征"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        mock_bento_model = MagicMock()
        mock_bento_model.tag = MagicMock()
        mock_bento_model.tag.__str__.return_value = "test:latest"
        mock_bentoml_for_registry.xgboost.save_model.return_value = mock_bento_model

        model_id = registry.register_model(
            model_name="test_model",
            model_version="1.0.0",
            task_type=TaskType.SCORING.value,
            model_type=ModelType.XGBOOST.value,
            framework=Framework.XGBOOST.value,
            input_features=[],
            output_schema={"score": "float"},
            created_by="test_user",
            model_file=sample_model_file
        )

        assert model_id.startswith("MDL_")

    # ==================== 模型状态管理测试 ====================

    def test_activate_model(self, registry, mock_db_session):
        """测试激活模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.status = ModelStatus.INACTIVE.value
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.activate_model("MDL_TEST", "test_user", "测试激活")

        assert mock_model.status == ModelStatus.ACTIVE.value
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    def test_activate_model_not_found(self, registry, mock_db_session):
        """测试激活模型 - 模型不存在"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ModelNotFoundException):
            registry.activate_model("MDL_NOT_EXIST", "test_user")

    def test_deactivate_model(self, registry, mock_db_session):
        """测试停用模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.status = ModelStatus.ACTIVE.value
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.deactivate_model("MDL_TEST", "test_user", "测试停用")

        assert mock_model.status == ModelStatus.INACTIVE.value
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    def test_promote_to_production(self, registry, mock_db_session):
        """测试提升为生产模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.SCORING.value
        mock_model.is_production = False
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.promote_to_production("MDL_TEST", "test_user", "提升为生产")

        assert mock_model.is_production is True
        mock_db_session.query.return_value.filter_by.return_value.update.assert_called()
        mock_db_session.commit.assert_called()

    def test_archive_model(self, registry, mock_db_session):
        """测试归档模型"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.status = ModelStatus.ACTIVE.value
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        registry.archive_model("MDL_TEST", "test_user", "测试归档")

        assert mock_model.status == ModelStatus.ARCHIVED.value
        assert mock_model.archived_at is not None
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    # ==================== 查询模型测试 ====================

    def test_get_model_info_success(self, registry, mock_db_session):
        """测试获取模型信息 - 成功"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.SCORING.value
        mock_model.model_type = ModelType.XGBOOST.value
        mock_model.framework = Framework.XGBOOST.value
        mock_model.file_path = "/path/to/model"
        mock_model.file_hash = "abc123"
        mock_model.file_size = 1024
        mock_model.input_features = ["age", "income"]
        mock_model.output_schema = {"score": "float"}
        mock_model.model_params = {}
        mock_model.status = ModelStatus.ACTIVE.value
        mock_model.is_production = True
        mock_model.ab_test_group = None
        mock_model.created_by = "test_user"
        mock_model.created_at = datetime.now()
        mock_model.updated_at = None
        mock_model.deployed_at = None
        mock_model.description = "测试模型"
        mock_model.tags = {"env": "test"}
        mock_model.metadata_json = {}

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        result = registry.get_model_info("MDL_TEST")

        assert result is not None
        assert result['model_id'] == "MDL_TEST"
        assert result['model_name'] == "test_model"
        assert result['task_type'] == TaskType.SCORING.value
        assert result['model_version'] == "1.0.0"
        assert result['status'] == ModelStatus.ACTIVE.value
        assert result['is_production'] is True
        assert result['tags'] == {"env": "test"}

    def test_get_model_info_not_found(self, registry, mock_db_session):
        """测试获取模型信息 - 不存在"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        result = registry.get_model_info("MDL_NOT_EXIST")
        assert result is None

    def test_list_models(self, registry, mock_db_session):
        """测试列出模型"""
        mock_model1 = MagicMock()
        mock_model1.model_id = "MDL_001"
        mock_model1.model_name = "model_1"
        mock_model1.model_version = "1.0.0"
        mock_model1.task_type = TaskType.SCORING.value
        mock_model1.model_type = ModelType.XGBOOST.value
        mock_model1.framework = Framework.XGBOOST.value
        mock_model1.status = ModelStatus.ACTIVE.value
        mock_model1.is_production = True
        mock_model1.ab_test_group = None
        mock_model1.created_by = "user1"
        mock_model1.created_at = datetime.now()

        mock_model2 = MagicMock()
        mock_model2.model_id = "MDL_002"
        mock_model2.model_name = "model_2"
        mock_model2.model_version = "2.0.0"
        mock_model2.task_type = TaskType.FRAUD_DETECTION.value
        mock_model2.model_type = ModelType.RANDOM_FOREST.value
        mock_model2.framework = Framework.SKLEARN.value
        mock_model2.status = ModelStatus.INACTIVE.value
        mock_model2.is_production = False
        mock_model2.ab_test_group = None
        mock_model2.created_by = "user2"
        mock_model2.created_at = datetime.now()

        mock_db_session.query.return_value.order_by.return_value.all.return_value = [mock_model1, mock_model2]

        result = registry.list_models()

        assert len(result) == 2
        assert result[0]['model_id'] == "MDL_001"
        assert result[1]['model_id'] == "MDL_002"

    def test_list_models_with_filters(self, registry, mock_db_session):
        """测试列出模型 - 带筛选条件"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_001"
        mock_model.model_name = "model_1"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.SCORING.value
        mock_model.model_type = ModelType.XGBOOST.value
        mock_model.framework = Framework.XGBOOST.value
        mock_model.status = ModelStatus.ACTIVE.value
        mock_model.is_production = True
        mock_model.ab_test_group = None
        mock_model.created_by = "user1"
        mock_model.created_at = datetime.now()

        mock_db_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [mock_model]

        result = registry.list_models(
            task_type=TaskType.SCORING.value,
            status=ModelStatus.ACTIVE.value,
            is_production=True
        )

        assert len(result) == 1
        assert result[0]['task_type'] == TaskType.SCORING.value
        assert result[0]['status'] == ModelStatus.ACTIVE.value
        assert result[0]['is_production'] is True

    def test_get_model_history(self, registry, mock_db_session):
        """测试获取模型历史"""
        mock_history1 = MagicMock()
        mock_history1.operation = "CREATE"
        mock_history1.operator = "user1"
        mock_history1.operation_time = datetime.now()
        mock_history1.reason = None
        mock_history1.details = {"file_size": 1024}

        mock_history2 = MagicMock()
        mock_history2.operation = "ACTIVATE"
        mock_history2.operator = "user1"
        mock_history2.operation_time = datetime.now()
        mock_history2.reason = "测试激活"
        mock_history2.details = {"before_status": "inactive"}

        mock_db_session.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [
            mock_history2, mock_history1
        ]

        result = registry.get_model_history("MDL_TEST")

        assert len(result) == 2
        assert result[0]['operation'] == "ACTIVATE"
        assert result[0]['reason'] == "测试激活"
        assert result[1]['operation'] == "CREATE"
        assert result[1]['details'] == {"file_size": 1024}

    # ==================== 更新模型测试 ====================

    def test_update_model_params_scorecard(self, registry, mock_db_session):
        """测试更新模型参数 - 评分卡"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.SCORING.value
        mock_model.model_params = {}
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        scorecard_params = {"base_score": 650, "pdo": 60}

        registry.update_model_params(
            model_id="MDL_TEST",
            operator="test_user",
            scorecard_params=scorecard_params,
            reason="更新评分卡参数"
        )

        assert mock_model.model_params['scorecard'] == scorecard_params
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    def test_update_model_params_risk_config(self, registry, mock_db_session):
        """测试更新模型参数 - 风险配置"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.FRAUD_DETECTION.value
        mock_model.model_params = {}
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = mock_model

        risk_config = {"levels": {"low": {"max": 0.3}, "high": {"min": 0.7}}}

        registry.update_model_params(
            model_id="MDL_TEST",
            operator="test_user",
            risk_config=risk_config,
            reason="更新风险配置"
        )

        assert mock_model.model_params['risk_config'] == risk_config
        mock_db_session.add.assert_called()
        mock_db_session.commit.assert_called()

    def test_update_model_params_not_found(self, registry, mock_db_session):
        """测试更新模型参数 - 模型不存在"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ModelNotFoundException):
            registry.update_model_params(
                model_id="MDL_NOT_EXIST",
                operator="test_user",
                scorecard_params={"base_score": 650}
            )

    # ==================== BentoML 操作测试 ====================

    def test_delete_from_bentoml_success(self, registry, mock_bentoml_for_registry):
        """测试从 BentoML 删除模型 - 成功"""
        mock_bentoml_for_registry.models.delete = MagicMock()

        result = registry.delete_from_bentoml("MDL_TEST")
        assert result is True
        mock_bentoml_for_registry.models.delete.assert_called_with("MDL_TEST")

    def test_delete_from_bentoml_failure(self, registry, mock_bentoml_for_registry):
        """测试从 BentoML 删除模型 - 失败"""
        from bentoml.exceptions import BentoMLException
        mock_bentoml_for_registry.models.delete = MagicMock(side_effect=BentoMLException("删除失败"))

        result = registry.delete_from_bentoml("MDL_TEST")
        assert result is False