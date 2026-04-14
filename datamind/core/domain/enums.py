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
  - TaskType: 机器学习任务类型（评分/反欺诈/分类）
  - ModelType: 具体算法类型（决策树/神经网络等）
  - Framework: 机器学习框架（sklearn/xgboost等）
  - ModelStatus: 模型生命周期状态
  - AuditAction: 审计操作类型
  - PerformanceOperation: 性能监控操作类型
  - DeploymentEnvironment: 部署环境
  - ABTestStatus: A/B测试状态
  - UserRole: 用户角色
  - UserStatus: 用户状态
  - DataType: 特征数据类型（数值/分类/布尔）
  - DatabaseOperation: 数据库操作类型
"""

from enum import Enum


class TaskType(str, Enum):
    """任务类型枚举

    定义机器学习任务类型。

    属性:
        SCORING: 评分任务
        FRAUD_DETECTION: 反欺诈检测任务
        CLASSIFICATION: 通用分类任务
    """
    SCORING = "scoring"
    FRAUD_DETECTION = "fraud_detection"
    CLASSIFICATION = "classification"


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
    MODEL_CREATE = "model_create"
    MODEL_UPDATE = "model_update"
    MODEL_DELETE = "model_delete"
    MODEL_QUERY = "model_query"
    MODEL_ACTIVATE = "model_activate"
    MODEL_DEACTIVATE = "model_deactivate"
    MODEL_DEPRECATE = "model_deprecate"
    MODEL_ARCHIVE = "model_archive"
    MODEL_RESTORE = "model_restore"
    MODEL_VERSION_ADD = "model_version_add"
    MODEL_VERSION_DELETE = "model_version_delete"
    MODEL_VERSION_SWITCH = "model_version_switch"
    MODEL_PROMOTE = "model_promote"
    MODEL_ROLLBACK = "model_rollback"

    # 模型运行时
    MODEL_LOAD = "model_load"
    MODEL_UNLOAD = "model_unload"
    MODEL_WARM_UP = "model_warm_up"
    MODEL_INFERENCE = "model_inference"
    MODEL_BATCH_INFERENCE = "model_batch_inference"
    MODEL_DOWNLOAD = "model_download"
    MODEL_SAVE = "model_save"
    MODEL_MIGRATE = "model_migrate"

    # A/B测试
    AB_TEST_CREATE = "ab_test_create"
    AB_TEST_UPDATE = "ab_test_update"
    AB_TEST_START = "ab_test_start"
    AB_TEST_PAUSE = "ab_test_pause"
    AB_TEST_RESUME = "ab_test_resume"
    AB_TEST_COMPLETE = "ab_test_complete"
    AB_TEST_TERMINATE = "ab_test_terminate"
    AB_TEST_ASSIGNMENT = "ab_test_assignment"
    AB_TEST_RECORD = "ab_test_record"
    AB_TEST_ERROR = "ab_test_error"

    # 认证授权
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_PASSWORD_CHANGE = "user_password_change"
    USER_PASSWORD_RESET = "user_password_reset"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    API_KEY_UPDATE = "api_key_update"

    # 安全防护
    CORS_PREFLIGHT = "cors_preflight"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    IP_BLOCKED = "ip_blocked"
    INVALID_SIGNATURE = "invalid_signature"
    INVALID_TIMESTAMP = "invalid_timestamp"
    REQUEST_TOO_LARGE = "request_too_large"

    # 系统配置
    CONFIG_CREATE = "config_create"
    CONFIG_UPDATE = "config_update"
    CONFIG_DELETE = "config_delete"
    CONFIG_RELOAD = "config_reload"

    # 数据库管理
    DB_INITIALIZE = "db_initialize"
    DB_CREATE_ENGINE = "db_create_engine"
    DB_GET_SESSION = "db_get_session"
    DB_HEALTH_CHECK = "db_health_check"
    DB_TRANSACTION = "db_transaction"
    DB_TRANSACTION_ERROR = "db_transaction_error"
    DB_RECONNECT = "db_reconnect"
    DB_INIT_SCHEMA = "db_init_schema"

    # 复制监控
    REPLICATION_STATUS = "replication_status"
    SYNC_STATUS = "sync_status"
    REPLICATION_SLOTS = "replication_slots"
    REPLICATION_METRICS = "replication_metrics"
    REPLICATION_ALERT = "replication_alert"

    # 数据管理
    DATABASE_BACKUP = "database_backup"
    DATABASE_RESTORE = "database_restore"
    DATABASE_MIGRATE = "database_migrate"
    DATA_EXPORT = "data_export"
    DATA_IMPORT = "data_import"

    # 存储管理
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"
    FILE_DELETE = "file_delete"
    FILE_COPY = "file_copy"
    FILE_MOVE = "file_move"
    FILE_LIST = "file_list"
    FILE_METADATA = "file_metadata"

    # 监控告警
    MONITORING_COLLECT = "monitoring_collect"
    ALERT_TRIGGER = "alert_trigger"
    SLOW_REQUEST = "slow_request"
    SLOW_QUERY = "slow_query"

    # 审计日志
    AUDIT_LOG_QUERY = "audit_log_query"
    AUDIT_LOG_EXPORT = "audit_log_export"

    # 性能监控
    PERFORMANCE_METRIC = "performance_metric"
    DB_QUERY_STATS = "db_query_stats"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"


class PerformanceOperation(str, Enum):
    """性能监控操作类型枚举

    定义需要记录性能指标的操作类型，用于性能监控和优化分析。

    分类说明：
        数据库操作: 数据库初始化、连接池、事务、查询等
        复制监控: 复制状态检查、复制槽状态等
        模型操作: 模型加载、推理、预热、保存等
        A/B测试: 测试分配、测试创建、测试启动、测试完成、结果记录等
        API操作: 请求处理、响应生成等
        缓存操作: 缓存读写、命中率等

    属性定义：
        数据库操作
            DB_INITIALIZE: 数据库初始化 - 创建连接池和引擎
            DB_CREATE_ENGINE: 创建数据库引擎 - 建立数据库连接
            DB_GET_SESSION: 获取会话 - 从连接池获取会话
            DB_TRANSACTION: 数据库事务 - 事务提交耗时
            DB_RECONNECT: 数据库重连 - 重新建立连接
            DB_QUERY: 数据库查询 - SQL查询执行耗时
            DB_BATCH_QUERY: 批量查询 - 批量SQL查询耗时
            DB_INSERT: 数据库插入 - 插入操作耗时
            DB_UPDATE: 数据库更新 - 更新操作耗时
            DB_DELETE: 数据库删除 - 删除操作耗时
            DB_INIT_SCHEMA: 初始化表结构 - 创建数据库表

        复制监控
            REPLICATION_STATUS_CHECK: 复制状态检查 - 主备复制状态查询
            REPLICATION_METRICS: 复制指标采集 - 复制延迟等指标

        模型操作
            MODEL_LOAD: 模型加载 - 从存储加载模型到内存
            MODEL_UNLOAD: 模型卸载 - 从内存卸载模型
            MODEL_INFERENCE: 模型推理 - 单次预测耗时
            MODEL_BATCH_INFERENCE: 批量推理 - 批量预测耗时
            MODEL_WARM_UP: 模型预热 - 预热推理耗时
            MODEL_SAVE: 模型保存 - 保存模型到存储
            MODEL_VALIDATION: 模型验证 - 验证模型文件完整性

        A/B测试
            AB_TEST_ASSIGNMENT: A/B测试分配 - 用户分组分配耗时
            AB_TEST_CREATE: A/B测试创建 - 创建测试配置耗时
            AB_TEST_START: A/B测试启动 - 启动测试耗时
            AB_TEST_COMPLETE: A/B测试完成 - 完成测试耗时
            AB_TEST_RECORD: A/B测试记录 - 记录测试结果耗时

        API操作
            API_REQUEST: API请求 - 完整请求处理耗时
            API_PREDICT: 预测API - /predict 端点耗时
            API_HEALTH: 健康检查 - /health 端点耗时
            API_METRICS: 指标API - /metrics 端点耗时

        缓存操作
            CACHE_GET: 缓存读取 - 从缓存获取数据耗时
            CACHE_SET: 缓存写入 - 写入缓存耗时
            CACHE_DELETE: 缓存删除 - 删除缓存耗时
            CACHE_CLEAR: 缓存清理 - 清理过期缓存耗时

        特征处理
            FEATURE_EXTRACT: 特征提取 - 从原始数据提取特征
            FEATURE_TRANSFORM: 特征转换 - 特征预处理耗时
            FEATURE_VALIDATION: 特征验证 - 验证特征完整性

        评分卡专用
            SCORECARD_CALCULATE: 评分卡计算 - 计算模型总分
            SCORECARD_FEATURE_SCORE: 特征分计算 - 计算各特征分数
    """

    # 数据库操作
    DB_INITIALIZE = "db_initialize"
    DB_CREATE_ENGINE = "db_create_engine"
    DB_GET_SESSION = "db_get_session"
    DB_TRANSACTION = "db_transaction"
    DB_RECONNECT = "db_reconnect"
    DB_QUERY = "db_query"
    DB_BATCH_QUERY = "db_batch_query"
    DB_INSERT = "db_insert"
    DB_UPDATE = "db_update"
    DB_DELETE = "db_delete"
    DB_INIT_SCHEMA = "db_init_schema"

    # 复制监控
    REPLICATION_STATUS_CHECK = "replication_status_check"
    REPLICATION_METRICS = "replication_metrics"

    # 模型操作
    MODEL_LOAD = "model_load"
    MODEL_UNLOAD = "model_unload"
    MODEL_INFERENCE = "model_inference"
    MODEL_BATCH_INFERENCE = "model_batch_inference"
    MODEL_WARM_UP = "model_warm_up"
    MODEL_SAVE = "model_save"
    MODEL_VALIDATION = "model_validation"

    # A/B测试
    AB_TEST_ASSIGNMENT = "ab_test_assignment"
    AB_TEST_CREATE = "ab_test_create"
    AB_TEST_START = "ab_test_start"
    AB_TEST_COMPLETE = "ab_test_complete"
    AB_TEST_RECORD = "ab_test_record"

    # API操作
    API_REQUEST = "api_request"
    API_PREDICT = "api_predict"
    API_HEALTH = "api_health"
    API_METRICS = "api_metrics"

    # 缓存操作
    CACHE_GET = "cache_get"
    CACHE_SET = "cache_set"
    CACHE_DELETE = "cache_delete"
    CACHE_CLEAR = "cache_clear"

    # 特征处理
    FEATURE_EXTRACT = "feature_extract"
    FEATURE_TRANSFORM = "feature_transform"
    FEATURE_VALIDATION = "feature_validation"

    # 评分卡专用
    SCORECARD_CALCULATE = "scorecard_calculate"
    SCORECARD_FEATURE_SCORE = "scorecard_feature_score"

    @classmethod
    def get_all(cls) -> list:
        """获取所有性能操作类型"""
        return [item.value for item in cls]

    @classmethod
    def get_by_category(cls, category: str) -> list:
        """根据分类获取性能操作类型

        参数:
            category: 分类名称（db/replication/model/ab_test/api/cache/feature/scorecard）

        返回:
            该分类下的所有操作类型列表
        """
        category_map = {
            'db': [
                cls.DB_INITIALIZE, cls.DB_CREATE_ENGINE, cls.DB_GET_SESSION,
                cls.DB_TRANSACTION, cls.DB_RECONNECT, cls.DB_QUERY,
                cls.DB_BATCH_QUERY, cls.DB_INSERT, cls.DB_UPDATE, cls.DB_DELETE,
                cls.DB_INIT_SCHEMA
            ],
            'replication': [cls.REPLICATION_STATUS_CHECK, cls.REPLICATION_METRICS],
            'model': [
                cls.MODEL_LOAD, cls.MODEL_UNLOAD, cls.MODEL_INFERENCE,
                cls.MODEL_BATCH_INFERENCE, cls.MODEL_WARM_UP, cls.MODEL_SAVE,
                cls.MODEL_VALIDATION
            ],
            'ab_test': [
                cls.AB_TEST_ASSIGNMENT, cls.AB_TEST_CREATE,
                cls.AB_TEST_START, cls.AB_TEST_COMPLETE, cls.AB_TEST_RECORD
            ],
            'api': [cls.API_REQUEST, cls.API_PREDICT, cls.API_HEALTH, cls.API_METRICS],
            'cache': [cls.CACHE_GET, cls.CACHE_SET, cls.CACHE_DELETE, cls.CACHE_CLEAR],
            'feature': [cls.FEATURE_EXTRACT, cls.FEATURE_TRANSFORM, cls.FEATURE_VALIDATION],
            'scorecard': [cls.SCORECARD_CALCULATE, cls.SCORECARD_FEATURE_SCORE],
        }
        ops = category_map.get(category, [])
        return [op.value for op in ops]


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
        LOCKED: 已锁定 - 因多次登录失败临时锁定
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LOCKED = "locked"


class DataType(str, Enum):
    """数据类型枚举

    定义特征数据的基本类型，用于数据验证和预处理。

    属性:
        NUMERIC: 数值类型（整数、浮点数）
        CATEGORICAL: 分类类型（字符串、有限枚举值）
        BOOLEAN: 布尔类型（True/False）
        ANY: 任意类型（不进行类型检查）
    """
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    ANY = "any"


class DatabaseOperation(str, Enum):
    """数据库操作类型枚举

    定义异步/同步数据库写入器支持的操作类型。
    用于技术层面的数据库操作，与业务审计的 AuditAction 区分。

    属性:
        INSERT: 插入单条记录
        UPDATE: 更新记录
        DELETE: 删除记录
        BATCH_INSERT: 批量插入
        BATCH_UPDATE: 批量更新
        UPSERT: 插入或更新（PostgreSQL ON CONFLICT）
    """
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"
    BATCH_INSERT = "batch_insert"
    BATCH_UPDATE = "batch_update"
    UPSERT = "upsert"


__all__ = [
    'TaskType',
    'ModelType',
    'Framework',
    'ModelStatus',
    'AuditAction',
    'PerformanceOperation',
    'DeploymentEnvironment',
    'ABTestStatus',
    'UserRole',
    'UserStatus',
    'DataType',
    'DatabaseOperation',
]