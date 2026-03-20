# Datamind/datamind/core/domain/enums.py

"""领域枚举定义

定义系统中使用的所有枚举类型，包括任务类型、模型类型、框架、状态等。

这些枚举在整个系统中共享，确保状态和类型的一致性，避免魔法字符串散落在代码各处。

设计原则：
  - 类型安全：使用枚举替代字符串，编译时检查
  - 统一管理：所有枚举集中定义，便于维护
  - 自文档化：每个枚举值都有清晰的说明
  - 可扩展性：支持添加新的枚举值而不影响现有代码

使用方式：
  - 在模型字段中使用枚举值：status = ModelStatus.ACTIVE.value
  - 在业务逻辑中判断类型：if task_type == TaskType.SCORING.value
  - 在API响应中返回枚举值：{"status": ModelStatus.ACTIVE.value}

枚举分类：
  - TaskType: 机器学习任务类型（评分/反欺诈）
  - ModelType: 具体算法类型（决策树/神经网络等）
  - Framework: 机器学习框架（sklearn/xgboost等）
  - ModelStatus: 模型生命周期状态
  - AuditAction: 审计操作类型
  - DeploymentEnvironment: 部署环境
  - ABTestStatus: A/B测试状态
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
        SKLEARN: 传统机器学习算法 Scikit-learn 框架
        XGBOOST: 梯度提升 XGBoost 原生框架
        LIGHTGBM: 高性能梯度提升 LightGBM 原生框架
        TORCH: 深度学习 PyTorch 框架
        TENSORFLOW: 深度学习 TensorFlow 框架
        ONNX: 模型交换格式运行时 ONNX 框架
        CATBOOST: 类别特征优化原生 CatBoost 框架
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

    状态流转：
        INACTIVE → ACTIVE → DEPRECATED → ARCHIVED
           ↓          ↓
        (删除)    (回滚)

    属性:
        ACTIVE: 活跃状态，模型可用，可正常推理
        INACTIVE: 非活跃状态，暂不可用，可随时激活
        DEPRECATED: 已弃用，不建议使用，但保留兼容性
        ARCHIVED: 已归档，仅用于历史查询，不可用于推理
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class AuditAction(str, Enum):
    """审计操作类型枚举

    定义系统中所有需要审计的操作类型，用于记录用户行为。

    分类：
        模型管理: CREATE, UPDATE, DELETE, VERSION_ADD, VERSION_SWITCH
        状态变更: ACTIVATE, DEACTIVATE, DEPRECATE, ARCHIVE, RESTORE
        部署相关: PROMOTE, ROLLBACK
        使用相关: INFERENCE, DOWNLOAD
        配置相关: CONFIG_CHANGE

    属性:
        CREATE: 创建操作 - 模型注册、测试创建等
        UPDATE: 更新操作 - 修改配置、更新元数据
        DELETE: 删除操作 - 删除模型、删除测试
        ACTIVATE: 激活操作 - 激活模型或测试
        DEACTIVATE: 停用操作 - 停用模型或测试
        DEPRECATE: 弃用操作 - 标记为弃用
        ARCHIVE: 归档操作 - 归档历史数据
        RESTORE: 恢复操作 - 从归档恢复
        VERSION_ADD: 添加版本 - 模型版本升级
        VERSION_SWITCH: 切换版本 - 切换使用版本
        DOWNLOAD: 下载操作 - 下载模型文件
        INFERENCE: 推理调用 - API调用记录
        PROMOTE: 提升版本 - 提升到生产环境
        ROLLBACK: 回滚操作 - 回滚到之前版本
        CONFIG_CHANGE: 配置变更 - 修改系统配置
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

    定义模型部署的环境类型，用于区分不同环境的配置和行为。

    属性:
        DEVELOPMENT: 开发环境 - 用于本地开发调试
        TESTING: 测试环境 - 用于自动化测试
        STAGING: 预发布环境 - 用于上线前验证
        PRODUCTION: 生产环境 - 真实业务流量
    """
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class ABTestStatus(str, Enum):
    """A/B测试状态枚举

    定义A/B测试的生命周期状态。

    状态流转：
        DRAFT → RUNNING → COMPLETED
          ↓        ↓
       (编辑)   PAUSED → RUNNING

    属性:
        DRAFT: 草稿状态，测试尚未开始，可编辑配置
        RUNNING: 运行中状态，测试正在进行，分配流量
        PAUSED: 暂停状态，测试临时停止，可恢复
        COMPLETED: 已完成状态，测试正常结束，有结果
        TERMINATED: 已终止状态，测试被提前终止，无有效结果
    """
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"