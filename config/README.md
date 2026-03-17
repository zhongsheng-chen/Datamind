# Datamind 配置组件

提供应用配置、日志配置和存储配置管理，支持多环境配置、环境变量覆盖、配置验证等功能。

## 特性

- **多环境支持** - 开发、测试、预发布、生产环境独立配置
- **环境变量覆盖** - 支持通过环境变量覆盖配置
- **配置验证** - 自动验证配置的合法性
- **类型安全** - 使用 Pydantic 模型定义配置
- **模块化设计** - 按功能域划分配置，清晰易维护
- **敏感信息保护** - 自动隐藏密码、密钥等敏感信息

## 目录结构

```text
config/
├── __init__.py      # 模块初始化，导出公共接口
├── settings.py      # 应用主配置
├── logging_config.py # 日志配置
├── storage_config.py # 存储配置
└── README.md
```

## 配置结构

```text
Settings (根配置)
├── app          - 应用基础配置
├── model        - 模型存储配置
├── inference    - 模型推理配置
├── feature_store - 特征存储配置
├── ab_test      - A/B测试配置
├── batch        - 批处理配置
├── api          - API服务配置
├── database     - 数据库配置
├── redis        - Redis配置
├── auth         - 认证授权配置
├── monitoring   - 监控配置
├── alert        - 告警配置
├── security     - 安全配置
├── logging      - 日志配置
└── storage      - 存储配置
```

## 快速开始

### 1. 获取配置

```python
from config import get_settings

# 获取配置实例
settings = get_settings()

# 访问配置
print(settings.app.app_name)
print(settings.app.env)
print(settings.api.host)
print(settings.api.port)

# 访问日志配置
print(settings.logging.level)
print(settings.logging.format)

# 访问存储配置
print(settings.storage.storage_type)
```

### 2. 环境变量文件

创建 `.env` 文件：

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

# Redis配置
DATAMIND_REDIS_URL=redis://localhost:6379/0
DATAMIND_REDIS_MAX_CONNECTIONS=50

# 日志配置
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json

# 存储配置
DATAMIND_STORAGE_TYPE=local
```

### 3. 多环境配置

```bash
# 开发环境
export DATAMIND_ENV=development

# 测试环境
export DATAMIND_ENV=testing

# 预发布环境
export DATAMIND_ENV=staging

# 生产环境
export DATAMIND_ENV=production
```

## 配置详解

### 应用配置 (app)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| app_name | DATAMIND_APP_NAME | Datamind | 应用名称 |
| version | DATAMIND_VERSION | 1.0.0 | 应用版本 |
| env | DATAMIND_ENV | development | 运行环境 |
| debug | DATAMIND_DEBUG | false | 调试模式 |

### API配置 (api)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| host | DATAMIND_API_HOST | 0.0.0.0 | API监听地址 |
| port | DATAMIND_API_PORT | 8000 | API监听端口 |
| prefix | DATAMIND_API_PREFIX | /api/v1 | API路由前缀 |
| root_path | DATAMIND_API_ROOT_PATH | "" | API根路径 |

### 数据库配置 (database)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| url | DATAMIND_DATABASE_URL | 必填 | PostgreSQL数据库连接URL |
| readonly_url | DATAMIND_READONLY_DATABASE_URL | None | 只读数据库连接URL |
| pool_size | DATAMIND_DB_POOL_SIZE | 20 | 数据库连接池大小 |
| max_overflow | DATAMIND_DB_MAX_OVERFLOW | 40 | 连接池最大溢出数 |
| pool_timeout | DATAMIND_DB_POOL_TIMEOUT | 30 | 连接池超时时间（秒） |
| pool_recycle | DATAMIND_DB_POOL_RECYCLE | 3600 | 连接回收时间（秒） |
| echo | DATAMIND_DB_ECHO | false | 是否打印SQL语句 |

### Redis配置 (redis)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| url | DATAMIND_REDIS_URL | redis://localhost:6379/0 | Redis连接URL |
| password | DATAMIND_REDIS_PASSWORD | None | Redis密码 |
| max_connections | DATAMIND_REDIS_MAX_CONNECTIONS | 50 | Redis最大连接数 |
| socket_timeout | DATAMIND_REDIS_SOCKET_TIMEOUT | 5 | Redis套接字超时（秒） |

### 认证配置 (auth)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| api_key_enabled | DATAMIND_API_KEY_ENABLED | true | 是否启用API密钥认证 |
| api_key_header | DATAMIND_API_KEY_HEADER | X-API-Key | API密钥头字段 |
| jwt_secret_key | DATAMIND_JWT_SECRET_KEY | 必填 | JWT密钥 |
| jwt_algorithm | DATAMIND_JWT_ALGORITHM | HS256 | JWT算法 |
| jwt_expire_minutes | DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES | 30 | JWT过期时间（分钟） |

### 日志配置 (logging)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| name | DATAMIND_LOG_NAME | datamind | 日志记录器名称 |
| level | DATAMIND_LOG_LEVEL | INFO | 日志级别 |
| format | DATAMIND_LOG_FORMAT | json | 日志格式 |
| file | DATAMIND_LOG_FILE | datamind.log | 主日志文件名 |
| error_file | DATAMIND_ERROR_LOG_FILE | datamind.error.log | 错误日志文件名 |
| max_bytes | DATAMIND_LOG_MAX_BYTES | 104857600 | 单个日志文件最大字节数 |
| backup_count | DATAMIND_LOG_BACKUP_COUNT | 30 | 备份文件数量 |
| retention_days | DATAMIND_LOG_RETENTION_DAYS | 90 | 日志保留天数 |

### 存储配置 (storage)

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| storage_type | DATAMIND_STORAGE_TYPE | local | 存储类型: local/minio/s3 |
| default_ttl | DATAMIND_STORAGE_DEFAULT_TTL | 86400 | 对象默认过期时间（秒） |
| enable_cache | DATAMIND_STORAGE_ENABLE_CACHE | true | 是否启用存储缓存 |
| cache_size | DATAMIND_STORAGE_CACHE_SIZE | 100 | 缓存大小 |
| max_file_size | DATAMIND_STORAGE_MAX_FILE_SIZE | 1GB | 最大文件大小 |

## 环境变量文件示例

### `.env.example`

```text
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

# Redis配置
DATAMIND_REDIS_URL=redis://localhost:6379/0
DATAMIND_REDIS_MAX_CONNECTIONS=50

# 认证配置
DATAMIND_JWT_SECRET_KEY=your-secret-key-change-in-production

# 日志配置
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json

# 存储配置
DATAMIND_STORAGE_TYPE=local
DATAMIND_LOCAL_STORAGE_PATH=./models
```

### `.env.dev` - 开发环境

```text
DATAMIND_ENV=development
DATAMIND_DEBUG=true
DATAMIND_LOG_LEVEL=DEBUG
DATAMIND_LOG_FORMAT=text
DATAMIND_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/datamind_dev
```

### `.env.prod` - 生产环境

```text
DATAMIND_ENV=production
DATAMIND_DEBUG=false
DATAMIND_LOG_LEVEL=INFO
DATAMIND_LOG_FORMAT=json
DATAMIND_DATABASE_URL=postgresql://user:password@prod-db:5432/datamind
DATAMIND_JWT_SECRET_KEY=complex-secret-key
```

## 最佳实践

### 1. 不要在代码中硬编码配置

```python
# 正确
from config import get_settings
settings = get_settings()
db_url = settings.database.url

# 错误
db_url = "postgresql://localhost:5432/db"
```

### 2. 使用环境判断

```python
settings = get_settings()

if settings.app.env == "development":
    # 开发环境特定逻辑
    pass
elif settings.app.env == "production":
    # 生产环境特定逻辑
    pass
```

### 3. 敏感信息不要提交到代码库

```text
# .gitignore
.env
.env.*
!.env.example
```

### 4. 配置验证

```python
from config import get_settings

try:
    settings = get_settings()
    # 配置会自动验证，无效配置会抛出异常
    print("配置验证通过")
except ValueError as e:
    print(f"配置验证失败: {e}")
```

## 运行测试

```python
# 运行所有测试（使用模块路径）
python -m tests.test_config

# 运行所有测试（使用文件路径）
python tests/test_config.py

# 运行特定测试类
python -m unittest tests.test_config.TestDatabaseConfig

# 运行特定测试方法
python -m unittest tests.test_config.TestDatabaseConfig.test_default_values

# 带详细输出的运行
python -m unittest tests.test_config -v

# 或者使用文件路径带详细输出
python -m unittest tests/test_config.py -v
```

## 常见问题

### Q: 如何在不同环境间切换？
A: 设置 `DATAMIND_ENV` 环境变量即可，如 `export DATAMIND_ENV=production`

### Q: 配置加载优先级是怎样的？
A: 环境变量 > .env文件 > 默认值

### Q: 如何查看当前生效的配置？
A: 
```python
from config import get_settings
settings = get_settings()
print(settings.model_dump())
```

### Q: 支持哪些配置文件格式？
A: 支持 `.env` 格式的环境变量文件

## API参考

### 函数

#### `get_settings() -> Settings`
获取配置实例（带缓存）

### 配置类

#### `Settings`
根配置类，包含所有子配置

#### `LoggingConfig`
日志配置类

#### `StorageConfig`
存储配置类

### 枚举

#### `StorageType`
- `LOCAL`: 本地存储
- `MINIO`: MinIO存储
- `S3`: S3存储

#### `LogLevel`
- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

#### `LogFormat`
- `TEXT`: 文本格式
- `JSON`: JSON格式
- `BOTH`: 同时输出两种格式