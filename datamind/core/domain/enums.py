# Datamind/datamind/core/domain/enums.py

"""领域枚举定义

定义系统中使用的所有枚举类型，包括任务类型、模型类型、框架、状态等。

这些枚举在整个系统中共享，确保状态和类型的一致性。
"""

from enum import Enum


class TaskType(str, Enum):
    """任务类型枚举

    定义机器学习任务类型，如评分、反欺诈等。

    属性:
        SCORING: 评分任务
        FRAUD_DETECTION: 反欺诈检测任务
    """
    SCORING = "scoring"
    FRAUD_DETECTION = "fraud_detection"


class ModelType(str, Enum):
    """模型类型枚举

    定义具体的机器学习模型算法类型。

    属性:
        DECISION_TREE: 决策树模型
        RANDOM_FOREST: 随机森林模型
        XGBOOST: XGBoost 梯度提升模型
        LIGHTGBM: LightGBM 梯度提升模型
        LOGISTIC_REGRESSION: 逻辑回归模型
        CATBOOST: CatBoost 梯度提升模型
        NEURAL_NETWORK: 神经网络模型
    """
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    LOGISTIC_REGRESSION = "logistic_regression"
    CATBOOST = "catboost"
    NEURAL_NETWORK = "neural_network"


class Framework(str, Enum):
    """机器学习框架枚举

    定义支持的机器学习框架，用于模型训练和部署。

    属性:
        SKLEARN: Scikit-learn 框架
        XGBOOST: XGBoost 原生框架
        LIGHTGBM: LightGBM 原生框架
        TORCH: PyTorch 框架
        TENSORFLOW: TensorFlow 框架
        ONNX: ONNX 运行时框架
        CATBOOST: CatBoost 原生框架
    """
    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    TORCH = "torch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    CATBOOST = "catboost"


class ModelStatus(str, Enum):
    """模型状态枚举

    定义模型在整个生命周期中的状态。

    属性:
        ACTIVE: 活跃状态，模型可用
        INACTIVE: 非活跃状态，暂不可用
        DEPRECATED: 已弃用，不建议使用
        ARCHIVED: 已归档，仅用于历史查询
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AuditAction(str, Enum):
    """审计操作类型枚举

    定义系统中所有需要审计的操作类型。

    属性:
        CREATE: 创建操作
        UPDATE: 更新操作
        DELETE: 删除操作
        ACTIVATE: 激活操作
        DEACTIVATE: 停用操作
        DEPRECATE: 弃用操作
        ARCHIVE: 归档操作
        RESTORE: 恢复操作
        VERSION_ADD: 添加版本
        VERSION_SWITCH: 切换版本
        DOWNLOAD: 下载操作
        INFERENCE: 推理调用
        PROMOTE: 提升版本（如到生产）
        ROLLBACK: 回滚操作
        CONFIG_CHANGE: 配置变更
    """
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


class DeploymentEnvironment(str, Enum):
    """部署环境枚举

    定义模型部署的环境类型。

    属性:
        DEVELOPMENT: 开发环境
        TESTING: 测试环境
        STAGING: 预发布环境
        PRODUCTION: 生产环境
    """
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ABTestStatus(str, Enum):
    """A/B测试状态枚举

    定义A/B测试的生命周期状态。

    属性:
        DRAFT: 草稿状态，测试尚未开始
        RUNNING: 运行中状态，测试正在进行
        PAUSED: 暂停状态，测试临时停止
        COMPLETED: 已完成状态，测试正常结束
        TERMINATED: 已终止状态，测试被提前终止
    """
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"