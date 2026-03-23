# datamind/core/domain/enums.py

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
    """
    审计操作类型枚举

    定义系统中所有需要审计的操作类型，用于记录用户行为。

    分类说明：
        模型生命周期: 模型的创建、更新、删除、版本管理、状态变更
        模型运行时: 模型的加载、卸载、预热、推理
        部署管理: 模型的部署、提升、回滚
        A/B测试: 测试的创建、启动、暂停、完成、分配、记录
        认证授权: 登录、登出、密码修改、认证成功/失败
        API密钥: 密钥的创建、吊销
        安全防护: CORS预检、限流触发、IP阻止、签名验证、时间戳验证
        系统配置: 配置变更
        数据库管理: 数据库初始化、连接池、事务、复制监控、备份恢复
        存储管理: 文件上传、下载、删除、复制、移动、列出、元数据操作
        监控告警: 性能指标、告警触发
        审计日志: 日志查询、导出

    属性定义：
        模型生命周期
            MODEL_CREATE: 创建模型 - 注册新模型
            MODEL_UPDATE: 更新模型 - 修改模型元数据、配置
            MODEL_DELETE: 删除模型 - 软删除/硬删除模型
            MODEL_QUERY: 查询模型 - 查询已有模型
            MODEL_ACTIVATE: 激活模型 - 将模型状态设为活跃
            MODEL_DEACTIVATE: 停用模型 - 将模型状态设为非活跃
            MODEL_DEPRECATE: 弃用模型 - 标记模型为弃用
            MODEL_ARCHIVE: 归档模型 - 将模型归档
            MODEL_RESTORE: 恢复模型 - 从归档恢复模型
            MODEL_VERSION_ADD: 添加版本 - 为模型添加新版本
            MODEL_VERSION_DELETE: 删除版本 - 删除已有模型版本
            MODEL_VERSION_SWITCH: 切换版本 - 切换使用的模型版本
            MODEL_PROMOTE: 提升版本 - 提升模型为生产版本
            MODEL_ROLLBACK: 回滚版本 - 回滚到之前版本

        模型运行时
            MODEL_LOAD: 加载模型 - 将模型加载到内存
            MODEL_UNLOAD: 卸载模型 - 从内存卸载模型
            MODEL_WARM_UP: 预热模型 - 执行预热推理
            MODEL_INFERENCE: 推理调用 - 单次模型推理
            MODEL_BATCH_INFERENCE: 批量推理 - 批量模型推理
            MODEL_DOWNLOAD: 下载模型 - 下载模型文件
            MODEL_SAVE: 保存模型 - 保存模型文件到存储
            MODEL_MIGRATE: 迁移模型 - 将模型迁移到其他存储后端

        A/B测试
            AB_TEST_CREATE: 创建A/B测试 - 创建新的A/B测试配置
            AB_TEST_UPDATE: 更新A/B测试 - 修改测试配置
            AB_TEST_START: 启动测试 - 开始运行A/B测试
            AB_TEST_PAUSE: 暂停测试 - 暂停A/B测试
            AB_TEST_RESUME: 恢复测试 - 恢复暂停的测试
            AB_TEST_COMPLETE: 完成测试 - 正常结束测试
            AB_TEST_TERMINATE: 终止测试 - 提前终止测试
            AB_TEST_ASSIGNMENT: 测试分配 - 用户分配到测试组
            AB_TEST_RECORD: 测试记录 - 记录测试结果
            AB_TEST_ERROR: 测试错误 - A/B测试过程中发生错误

        认证授权
            USER_LOGIN: 用户登录
            USER_LOGOUT: 用户登出
            USER_PASSWORD_CHANGE: 密码修改
            USER_PASSWORD_RESET: 密码重置
            AUTH_SUCCESS: 认证成功 - JWT/API Key/Basic Auth认证成功
            AUTH_FAILED: 认证失败 - 认证失败记录
            API_KEY_CREATE: API密钥创建
            API_KEY_REVOKE: API密钥吊销
            API_KEY_UPDATE: API密钥更新

        安全防护
            CORS_PREFLIGHT: CORS预检请求
            RATE_LIMIT_EXCEEDED: 限流触发 - 请求被限流
            IP_BLOCKED: IP被阻止 - IP白/黑名单拦截
            INVALID_SIGNATURE: 无效签名 - 请求签名验证失败
            INVALID_TIMESTAMP: 无效时间戳 - 时间戳验证失败
            REQUEST_TOO_LARGE: 请求过大 - 请求体超过大小限制

        系统配置
            CONFIG_CREATE: 创建配置 - 创建系统配置
            CONFIG_UPDATE: 更新配置 - 修改系统配置
            CONFIG_DELETE: 删除配置 - 删除系统配置
            CONFIG_RELOAD: 配置重载 - 热重载配置

        数据库管理
            DB_INITIALIZE: 数据库初始化
            DB_CREATE_ENGINE: 创建数据库引擎
            DB_GET_SESSION: 获取数据库会话
            DB_HEALTH_CHECK: 数据库健康检查
            DB_TRANSACTION: 数据库事务
            DB_TRANSACTION_ERROR: 数据库事务错误
            DB_RECONNECT: 数据库重新连接
            DB_INIT_SCHEMA: 初始化数据库表结构
            REPLICATION_STATUS: 复制状态检查
            SYNC_STATUS: 同步复制状态检查
            REPLICATION_SLOTS: 复制槽状态检查
            REPLICATION_METRICS: 复制性能指标
            REPLICATION_ALERT: 复制告警

        数据管理
            DATABASE_BACKUP: 数据库备份
            DATABASE_RESTORE: 数据库恢复
            DATABASE_MIGRATE: 数据库迁移
            DATA_EXPORT: 数据导出
            DATA_IMPORT: 数据导入

        存储管理
            FILE_UPLOAD: 文件上传 - 上传/保存文件
            FILE_DOWNLOAD: 文件下载 - 下载/加载文件
            FILE_DELETE: 文件删除 - 删除文件
            FILE_COPY: 文件复制 - 复制文件
            FILE_MOVE: 文件移动 - 移动文件
            FILE_LIST: 列出文件 - 列出目录中的文件
            FILE_METADATA: 文件元数据 - 获取/修改文件元数据

        监控告警
            MONITORING_COLLECT: 监控数据收集
            ALERT_TRIGGER: 告警触发
            SLOW_REQUEST: 慢请求检测
            SLOW_QUERY: 慢查询检测

        审计日志
            AUDIT_LOG_QUERY: 审计日志查询
            AUDIT_LOG_EXPORT: 审计日志导出

        性能监控
            PERFORMANCE_METRIC: 性能指标记录
            DB_QUERY_STATS: 数据库查询统计
            CACHE_HIT: 缓存命中
            CACHE_MISS: 缓存未命中
    """

    # 模型生命周期
    MODEL_CREATE = "MODEL_CREATE"
    MODEL_UPDATE = "MODEL_UPDATE"
    MODEL_DELETE = "MODEL_DELETE"
    MODEL_QUERY = "MODEL_QUERY"
    MODEL_ACTIVATE = "MODEL_ACTIVATE"
    MODEL_DEACTIVATE = "MODEL_DEACTIVATE"
    MODEL_DEPRECATE = "MODEL_DEPRECATE"
    MODEL_ARCHIVE = "MODEL_ARCHIVE"
    MODEL_RESTORE = "MODEL_RESTORE"
    MODEL_VERSION_ADD = "MODEL_VERSION_ADD"
    MODEL_VERSION_DELETE = "MODEL_VERSION_DELETE"
    MODEL_VERSION_SWITCH = "MODEL_VERSION_SWITCH"
    MODEL_PROMOTE = "MODEL_PROMOTE"
    MODEL_ROLLBACK = "MODEL_ROLLBACK"

    # 模型运行时
    MODEL_LOAD = "MODEL_LOAD"
    MODEL_UNLOAD = "MODEL_UNLOAD"
    MODEL_WARM_UP = "MODEL_WARM_UP"
    MODEL_INFERENCE = "MODEL_INFERENCE"
    MODEL_BATCH_INFERENCE = "MODEL_BATCH_INFERENCE"
    MODEL_DOWNLOAD = "MODEL_DOWNLOAD"
    MODEL_SAVE = "MODEL_SAVE"
    MODEL_MIGRATE = "MODEL_MIGRATE"

    # A/B测试
    AB_TEST_CREATE = "AB_TEST_CREATE"
    AB_TEST_UPDATE = "AB_TEST_UPDATE"
    AB_TEST_START = "AB_TEST_START"
    AB_TEST_PAUSE = "AB_TEST_PAUSE"
    AB_TEST_RESUME = "AB_TEST_RESUME"
    AB_TEST_COMPLETE = "AB_TEST_COMPLETE"
    AB_TEST_TERMINATE = "AB_TEST_TERMINATE"
    AB_TEST_ASSIGNMENT = "AB_TEST_ASSIGNMENT"
    AB_TEST_RECORD = "AB_TEST_RECORD"
    AB_TEST_ERROR = "AB_TEST_ERROR"

    # 认证授权
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_PASSWORD_CHANGE = "USER_PASSWORD_CHANGE"
    USER_PASSWORD_RESET = "USER_PASSWORD_RESET"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILED = "AUTH_FAILED"
    API_KEY_CREATE = "API_KEY_CREATE"
    API_KEY_REVOKE = "API_KEY_REVOKE"
    API_KEY_UPDATE = "API_KEY_UPDATE"

    # 安全防护
    CORS_PREFLIGHT = "CORS_PREFLIGHT"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    IP_BLOCKED = "IP_BLOCKED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    REQUEST_TOO_LARGE = "REQUEST_TOO_LARGE"

    # 系统配置
    CONFIG_CREATE = "CONFIG_CREATE"
    CONFIG_UPDATE = "CONFIG_UPDATE"
    CONFIG_DELETE = "CONFIG_DELETE"
    CONFIG_RELOAD = "CONFIG_RELOAD"

    # 数据库管理
    DB_INITIALIZE = "DB_INITIALIZE"
    DB_CREATE_ENGINE = "DB_CREATE_ENGINE"
    DB_GET_SESSION = "DB_GET_SESSION"
    DB_HEALTH_CHECK = "DB_HEALTH_CHECK"
    DB_TRANSACTION = "DB_TRANSACTION"
    DB_TRANSACTION_ERROR = "DB_TRANSACTION_ERROR"
    DB_RECONNECT = "DB_RECONNECT"
    DB_INIT_SCHEMA = "DB_INIT_SCHEMA"

    # 复制监控
    REPLICATION_STATUS = "REPLICATION_STATUS"
    SYNC_STATUS = "SYNC_STATUS"
    REPLICATION_SLOTS = "REPLICATION_SLOTS"
    REPLICATION_METRICS = "REPLICATION_METRICS"
    REPLICATION_ALERT = "REPLICATION_ALERT"

    # 数据管理
    DATABASE_BACKUP = "DATABASE_BACKUP"
    DATABASE_RESTORE = "DATABASE_RESTORE"
    DATABASE_MIGRATE = "DATABASE_MIGRATE"
    DATA_EXPORT = "DATA_EXPORT"
    DATA_IMPORT = "DATA_IMPORT"

    # 存储管理
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    FILE_DELETE = "FILE_DELETE"
    FILE_COPY = "FILE_COPY"
    FILE_MOVE = "FILE_MOVE"
    FILE_LIST = "FILE_LIST"
    FILE_METADATA = "FILE_METADATA"

    # 监控告警
    MONITORING_COLLECT = "MONITORING_COLLECT"
    ALERT_TRIGGER = "ALERT_TRIGGER"
    SLOW_REQUEST = "SLOW_REQUEST"
    SLOW_QUERY = "SLOW_QUERY"

    # 审计日志
    AUDIT_LOG_QUERY = "AUDIT_LOG_QUERY"
    AUDIT_LOG_EXPORT = "AUDIT_LOG_EXPORT"

    # 性能监控
    PERFORMANCE_METRIC = "PERFORMANCE_METRIC"
    DB_QUERY_STATS = "DB_QUERY_STATS"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"


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


class UserRole(str, Enum):
    """用户角色枚举

    定义用户在系统中的角色权限。

    属性:
        ADMIN: 管理员 - 拥有所有权限，可以管理模型、查看审计日志、管理API密钥
        DEVELOPER: 开发者 - 可以注册模型、进行推理、查看自己的模型
        ANALYST: 分析师 - 可以查看模型、进行推理，不能修改模型
        API_USER: API用户 - 仅能通过API进行推理，不能访问管理界面
    """
    ADMIN = "admin"
    DEVELOPER = "developer"
    ANALYST = "analyst"
    API_USER = "api_user"


class UserStatus(str, Enum):
    """用户状态枚举

    属性:
        ACTIVE: 活跃状态 - 正常使用
        INACTIVE: 非活跃状态 - 临时禁用
        SUSPENDED: 已暂停 - 因违规等暂停使用
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"