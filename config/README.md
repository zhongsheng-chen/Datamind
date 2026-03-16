# Datamind 配置组件

提供应用配置和日志配置管理，支持多环境配置、环境变量覆盖、配置验证等功能。

## 特性

- **多环境支持** - 开发、测试、预发布、生产环境独立配置
- **环境变量覆盖** - 支持通过环境变量覆盖配置
- **配置验证** - 自动验证配置的合法性
- **类型安全** - 使用 Pydantic 模型定义配置
- **热重载** - 支持配置动态重载
- **敏感信息保护** - 自动隐藏密码、密钥等敏感信息
- **配置导出/导入** - 支持导出为 JSON/YAML 格式
- **配置监听** - 支持配置变更事件监听
- **配置缓存** - 缓存配置实例避免重复加载

## 目录结构
```text
config/
├── init.py # 模块初始化
├── settings.py # 应用配置
├── logging_config.py # 日志配置
├── storage_config.py # 存储配置
└── README.md
```

## 快速开始

### 1. 加载配置

```python
from config import settings, LoggingConfig, StorageConfig

# 获取应用配置
print(settings.APP_NAME)
print(settings.VERSION)
print(settings.ENV)

# 加载日志配置
log_config = LoggingConfig.load()
print(log_config.level)
print(log_config.format)

# 加载存储配置
storage_config = StorageConfig.load()
print(storage_config.type)
print(storage_config.models_path)
```

### 2. 环境变量文件

创建 .env 文件：

```bash
# 应用配置
DATAMIND_APP_NAME=Datamind
DATAMIND_VERSION=1.0.0
DATAMIND_ENV=development
DATAMIND_DEBUG=true

# API配置
DATAMIND_API_HOST=0.0.0.0
DATAMIND_API_PORT=8000
DATAMIND_API_PREFIX=/api/v1

# 数据库配置
DATAMIND_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datamind
DATAMIND_DB_POOL_SIZE=20
DATAMIND_DB_MAX_OVERFLOW=40

# 日志配置
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json
DATAMIND_LOG_PATH=./logs

# 存储配置
DATAMIND_STORAGE_TYPE=local
DATAMIND_LOCAL_STORAGE_PATH=./models
```

### 3. 多环境配置

```bash
# 开发环境
cp .env.dev.example .env.dev
export DATAMIND_ENV=development

# 测试环境
cp .env.test.example .env.test
export DATAMIND_ENV=test

# 生产环境
cp .env.prod.example .env.prod
export DATAMIND_ENV=production
```
## 配置详解

### 应用配置 (settings.py)

#### 基础配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| APP_NAME | DATAMIND_APP_NAME | Datamind | 应用名称 |
| VERSION | DATAMIND_VERSION | 1.0.0 | 应用版本 |
| ENV | DATAMIND_ENV | development | 运行环境 |
| DEBUG | DATAMIND_DEBUG | false | 调试模式 |

#### API配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| API_HOST | DATAMIND_API_HOST | 0.0.0.0 | API监听地址 |
| API_PORT | DATAMIND_API_PORT | 8000 | API监听端口 |
| API_PREFIX | DATAMIND_API_PREFIX | /api/v1 | API路由前缀 |

#### 数据库配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| DATABASE_URL | DATAMIND_DATABASE_URL | postgresql://... | 数据库连接 |
| READONLY_DATABASE_URL | DATAMIND_READONLY_DATABASE_URL | None | 只读数据库 |
| DB_POOL_SIZE | DATAMIND_DB_POOL_SIZE | 20 | 连接池大小 |
| DB_MAX_OVERFLOW | DATAMIND_DB_MAX_OVERFLOW | 40 | 最大溢出连接 |
| DB_ECHO | DATAMIND_DB_ECHO | false | 打印SQL |

#### Redis配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| REDIS_URL | DATAMIND_REDIS_URL | redis://localhost:6379/0 | Redis连接 |
| REDIS_PASSWORD | DATAMIND_REDIS_PASSWORD | None | Redis密码 |
| REDIS_MAX_CONNECTIONS | DATAMIND_REDIS_MAX_CONNECTIONS | 50 | 最大连接数 |

#### 模型配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| MODELS_PATH | DATAMIND_MODELS_PATH | ./models_storage | 模型存储路径 |
| MODEL_FILE_MAX_SIZE | DATAMIND_MODEL_FILE_MAX_SIZE | 1GB | 模型文件最大大小 |
| MODEL_INFERENCE_TIMEOUT | DATAMIND_MODEL_INFERENCE_TIMEOUT | 30 | 推理超时(秒) |

#### 认证配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| API_KEY_ENABLED | DATAMIND_API_KEY_ENABLED | true | 启用API密钥 |
| API_KEY_HEADER | DATAMIND_API_KEY_HEADER | X-API-Key | API密钥头 |
| JWT_SECRET_KEY | DATAMIND_JWT_SECRET_KEY | your-secret-key | JWT密钥 |
| JWT_ACCESS_TOKEN_EXPIRE_MINUTES | DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 30 | Token过期时间 |

#### 限流配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| RATE_LIMIT_ENABLED | DATAMIND_RATE_LIMIT_ENABLED | true | 启用限流 |
| RATE_LIMIT_REQUESTS | DATAMIND_RATE_LIMIT_REQUESTS | 100 | 请求数限制 |
| RATE_LIMIT_PERIOD | DATAMIND_RATE_LIMIT_PERIOD | 60 | 限制周期(秒) |

### 日志配置 (logging_config.py)

#### 基本配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| name | DATAMIND_LOG_NAME | Datamind | 日志记录器名称 |
| level | DATAMIND_LOG_LEVEL | INFO | 日志级别 |
| encoding | DATAMIND_LOG_ENCODING | utf-8 | 日志文件编码 |

#### 调试配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| formatter_debug | DATAMIND_LOG_FORMATTER_DEBUG | false | 格式化器调试 |
| manager_debug | DATAMIND_LOG_MANAGER_DEBUG | false | 管理器调试 |
| handler_debug | DATAMIND_LOG_HANDLER_DEBUG | false | 处理器调试 |
| filter_debug | DATAMIND_LOG_FILTER_DEBUG | false | 过滤器调试 |

#### 时间格式配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| timezone | DATAMIND_LOG_TIMEZONE | UTC | 日志时区 |
| timestamp_precision | DATAMIND_LOG_TIMESTAMP_PRECISION | milliseconds | 时间戳精度 |
| text_date_format | DATAMIND_TEXT_DATE_FORMAT | %Y-%m-%d %H:%M:%S | 文本日志日期格式 |
| json_datetime_format | DATAMIND_JSON_DATETIME_FORMAT | yyyy-MM-dd'T'HH:mm:ss.SSSZ | JSON时间格式 |

#### 文件配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| file | DATAMIND_LOG_FILE | logs/Datamind.log | 主日志文件 |
| error_file | DATAMIND_ERROR_LOG_FILE | logs/Datamind.error.log | 错误日志文件 |
| access_log_file | DATAMIND_ACCESS_LOG_FILE | logs/access.log | 访问日志文件 |
| audit_log_file | DATAMIND_AUDIT_LOG_FILE | logs/audit.log | 审计日志文件 |
| performance_log_file | DATAMIND_PERFORMANCE_LOG_FILE | logs/performance.log | 性能日志文件 |

#### 轮转配置

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| max_bytes | DATAMIND_LOG_MAX_BYTES | 100MB | 单个文件最大大小 |
| backup_count | DATAMIND_LOG_BACKUP_COUNT | 30 | 备份文件数量 |
| rotation_when | DATAMIND_LOG_ROTATION_WHEN | MIDNIGHT | 轮转时间单位 |
| retention_days | DATAMIND_LOG_RETENTION_DAYS | 90 | 日志保留天数 |

#### 敏感信息脱敏

| 配置项 | 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| mask_sensitive | DATAMIND_LOG_MASK_SENSITIVE | true | 启用脱敏 |
| sensitive_fields | DATAMIND_SENSITIVE_FIELDS | ["id_number", "phone", ...] | 敏感字段列表 |
| mask_char | DATAMIND_LOG_MASK_CHAR | * | 脱敏字符 |

# 使用方法

## 1. 基本使用

```python
from config import settings

# 获取配置值
print(settings.APP_NAME)
print(settings.API_HOST)
print(settings.DATABASE_URL)

# 检查环境
if settings.is_development():
    print("开发环境")
elif settings.is_production():
    print("生产环境")

# 获取分组配置
db_config = settings.get_database_config()
redis_config = settings.get_redis_config()
logging_config = settings.get_logging_config()
```

---

## 2. 日志配置加载

```python
from config import LoggingConfig
from core.logging import log_manager

# 加载日志配置
log_config = LoggingConfig.load()
log_manager.initialize(log_config)

# 获取配置摘要
digest = log_config.get_config_digest()
print(f"配置摘要: {digest}")

# 验证配置
validation = log_config.validate_all()
if not validation['valid']:
    for error in validation['errors']:
        print(f"错误: {error}")
```

---

## 3. 多环境配置

```python
# 指定环境加载配置
dev_config = LoggingConfig.load(env="development")
test_config = LoggingConfig.load(env="test")
prod_config = LoggingConfig.load(env="production")

# 比较配置差异
diff = dev_config.diff(prod_config)
print(f"差异: {diff}")
```

---

## 4. 配置热重载

```python
from config import settings, LoggingConfig

# 重载应用配置
new_settings = settings.reload()

# 重载日志配置
old_config = LoggingConfig.load()
# ... 修改配置文件 ...
new_config = old_config.reload()

if not old_config.is_equivalent_to(new_config):
    print("配置已变更")
    log_manager.reload_config(new_config)
```

---

## 5. 导出配置

```python
# 导出为字典
config_dict = settings.to_dict(exclude_sensitive=True)
print(config_dict)

# 导出为YAML文件
settings.to_yaml("config_backup.yaml", exclude_sensitive=True)

# 导出为JSON
import json
print(json.dumps(settings.to_dict(), indent=2))
```

---

# 环境变量文件

## `.env.example`

```bash
# 应用配置
DATAMIND_APP_NAME=Datamind
DATAMIND_VERSION=1.0.0
DATAMIND_ENV=development
DATAMIND_DEBUG=true

# API配置
DATAMIND_API_HOST=0.0.0.0
DATAMIND_API_PORT=8000
DATAMIND_API_PREFIX=/api/v1
DATAMIND_API_ROOT_PATH=

# 数据库配置
DATAMIND_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datamind
DATAMIND_READONLY_DATABASE_URL=
DATAMIND_DB_POOL_SIZE=20
DATAMIND_DB_MAX_OVERFLOW=40
DATAMIND_DB_POOL_TIMEOUT=30
DATAMIND_DB_POOL_RECYCLE=3600
DATAMIND_DB_ECHO=false

# Redis配置
DATAMIND_REDIS_URL=redis://localhost:6379/0
DATAMIND_REDIS_PASSWORD=
DATAMIND_REDIS_MAX_CONNECTIONS=50
DATAMIND_REDIS_SOCKET_TIMEOUT=5

# 模型存储配置
DATAMIND_MODELS_PATH=./models_storage
DATAMIND_MODEL_FILE_MAX_SIZE=1073741824
DATAMIND_XGBOOST_USE_JSON=true

# 认证配置
DATAMIND_API_KEY_ENABLED=true
DATAMIND_API_KEY_HEADER=X-API-Key
DATAMIND_JWT_SECRET_KEY=your-secret-key-change-in-production
DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# 日志配置
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json
DATAMIND_LOG_PATH=./logs
DATAMIND_LOG_MAX_BYTES=104857600
DATAMIND_LOG_BACKUP_COUNT=30
DATAMIND_LOG_RETENTION_DAYS=90
DATAMIND_LOG_TIMEZONE=UTC
DATAMIND_LOG_ENABLE_ACCESS=true
DATAMIND_LOG_ENABLE_AUDIT=true
DATAMIND_LOG_ENABLE_PERFORMANCE=true
DATAMIND_LOG_MASK_SENSITIVE=true
DATAMIND_LOG_SAMPLING_RATE=1.0

# A/B测试配置
DATAMIND_AB_TEST_ENABLED=true
DATAMIND_AB_TEST_REDIS_KEY_PREFIX=ab_test:
DATAMIND_AB_TEST_ASSIGNMENT_EXPIRY=86400

# 监控配置
DATAMIND_METRICS_ENABLED=true
DATAMIND_PROMETHEUS_PORT=9090
DATAMIND_METRICS_PATH=/metrics

# 安全配置
DATAMIND_CORS_ORIGINS=["*"]
DATAMIND_TRUSTED_PROXIES=[]
DATAMIND_RATE_LIMIT_ENABLED=true
DATAMIND_RATE_LIMIT_REQUESTS=100
DATAMIND_RATE_LIMIT_PERIOD=60

# 模型推理配置
DATAMIND_MODEL_INFERENCE_TIMEOUT=30
DATAMIND_MODEL_CACHE_SIZE=10
DATAMIND_MODEL_CACHE_TTL=3600

# 特征存储配置
DATAMIND_FEATURE_STORE_ENABLED=true
DATAMIND_FEATURE_CACHE_SIZE=1000
DATAMIND_FEATURE_CACHE_TTL=300

# 批处理配置
DATAMIND_BATCH_SIZE=100
DATAMIND_MAX_WORKERS=10

# 告警配置
DATAMIND_ALERT_ENABLED=false
DATAMIND_ALERT_WEBHOOK_URL=
DATAMIND_ALERT_ON_ERROR=true
DATAMIND_ALERT_ON_MODEL_DEGRADATION=true
```

---

## `.env.dev` - 开发环境

```bash
DATAMIND_ENV=development
DATAMIND_DEBUG=true
DATAMIND_LOG_LEVEL=DEBUG
DATAMIND_LOG_FORMAT=text
DATAMIND_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datamind_dev
```

---

## `.env.test` - 测试环境

```bash
DATAMIND_ENV=test
DATAMIND_DEBUG=false
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json
DATAMIND_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datamind_test
```

---

## `.env.prod` - 生产环境

```bash
DATAMIND_ENV=production
DATAMIND_DEBUG=false
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json
DATAMIND_DATABASE_URL=postgresql://user:password@prod-db:5432/datamind
DATAMIND_JWT_SECRET_KEY=complex-secret-key
```

---

# 配置验证

## 验证所有配置

```python
from config import LoggingConfig

config = LoggingConfig.load()
validation = config.validate_all()

if validation['valid']:
    print("✅ 配置验证通过")
else:
    print("❌ 配置验证失败:")
    for error in validation['errors']:
        print(f"  - {error}")

if validation['warnings']:
    print("\n⚠️ 警告:")
    for warning in validation['warnings']:
        print(f"  - {warning}")
```

---

## 自定义验证

```python
from config import settings
from pydantic import validator

class CustomSettings(settings.__class__):
    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        if 'localhost' in v and settings.ENV == 'production':
            raise ValueError('生产环境不能使用本地数据库')
        return v
```

---

# 配置优先级

配置加载顺序（从低到高）：

1. 默认值 - 代码中的默认值  
2. `.env` 文件 - 项目根目录  
3. `.env.{env}` 文件 - 环境特定配置  
4. `.env.local` 文件 - 本地覆盖  
5. 环境变量 - 系统环境变量  
6. `env_file` 参数 - 手动指定的配置文件  

```python
# 最高优先级：手动指定配置文件
config = LoggingConfig.load(env_file="/path/to/custom.env")
```


# 最佳实践

## 1. 不要提交敏感信息

```bash
# .gitignore
.env
.env.local
*.env
!*.env.example
```

## 2. 使用配置分组

```python
# 数据库配置
db_config = {
    'pool_size': settings.DB_POOL_SIZE,
    'max_overflow': settings.DB_MAX_OVERFLOW,
    'pool_timeout': settings.DB_POOL_TIMEOUT
}

# 日志配置
log_config = {
    'level': settings.LOG_LEVEL,
    'format': settings.LOG_FORMAT,
    'path': settings.LOG_PATH
}
```

## 3. 环境判断

```python
if settings.is_development():
    pass
elif settings.is_testing():
    pass
elif settings.is_staging():
    pass
elif settings.is_production():
    pass
```


# 故障排查

## 1. 配置加载失败

```python
try:
    config = LoggingConfig.load()
except Exception as e:
    print(f"配置加载失败: {e}")
```

## 2. 配置验证失败

```python
config = LoggingConfig.load()
validation = config.validate_all()

if not validation['valid']:
    print("错误详情:")
    for error in validation['errors']:
        print(f"  - {error}")
```

## 3. 查看当前使用的配置文件

```python
config = LoggingConfig.load()
print(f"环境: {config._env}")
print(f"配置文件: {config.get_env_files()}")
print(f"配置摘要: {config.get_config_digest()}")
```

# 性能考虑

- 配置加载是轻量级操作，通常 `< 10ms`
- 建议在应用启动时加载一次
- 热重载会重新初始化日志系统，可能影响性能
- 配置验证建议在启动时执行，不要在每个请求中执行














