# Datamind 核心组件

核心业务逻辑模块，包含数据库管理、机器学习模型管理、实验管理和日志系统。

## 目录结构
```text
core/
├── init.py # 模块初始化
├── db/ # 数据库模块
│    ├── init.py
│    ├── database.py # 数据库连接管理
│    ├── models.py # SQLAlchemy数据库模型
│    └── enums.py # 枚举定义
├── ml/ # 机器学习模块
│    ├── init.py
│    ├── model_registry.py # 模型注册中心
│    ├── model_loader.py # 模型热加载器
│    ├── inference.py # 统一推理引擎
│    └── exceptions.py # 异常定义
├── experiment/ # 实验模块
│        ├── init.py
│        └── ab_test.py # A/B测试管理器
│── logging/ # 日志模块
│       ├── init.py
│       ├── bootstrap.py # 缓存启动日志
│       ├── manager.py # 日志管理器
│       ├── formatters.py # 日志格式化器
│       ├── filters.py # 日志过滤器
│       ├── handlers.py # 日志处理器
│       ├── cleanup.py # 日志清理
│       ├── context.py # 日志上下文
│       └── debug.py # 调试工具
└── README.md
```


## 1. 数据库模块 (`core/db/`)

提供PostgreSQL数据库连接管理和数据模型定义。

### 特性

- **连接池管理** - 高效管理数据库连接
- **自动重连** - 连接失败自动重试
- **读写分离** - 支持只读副本
- **事务管理** - 上下文管理器自动处理事务
- **健康检查** - 定期检查数据库连接状态
- **枚举类型** - 完整的枚举定义

### 快速开始

```python
from datamind.core import db_manager, get_db, init_db
from datamind.core import ModelMetadata
from datamind.core import TaskType, ModelStatus

# 初始化数据库连接
db_manager.initialize(
    database_url="postgresql://user:pass@localhost:5432/datamind",
    pool_size=20,
    max_overflow=40
)

# 创建表
init_db()

# 使用会话上下文管理器
with get_db() as session:
    # 查询模型
    models = session.query(ModelMetadata).filter_by(
        task_type=TaskType.SCORING.value,
        status=ModelStatus.ACTIVE.value
    ).all()

    for model in models:
        print(f"模型: {model.model_name} v{model.model_version}")

# 使用事务
with db_manager.transaction() as session:
    model = session.query(ModelMetadata).filter_by(model_id="MDL_123").first()
    model.status = ModelStatus.ACTIVE.value
    session.commit()  # 手动提交
```

### 枚举定义 (`enums.py`)

```python
from datamind.core import (
    TaskType,  # 任务类型: scoring, fraud_detection
    ModelType,  # 模型类型: decision_tree, xgboost, ...
    Framework,  # 模型框架: sklearn, pytorch, ...
    ModelStatus,  # 模型状态: active, inactive, ...
    AuditAction,  # 审计操作: CREATE, UPDATE, ...
    DeploymentEnvironment,  # 部署环境
    ABTestStatus  # A/B测试状态
)

# 验证框架和模型类型兼容性
from datamind.core import validate_framework_model_compatibility

is_compatible = validate_framework_model_compatibility(
    framework=Framework.SKLEARN,
    model_type=ModelType.RANDOM_FOREST
)
print(f"兼容性: {is_compatible}")

# 获取兼容的框架
from datamind.core import get_compatible_frameworks

frameworks = get_compatible_frameworks(ModelType.XGBOOST)
print(f"XGBoost支持的框架: {[f.value for f in frameworks]}")
```

### 数据库模型 (`models.py`)

```python
from datamind.core import (
    ModelMetadata,  # 模型元数据
    ModelVersionHistory,  # 版本历史
    ModelDeployment,  # 部署记录
    ApiCallLog,  # API调用日志
    ModelPerformanceMetrics,  # 性能指标
    AuditLog,  # 审计日志
    ABTestConfig,  # A/B测试配置
    ABTestAssignment,  # A/B测试分配
    SystemConfig  # 系统配置
)

# 查询示例
from datamind.core.db import get_db
from datamind.core import TaskType
from datamind.core import ModelMetadata, AuditLog

with get_db() as session:
    # 获取生产模型
    prod_model = session.query(ModelMetadata).filter_by(
        is_production=True,
        task_type=TaskType.SCORING.value
    ).first()

    # 获取最近审计日志
    recent_audits = session.query(AuditLog).order_by(
        AuditLog.created_at.desc()
    ).limit(10).all()
```

### 数据库管理器 API

| 方法 | 描述 | 参数 | 返回值 |
|-----|-----|-----|------|
| `initialize()` | 初始化连接池 | `database_url`, `pool_size`, ... | `None` |
| `get_session()` | 获取数据库会话 | `engine_name` | `Session` |
| `session_scope()` | 会话上下文管理器 | `engine_name`, `commit` | `Session` |
| `transaction()` | 事务上下文管理器 | `engine_name` | `Session` |
| `reconnect()` | 重新连接 | `engine_name` | `None` |
| `check_health()` | 健康检查 | - | `dict` |
| `dispose_all()` | 释放所有连接 | - | `None` |



## 2. 机器学习模块 (`core/ml/`)

提供模型注册、加载、推理等核心功能。

### 特性

- **模型注册** - 完整的模型生命周期管理  
- **模型加载** - 动态加载 / 卸载模型  
- **统一推理** - 支持评分卡和反欺诈模型  
- **特征重要性** - 自动提取特征重要性  
- **性能监控** - 记录推理时间和成功率  
- **异常处理** - 完善的异常体系  


### 快速开始

```python
from datamind.core import (
    model_registry,  # 模型注册中心
    model_loader,  # 模型加载器
    inference_engine  # 推理引擎
)

# 注册模型
model_id = model_registry.register_model(
    model_name="credit_score_v2",
    model_version="1.0.0",
    task_type="scoring",
    model_type="xgboost",
    framework="xgboost",
    input_features=["age", "income", "credit_history"],
    output_schema={"score": "float"},
    created_by="admin",
    model_file=open("model.json", "rb"),
    scorecard_params={  # 评分卡参数
        "base_score": 600,
        "pdo": 50,
        "min_score": 320,
        "max_score": 960,
        "direction": "lower_better"
    }
)

# 激活模型
model_registry.activate_model(model_id, "admin")

# 加载模型到内存
model_loader.load_model(model_id, "admin")

# 推理预测
result = inference_engine.predict_scorecard(
    model_id=model_id,
    features={"age": 35, "income": 50000, "credit_history": 720},
    application_id="APP001",
    user_id="system"
)

print(f"总分: {result['total_score']}")
print(f"特征分: {result['feature_scores']}")
```

### 模型注册中心 API

| 方法 | 描述 | 参数 | 返回值 |
|-----|-----|-----|------|
| `register_model()` | 注册新模型 | `model_name`, `version`, ... | `model_id` |
| `activate_model()` | 激活模型 | `model_id`, `operator` | `None` |
| `deactivate_model()` | 停用模型 | `model_id`, `operator` | `None` |
| `set_production_model()` | 设为生产模型 | `model_id`, `operator` | `None` |
| `get_model_info()` | 获取模型信息 | `model_id` | `dict` |
| `list_models()` | 列出模型 | `filters` | `list` |
| `get_model_history()` | 获取历史 | `model_id` | `list` |
| `delete_model()` | 删除模型 | `model_id`, `operator` | `None` |
| `update_model_params()` | 更新参数 | `model_id`, `params` | `None` |


### 模型加载器 API

| 方法 | 描述 | 参数 | 返回值 |
|-----|-----|-----|------|
| `load_model()` | 加载模型 | `model_id`, `operator` | `bool` |
| `unload_model()` | 卸载模型 | `model_id`, `operator` | `None` |
| `get_model()` | 获取模型 | `model_id` | `model` |
| `is_loaded()` | 检查是否已加载 | `model_id` | `bool` |
| `get_loaded_models()` | 获取已加载列表 | - | `list` |


### 推理引擎 API

| 方法 | 描述 | 参数 | 返回值 |
|-----|-----|-----|------|
| `predict_scorecard()` | 评分卡预测 | `model_id`, `features`, ... | `dict` |
| `predict_fraud()` | 反欺诈预测 | `model_id`, `features`, ... | `dict` |
| `get_stats()` | 获取统计信息 | - | `dict` |


### 异常处理

```python
from datamind.core.ml.common.exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelLoadException,
    ModelInferenceException
)

try:
    model = model_loader.get_model("invalid_id")
except ModelNotFoundException as e:
    print(f"模型不存在: {e}")
except ModelLoadException as e:
    print(f"模型加载失败: {e}")
```

## 3. 实验模块 (`core/experiment/`)

提供 A/B 测试功能，支持流量分配和结果分析。

### 特性

- **多组测试** - 支持多个实验组  
- **流量分配** - 按权重分配流量  
- **多种策略** - 随机、一致性哈希等  
- **Redis 缓存** - 加速分配查询  
- **结果分析** - 自动分析测试结果  
- **审计日志** - 完整记录测试过程  

---

### 快速开始

```python
from datamind.core.experiment import ab_test_manager
from datetime import datetime, timedelta

# 创建 A/B 测试
test_id = ab_test_manager.create_test(
    test_name="模型对比测试v1",
    task_type="scoring",
    groups=[
        {"name": "A", "weight": 50, "model_id": "MDL_123"},
        {"name": "B", "weight": 50, "model_id": "MDL_456"}
    ],
    created_by="admin",
    traffic_allocation=100,
    assignment_strategy="random",
    start_date=datetime.now(),
    end_date=datetime.now() + timedelta(days=30)
)

# 启动测试
ab_test_manager.start_test(test_id, "admin")

# 获取用户分配
assignment = ab_test_manager.get_assignment(
    test_id=test_id,
    user_id="user123",
    ip_address="192.168.1.1"
)

print(f"分配组: {assignment['group_name']}")
print(f"模型ID: {assignment['model_id']}")

# 记录结果
ab_test_manager.record_result(
    test_id=test_id,
    user_id="user123",
    metrics={
        "score": 725,
        "processing_time_ms": 87
    }
)

# 分析结果
results = ab_test_manager.analyze_results(test_id)
print(f"获胜组: {results['winning_group']}")
```

### A/B 测试配置示例

```python
# 测试组配置
groups = [
    {
        "name": "control",           # 对照组
        "weight": 50,                # 50%流量
        "model_id": "MDL_123"        # 旧模型
    },
    {
        "name": "treatment",         # 实验组
        "weight": 30,                # 30%流量
        "model_id": "MDL_456"        # 新模型
    },
    {
        "name": "champion",          # 冠军组
        "weight": 20,                # 20%流量
        "model_id": "MDL_789"        # 另一个新模型
    }
]

# 获胜标准
winning_criteria = {
    "metric": "score",                # 比较指标
    "higher_is_better": True          # 越高越好
}
```


### A/B 测试管理器 API

| 方法 | 描述 | 参数 | 返回值 |
|-----|-----|-----|------|
| `create_test()` | 创建测试 | `test_name`, `groups`, ... | `test_id` |
| `start_test()` | 启动测试 | `test_id`, `operator` | `None` |
| `stop_test()` | 停止测试 | `test_id`, `operator` | `None` |
| `get_assignment()` | 获取分配 | `test_id`, `user_id` | `dict` |
| `record_result()` | 记录结果 | `test_id`, `user_id`, `metrics` | `None` |
| `analyze_results()` | 分析结果 | `test_id` | `dict` |
| `get_stats()` | 获取统计 | - | `dict` |


## 4. 日志模块 (`core/logging/`)

提供完整的日志管理功能，支持多种格式、时区、脱敏等。

### 特性

- **多格式支持** - 文本、JSON、同时输出  
- **时区处理** - 支持多种时区  
- **敏感信息脱敏** - 自动隐藏敏感数据  
- **日志采样** - 高流量时采样  
- **异步日志** - 高性能异步写入  
- **日志轮转** - 按大小或时间轮转  
- **自动清理** - 定期清理旧日志  
- **审计日志** - 专门用于审计  
- **性能日志** - 记录性能指标  
- **上下文管理** - 请求ID传递  

### 快速开始

```python
from datamind.core import (
    log_manager,
    get_request_id,
    set_request_id,
    debug_print
)
from datamind.config import LoggingConfig

# 初始化日志
config = LoggingConfig.load()
log_manager.initialize(config)

# 设置请求ID
set_request_id("req_abc123")

# 记录审计日志
log_manager.log_audit(
    action="USER_LOGIN",
    user_id="admin",
    ip_address="192.168.1.1",
    details={
        "login_method": "password",
        "browser": "Chrome"
    }
)

# 记录访问日志
log_manager.log_access(
    method="POST",
    path="/api/v1/scoring/predict",
    status=200,
    duration_ms=87.5,
    ip="192.168.1.1",
    user_agent="Mozilla/5.0..."
)

# 记录性能日志
log_manager.log_performance(
    operation="model_inference",
    duration_ms=45.2,
    model_id="MDL_123",
    cpu_usage=25.5
)

# 调试输出
debug_print("ModelRegistry", "模型加载成功", model_id="MDL_123")
```


### 日志配置示例

```python
from datamind.config import LoggingConfig

# 加载配置
config = LoggingConfig.load(env="development")

# 自定义配置
custom_config = LoggingConfig(
    level="INFO",
    format="json",
    timezone="Asia/Shanghai",
    mask_sensitive=True,
    sensitive_fields=["id_number", "phone", "password"],
    enable_audit_log=True,
    enable_performance_log=True,
    retention_days=90
)

# 验证配置
validation = config.validate_all()
if validation['valid']:
    log_manager.initialize(config)
```

### 日志格式示例

#### JSON格式

```json
{
  "@timestamp": "2024-03-15T10:30:00.123+08:00",
  "level": "INFO",
  "logger": "audit",
  "request_id": "req_abc123",
  "action": "MODEL_REGISTER",
  "user_id": "admin",
  "ip_address": "192.168.1.1",
  "details": {
    "model_id": "MDL_123",
    "model_name": "credit_score_v2"
  },
  "result": "SUCCESS"
}
```

#### 文本格式

```text
2024-03-15 10:30:00,123 - audit - INFO - [req_abc123] - 用户 admin 注册模型 MDL_123
```


### 日志管理器 API

| 方法 | 描述 | 参数 |
|-----|-----|-----|
| `initialize()` | 初始化日志 | `config` |
| `log_audit()` | 记录审计日志 | `action`, `user_id`, `details` |
| `log_access()` | 记录访问日志 | `method`, `path`, `status`, ... |
| `log_performance()` | 记录性能日志 | `operation`, `duration_ms`, ... |
| `set_request_id()` | 设置请求ID | `request_id` |
| `get_request_id()` | 获取请求ID | - |
| `get_current_time()` | 获取当前时间 | - |
| `reload_config()` | 重载配置 | `new_config` |
| `watch_config_changes()` | 监控配置变化 | `interval` |
| `cleanup()` | 清理资源 | - |


### 调试工具

```python
from datamind.core import (
    in_debug,
    set_debug,
    debug_print
)

# 启用调试模式
set_debug(True)

# 条件调试输出
if in_debug():
    print("调试信息")

# 带标签的调试输出
debug_print("ModelLoader", "开始加载模型", model_id="MDL_123")
```


### 上下文管理

```python
from datamind.core import get_request_id, set_request_id
from datamind.core.logging.context import set_request_id as set_context_id

# 设置请求ID（两种方式等价）
set_request_id("req_abc123")
set_context_id("req_abc123")

# 获取请求ID
request_id = get_request_id()
```

### 模块集成示例

```python
from datamind.core import get_db
from datamind.core import ModelMetadata
from datamind.core import model_registry, model_loader, inference_engine
from datamind.core.experiment import ab_test_manager
from datamind.core import log_manager, get_request_id


async def deploy_and_test_model(model_path: str):
    """部署并测试模型"""
    request_id = get_request_id()

    try:
        # 1. 注册模型
        model_id = model_registry.register_model(
            model_name="test_model",
            model_version="1.0.0",
            task_type="scoring",
            model_type="xgboost",
            framework="xgboost",
            input_features=["age", "income"],
            output_schema={"score": "float"},
            created_by="admin",
            model_file=open(model_path, "rb"),
            scorecard_params={
                "base_score": 600,
                "pdo": 50,
                "direction": "lower_better"
            }
        )

        # 2. 激活模型
        model_registry.activate_model(model_id, "admin")

        # 3. 加载到内存
        model_loader.load_model(model_id, "admin")

        # 4. 创建A/B测试
        test_id = ab_test_manager.create_test(
            test_name="新模型测试",
            task_type="scoring",
            groups=[
                {"name": "control", "weight": 50, "model_id": "MDL_OLD"},
                {"name": "treatment", "weight": 50, "model_id": model_id}
            ],
            created_by="admin"
        )
        ab_test_manager.start_test(test_id, "admin")

        # 5. 执行推理
        for i in range(100):
            assignment = ab_test_manager.get_assignment(
                test_id=test_id,
                user_id=f"user{i}"
            )

            result = await inference_engine.predict_scorecard(
                model_id=assignment['model_id'],
                features={"age": 30 + i, "income": 50000 + i * 1000},
                application_id=f"APP{i}"
            )

            ab_test_manager.record_result(
                test_id=test_id,
                user_id=f"user{i}",
                metrics={"score": result['total_score']}
            )

        # 6. 分析结果
        results = ab_test_manager.analyze_results(test_id)

        log_manager.log_audit(
            action="TEST_COMPLETED",
            user_id="admin",
            details={
                "test_id": test_id,
                "winning_group": results['winning_group']
            }
        )

        return results

    except Exception as e:
        log_manager.log_audit(
            action="TEST_FAILED",
            user_id="admin",
            details={"error": str(e)},
            reason=str(e)
        )
        raise
```

## 性能指标

| 模块 | 操作 | 平均耗时 |
|-----|-----|---------|
| db | 查询单条记录 | 5ms |
| db | 批量插入100条 | 50ms |
| ml | 模型加载 (100MB) | 500ms |
| ml | 推理 (单条) | 20ms |
| ml | 批量推理 (100条) | 100ms |
| experiment | 获取分配 | 2ms |
| logging | 记录日志 | 1ms |


## 配置参考

### 数据库配置

```python
# 连接池配置
DATABASE_URL = "postgresql://user:pass@localhost:5432/datamind"
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 40
DB_POOL_TIMEOUT = 30
DB_POOL_RECYCLE = 3600
```


### 模型配置

```python
# 模型存储
MODELS_PATH = "./models_storage"
MODEL_FILE_MAX_SIZE = 1073741824  # 1GB
MODEL_INFERENCE_TIMEOUT = 30  # 秒
MODEL_CACHE_SIZE = 10
```


### 日志配置

```python
# 日志级别
LOG_LEVEL = "INFO"
LOG_FORMAT = "json"
LOG_PATH = "./logs"
LOG_RETENTION_DAYS = 90
LOG_TIMEZONE = "Asia/Shanghai"
```


## 错误处理

### 数据库错误

```python
from datamind.core.db.database import get_db
from sqlalchemy.exc import SQLAlchemyError

try:
    with get_db() as session:
        session.add(model)
        session.commit()
except SQLAlchemyError as e:
    print(f"数据库错误: {e}")
    # 自动回滚
```


### 模型错误

```python
from datamind.core.ml.common.exceptions import ModelException

try:
    result = inference_engine.predict_scorecard(model_id, features)
except ModelNotFoundException:
    print("模型不存在")
except ModelInferenceException as e:
    print(f"推理失败: {e}")
```


## 最佳实践

### 1. 使用上下文管理器

```python
# 数据库会话
with get_db() as session:
    models = session.query(ModelMetadata).all()

# 事务
with db_manager.transaction() as session:
    model.status = "active"
    session.commit()
```


### 2. 统一日志

```python
# 所有重要操作记录审计日志
log_manager.log_audit(
    action="MODEL_UPDATE",
    user_id=operator,
    details={"model_id": model_id}
)
```


### 3. 错误处理

```python
try:
    result = await inference_engine.predict_scorecard(...)
except ModelException as e:
    log_manager.log_audit(
        action="PREDICT_ERROR",
        user_id=user_id,
        details={"error": str(e)},
        reason=str(e)
    )
    raise
```


### 4. 性能监控

```python
start_time = time.time()
result = await inference_engine.predict_scorecard(...)
duration = (time.time() - start_time) * 1000

log_manager.log_performance(
    operation="predict",
    duration_ms=duration,
    model_id=model_id
)
```


## 故障排查

### 数据库连接问题

```python
# 检查数据库健康状态
health = db_manager.check_health()
if health['status'] != 'healthy':
    print("数据库异常:", health['engines'])

# 获取连接池统计
stats = db_manager.get_stats()
print(f"活跃连接: {stats['default']['checked_out_connections']}")
```


### 模型加载问题

```python
# 检查模型是否已加载
if not model_loader.is_loaded(model_id):
    print("模型未加载，尝试加载...")
    model_loader.load_model(model_id, "system")

# 查看已加载模型
loaded = model_loader.get_loaded_models()
for model in loaded:
    print(f"已加载: {model['model_name']} v{model['model_version']}")
```


### 日志问题

```python
# 检查日志配置
from datamind.config import LoggingConfig

config = LoggingConfig.load()
validation = config.validate_all()
if not validation['valid']:
    print("日志配置错误:", validation['errors'])

# 获取日志统计
stats = log_manager.get_stats()
print(f"已处理日志: {stats['logs_processed']}")
print(f"错误数: {stats['errors']}")
```
