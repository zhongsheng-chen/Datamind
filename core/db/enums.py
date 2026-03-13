# core/enums.py
import enum
from typing import Dict, Set, List


class TaskType(str, enum.Enum):
    """任务类型"""
    SCORING = "scoring"
    FRAUD_DETECTION = "fraud_detection"


class ModelType(str, enum.Enum):
    """模型类型"""
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    LOGISTIC_REGRESSION = "logistic_regression"
    CATBOOST = "catboost"
    NEURAL_NETWORK = "neural_network"


class Framework(str, enum.Enum):
    """模型框架"""
    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    TORCH = "torch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    CATBOOST = "catboost"


class ModelStatus(str, enum.Enum):
    """模型状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AuditAction(str, enum.Enum):
    """审计操作类型"""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    ACTIVATE = "ACTIVATE"
    DEACTIVATE = "DEACTIVATE"
    DEPRECATE = "DEPRECATE"
    ARCHIVE = "ARCHIVE"
    RESTORE = "RESTORE"
    VERSION_ADD = "VERSION_ADD"
    VERSION_SWITCH = "VERSION_SWITCH"
    DOWNLOAD = "DOWNLOAD"
    INFERENCE = "INFERENCE"
    PROMOTE = "PROMOTE"
    ROLLBACK = "ROLLBACK"
    CONFIG_CHANGE = "CONFIG_CHANGE"


class DeploymentEnvironment(str, enum.Enum):
    """部署环境"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ABTestStatus(str, enum.Enum):
    """A/B测试状态"""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


# 框架和模型类型的兼容性映射
FRAMEWORK_MODEL_COMPATIBILITY: Dict[Framework, Set[ModelType]] = {
    Framework.SKLEARN: {
        ModelType.DECISION_TREE,
        ModelType.RANDOM_FOREST,
        ModelType.LOGISTIC_REGRESSION
    },
    Framework.XGBOOST: {
        ModelType.XGBOOST
    },
    Framework.LIGHTGBM: {
        ModelType.LIGHTGBM
    },
    Framework.CATBOOST: {
        ModelType.CATBOOST
    },
    Framework.TORCH: {
        ModelType.NEURAL_NETWORK,
        ModelType.LOGISTIC_REGRESSION
    },
    Framework.TENSORFLOW: {
        ModelType.NEURAL_NETWORK,
        ModelType.LOGISTIC_REGRESSION
    },
    Framework.ONNX: {
        ModelType.DECISION_TREE,
        ModelType.RANDOM_FOREST,
        ModelType.XGBOOST,
        ModelType.LIGHTGBM,
        ModelType.CATBOOST,
        ModelType.LOGISTIC_REGRESSION,
        ModelType.NEURAL_NETWORK
    }
}


def validate_framework_model_compatibility(framework: Framework, model_type: ModelType) -> bool:
    """验证框架和模型类型的兼容性"""
    compatible_models = FRAMEWORK_MODEL_COMPATIBILITY.get(framework, set())
    return model_type in compatible_models


def get_compatible_frameworks(model_type: ModelType) -> List[Framework]:
    """获取指定模型类型支持的框架列表"""
    return [f for f, models in FRAMEWORK_MODEL_COMPATIBILITY.items() if model_type in models]


def get_compatible_model_types(framework: Framework) -> List[ModelType]:
    """获取指定框架支持的模型类型列表"""
    return list(FRAMEWORK_MODEL_COMPATIBILITY.get(framework, set()))