# tests/ml/test_model_registry.py

"""测试模型注册中心"""

import pytest
import pickle
from unittest.mock import MagicMock
from datetime import datetime
from io import BytesIO

from datamind.core.ml.model_registry import ModelRegistry
from datamind.core.ml.exceptions import (
    ModelValidationException,
    UnsupportedFrameworkException,
)
from datamind.core.domain.enums import TaskType, ModelType, Framework


class TestModelRegistry:
    """测试模型注册中心"""

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

    # ==================== 参数验证测试 ====================

    def test_validate_scorecard_params_valid(self, registry):
        """测试验证评分卡参数 - 有效"""
        valid_params = {
            "base_score": 600,
            "pdo": 50,
            "min_score": 300,
            "max_score": 900,
            "direction": "lower_better"
        }
        registry._validate_scorecard_params(valid_params)

    def test_validate_scorecard_params_invalid_base_score(self, registry):
        """测试验证评分卡参数 - base_score 无效"""
        with pytest.raises(ModelValidationException):
            registry._validate_scorecard_params({"base_score": -100})

    def test_validate_scorecard_params_invalid_pdo(self, registry):
        """测试验证评分卡参数 - pdo 无效"""
        with pytest.raises(ModelValidationException):
            registry._validate_scorecard_params({"pdo": -10})

    def test_validate_scorecard_params_invalid_min_max_score(self, registry):
        """测试验证评分卡参数 - min_score > max_score"""
        with pytest.raises(ModelValidationException):
            registry._validate_scorecard_params({"min_score": 900, "max_score": 300})

    def test_validate_scorecard_params_invalid_direction(self, registry):
        """测试验证评分卡参数 - direction 无效"""
        with pytest.raises(ModelValidationException):
            registry._validate_scorecard_params({"direction": "invalid"})

    def test_validate_risk_config_missing_levels(self, registry):
        """测试验证风险配置 - 缺少 levels"""
        with pytest.raises(ModelValidationException):
            registry._validate_risk_config({})

    def test_validate_risk_config_valid(self, registry):
        """测试验证风险配置 - 有效"""
        valid_config = {
            "levels": {
                "low": {"max": 0.3},
                "medium": {"min": 0.3, "max": 0.6},
                "high": {"min": 0.6}
            }
        }
        registry._validate_risk_config(valid_config)

    # ==================== 辅助方法测试 ====================

    def test_calculate_file_hash(self, registry, tmp_path):
        """测试计算文件哈希"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        file_hash = registry._calculate_file_hash(test_file)
        assert file_hash is not None
        assert len(file_hash) == 64
        assert isinstance(file_hash, str)

    def test_merge_model_params_with_scorecard(self, registry):
        """测试合并模型参数 - 带评分卡"""
        model_params = {"param1": "value1"}
        scorecard_params = {"base_score": 600}
        result = registry._merge_model_params(
            model_params=model_params,
            scorecard_params=scorecard_params,
            risk_config=None,
            task_type=TaskType.SCORING.value
        )
        assert result['param1'] == "value1"
        assert result['scorecard'] == scorecard_params

    def test_merge_model_params_with_risk(self, registry):
        """测试合并模型参数 - 带风险配置"""
        model_params = {"param1": "value1"}
        risk_config = {"levels": {"low": {"max": 0.3}}}
        result = registry._merge_model_params(
            model_params=model_params,
            scorecard_params=None,
            risk_config=risk_config,
            task_type=TaskType.FRAUD_DETECTION.value
        )
        assert result['param1'] == "value1"
        assert result['risk_config'] == risk_config

    def test_merge_model_params_no_extra(self, registry):
        """测试合并模型参数 - 无额外参数"""
        model_params = {"param1": "value1"}
        result = registry._merge_model_params(
            model_params=model_params,
            scorecard_params=None,
            risk_config=None,
            task_type=TaskType.SCORING.value
        )
        assert result == model_params
        assert 'scorecard' not in result

    def test_create_snapshot(self, registry):
        """测试创建元数据快照"""
        mock_model = MagicMock()
        mock_model.model_id = "MDL_TEST"
        mock_model.model_name = "test_model"
        mock_model.model_version = "1.0.0"
        mock_model.task_type = TaskType.SCORING.value
        mock_model.model_type = ModelType.XGBOOST.value
        mock_model.framework = Framework.XGBOOST.value
        mock_model.created_by = "test_user"
        mock_model.created_at = datetime.now()

        snapshot = registry._create_snapshot(mock_model)

        assert snapshot['model_id'] == "MDL_TEST"
        assert snapshot['model_name'] == "test_model"
        assert snapshot['task_type'] == TaskType.SCORING.value
        assert snapshot['created_by'] == "test_user"

    # ==================== 不支持的框架测试 ====================

    def test_register_model_unsupported_framework(self, registry, sample_model_file):
        """测试注册模型 - 不支持的框架"""
        with pytest.raises(UnsupportedFrameworkException):
            registry.register_model(
                model_name="test_model",
                model_version="1.0.0",
                task_type=TaskType.SCORING.value,
                model_type=ModelType.XGBOOST.value,
                framework="unsupported_framework",
                input_features=["age"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file
            )

    def test_register_model_invalid_framework_model_combo(self, registry, sample_model_file):
        """测试注册模型 - 框架和模型类型不兼容"""
        with pytest.raises(ModelValidationException):
            registry.register_model(
                model_name="test_model",
                model_version="1.0.0",
                task_type=TaskType.SCORING.value,
                model_type=ModelType.XGBOOST.value,
                framework=Framework.SKLEARN.value,
                input_features=["age"],
                output_schema={"score": "float"},
                created_by="test_user",
                model_file=sample_model_file
            )