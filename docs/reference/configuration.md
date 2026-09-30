# 配置参考

按功能查阅环境变量、用途、默认值与校验规则。首次配置见[配置与初始化](../getting-started/configuration.md)。

配置优先级从高到低为：显式构造参数、环境变量、工作目录 `.env`、默认值。CLI、Runtime、Console 与任务 Worker 使用相同的部署配置，修改后重启相关进程。嵌套配置使用独立前缀，例如 `DATAMIND_STORAGE_MINIO_`。

列表使用 JSON，例如 `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS=["127.0.0.0/8"]`。相对路径以进程工作目录为起点。数据库 URL 必须填写，选择 MinIO 时填写访问密钥，启用认证时填写签名密钥。

## 审计

前缀：`DATAMIND_AUDIT_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/audit.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_AUDIT_ENABLED` | `boolean` | `true` | 是否启用审计组件。 |
| `DATAMIND_AUDIT_FAILURE_MODE` | `open/closed` | `"open"` | 审计失败处理模式。 |
| `DATAMIND_AUDIT_MAX_RETRIES` | `integer` | `2` | 瞬时数据库错误最大尝试次数。 |
| `DATAMIND_AUDIT_RETRY_BASE_DELAY` | `number` | `0.05` | 重试基础延迟（秒）。 |

校验规则：

- max_retries 必须大于等于 1
- retry_base_delay 必须大于 0

## 本地认证

前缀：`DATAMIND_AUTH_LOCAL_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/auth.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_AUTH_LOCAL_MAX_FAILED_LOGIN_ATTEMPTS` | `integer` | `5` | 最大连续登录失败次数。 |
| `DATAMIND_AUTH_LOCAL_LOCK_MINUTES` | `integer` | `30` | 登录失败锁定时间。单位：分钟。 |
| `DATAMIND_AUTH_LOCAL_UPGRADE_PASSWORD_HASH` | `boolean` | `true` | 是否自动升级密码哈希。 |
| `DATAMIND_AUTH_LOCAL_BREAK_GLASS_ONLY` | `boolean` | `false` | 是否仅允许应急账户登录。 |
| `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS` | `array[string]` | `[]` | 本地认证允许访问的网段。 |
| `DATAMIND_AUTH_LOCAL_BREAK_GLASS_ACCESS_TOKEN_EXPIRES_MINUTES` | `integer` | `15` | 应急访问令牌有效时间。单位：分钟。 |

校验规则：

- max_failed_login_attempts 必须大于 0
- lock_minutes 必须大于 0
- break_glass_access_token_expires_minutes 必须大于 0
- allowed_networks 包含无效网段

## 认证

前缀：`DATAMIND_AUTH_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/auth.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_AUTH_ENABLED` | `boolean` | `false` | 是否启用认证功能。 |
| `DATAMIND_AUTH_SECRET_KEY` | `string (password)` | `""` | JWT 签名密钥。 |
| `DATAMIND_AUTH_ALGORITHM` | `string` | `"HS256"` | JWT 签名算法。 |
| `DATAMIND_AUTH_ACCESS_TOKEN_EXPIRES_MINUTES` | `integer` | `30` | 访问令牌有效时间。单位：分钟。 |
| `DATAMIND_AUTH_REFRESH_TOKEN_EXPIRES_DAYS` | `integer` | `7` | 刷新令牌有效时间。单位：天。 |

校验规则：

- algorithm 不能为空
- access_token_expires_minutes 必须大于 0
- refresh_token_expires_days 必须大于 0
- 启用认证功能时，secret_key 不能为空

## 分类预测

前缀：`DATAMIND_CLASSIFICATION_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/classification.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_CLASSIFICATION_THRESHOLD` | `number` | `0.5` | 分类阈值，概率大于该值时预测为正类。 |

校验规则：

- threshold 必须在 0 到 1 之间

## 管理控制台

前缀：`DATAMIND_CONSOLE_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/console.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_CONSOLE_HOST` | `string` | `"127.0.0.1"` | 管理控制台监听地址。 |
| `DATAMIND_CONSOLE_PORT` | `integer` | `8701` | 管理控制台监听端口。 |
| `DATAMIND_CONSOLE_STARTUP_TIMEOUT` | `integer` | `120` | 控制台启动超时时间（秒），范围 1 到 600。 |

校验规则：

- host 不能为空
- port 必须在 1 到 65535 之间
- startup_timeout 必须在 1 到 600 之间

## 数据库

前缀：`DATAMIND_DATABASE_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/database.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_DATABASE_URL` | `string` | `""` | 数据库连接 URL，必填。 |
| `DATAMIND_DATABASE_POOL_SIZE` | `integer` | `10` | 连接池大小。 |
| `DATAMIND_DATABASE_MAX_OVERFLOW` | `integer` | `20` | 最大溢出连接数。 |
| `DATAMIND_DATABASE_POOL_TIMEOUT` | `integer` | `30` | 获取连接超时时间（秒）。 |
| `DATAMIND_DATABASE_POOL_RECYCLE` | `integer` | `3600` | 连接回收时间（秒）。 |
| `DATAMIND_DATABASE_ECHO` | `boolean` | `false` | 是否打印 SQL 语句。 |

校验规则：

- url 不能为空
- pool_size 必须大于等于 0
- max_overflow 必须大于等于 0
- pool_timeout 必须大于等于 0
- pool_recycle 必须大于等于 0

## 初始化

前缀：`DATAMIND_INIT_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/initialization.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_INIT_ADMIN_USERNAME` | `string` | `"admin"` | 管理员用户名。 |
| `DATAMIND_INIT_ADMIN_PASSWORD` | `string (password)` | `"admin"` | 管理员密码。 |

校验规则：

- admin_username 不能为空
- admin_username 长度不能超过 64

## 日志

前缀：`DATAMIND_LOG_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/logging.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_LOG_LEVEL` | `DEBUG/INFO/WARNING/ERROR/CRITICAL` | `"INFO"` | 日志级别。 |
| `DATAMIND_LOG_FORMAT` | `text/json` | `"json"` | 日志格式。 |
| `DATAMIND_LOG_ENCODING` | `string` | `"utf-8"` | 日志编码。 |
| `DATAMIND_LOG_DIR` | `string (path)` | `"logs"` | 日志文件目录。 |
| `DATAMIND_LOG_FILENAME` | `string` | `"datamind.log"` | 日志文件名。 |
| `DATAMIND_LOG_DATE_FORMAT` | `string \| null` | `null` | 日期格式。 |
| `DATAMIND_LOG_TIMEZONE` | `string` | `"Asia/Shanghai"` | IANA 时区名称。 |
| `DATAMIND_LOG_ROTATION` | `time/size` | `"time"` | 日志轮转策略。 |
| `DATAMIND_LOG_ROTATION_WHEN` | `MIDNIGHT/H/M/S/W0/W1/W2/W3/W4/W5/W6` | `"MIDNIGHT"` | 时间轮转周期。 |
| `DATAMIND_LOG_ROTATION_INTERVAL` | `integer` | `1` | 日志轮转间隔。 |
| `DATAMIND_LOG_MAX_BYTES` | `integer` | `104857600` | 大小轮转阈值。单位：字节。 |
| `DATAMIND_LOG_BACKUP_COUNT` | `integer` | `30` | 轮转备份文件数量。 |
| `DATAMIND_LOG_RETENTION_DAYS` | `integer` | `90` | 日志保留天数。 |
| `DATAMIND_LOG_ENABLE_CONSOLE` | `boolean` | `true` | 是否输出到控制台。 |
| `DATAMIND_LOG_CONSOLE_LEVEL` | `DEBUG/INFO/WARNING/ERROR/CRITICAL` | `"WARNING"` | 控制台日志级别。 |
| `DATAMIND_LOG_ENABLE_FILE` | `boolean` | `true` | 是否输出到文件。 |
| `DATAMIND_LOG_ENABLE_ASYNC` | `boolean` | `false` | 是否启用异步日志。 |
| `DATAMIND_LOG_SAMPLE_RATE` | `number` | `1.0` | 普通日志采样率。 |
| `DATAMIND_LOG_MASK_SENSITIVE` | `boolean` | `true` | 是否脱敏敏感信息。 |
| `DATAMIND_LOG_MASK_CHAR` | `string` | `"*"` | 脱敏字符。 |
| `DATAMIND_LOG_UNMASKED_PREFIX` | `integer` | `2` | 脱敏时前面保留位数。 |
| `DATAMIND_LOG_UNMASKED_SUFFIX` | `integer` | `2` | 脱敏时后面保留位数。 |

校验规则：

- encoding 不能为空
- filename 不能为空
- date_format 不能是空字符串
- timezone 不能为空
- rotation_interval 必须大于 0
- max_bytes 必须大于 0
- backup_count 必须大于 0
- retention_days 必须大于 0
- sample_rate 必须大于 0 且小于等于 1
- mask_char 不能为空
- mask_char 只能包含一个字符
- unmasked_prefix 必须大于等于 0
- unmasked_suffix 必须大于等于 0
- encoding 不是有效的字符编码
- timezone 不是有效的 IANA 时区

## 任务队列

前缀：`DATAMIND_TASK_QUEUE_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/queue.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_TASK_QUEUE_BROKER_URL` | `string` | `"redis://localhost:6379/0"` | Celery Broker 连接 URL。 |
| `DATAMIND_TASK_QUEUE_BATCH_QUEUE` | `string` | `"prediction.batch"` | 批量预测任务队列名称。 |
| `DATAMIND_TASK_QUEUE_SHADOW_QUEUE` | `string` | `"prediction.shadow"` | 影子预测任务队列名称。 |
| `DATAMIND_TASK_QUEUE_MAX_RETRIES` | `integer` | `3` | 任务最大重试次数。 |
| `DATAMIND_TASK_QUEUE_BATCH_CHUNK_SIZE` | `integer` | `20` | 单个批量分片包含的请求数。 |
| `DATAMIND_TASK_QUEUE_RETRY_BACKOFF_SECONDS` | `integer` | `5` | 任务重试退避基数（秒）。 |
| `DATAMIND_TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS` | `integer` | `3600` | Broker 消息可见性超时时间（秒）。 |

校验规则：

- broker_url 不能为空
- batch_queue 不能为空
- shadow_queue 不能为空
- 批量预测和影子预测必须使用不同队列
- max_retries 不能小于 0
- batch_chunk_size 必须大于等于 1
- retry_backoff_seconds 必须大于等于 1
- visibility_timeout_seconds 必须大于等于 1

## 运行协调与影子预测

前缀：`DATAMIND_RUNTIME_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/runtime.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_RUNTIME_RECONCILE_INTERVAL` | `number` | `2.0` | 运行状态协调间隔（秒）。 |
| `DATAMIND_RUNTIME_HEARTBEAT_INTERVAL` | `number` | `30.0` | Worker 运行心跳间隔（秒）。 |
| `DATAMIND_RUNTIME_SHADOW_ENABLED` | `boolean` | `true` | 是否执行影子预测。 |
| `DATAMIND_RUNTIME_SHADOW_TIMEOUT` | `number` | `5.0` | 单次影子预测超时时间（秒）。 |

校验规则：

- reconcile_interval 必须大于 0
- heartbeat_interval 必须大于 0
- shadow_timeout 必须大于 0

## 评分预测

前缀：`DATAMIND_SCORING_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/scoring.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_SCORING_THRESHOLD` | `number` | `600.0` | 评分决策阈值，评分大于等于该值时通过。 |

校验规则：

- threshold 必须是有限数值

## 预测服务

前缀：`DATAMIND_SERVICE_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/service.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_SERVICE_NAME` | `string` | `"datamind"` | 服务名称。 |
| `DATAMIND_SERVICE_VERSION` | `string` | `"1.0.0"` | 服务版本。 |
| `DATAMIND_SERVICE_ENVIRONMENT` | `development/testing/staging/production` | `必需` | 运行环境，必填。 |
| `DATAMIND_SERVICE_HOST` | `string` | `"0.0.0.0"` | 服务监听地址。 |
| `DATAMIND_SERVICE_PORT` | `integer` | `8700` | 服务监听端口。 |
| `DATAMIND_SERVICE_WORKERS` | `integer` | `4` | 工作进程数。 |
| `DATAMIND_SERVICE_TIMEOUT` | `integer` | `30` | 认证后单条或整批预测请求的超时时间（秒），不包含启动等待。 |
| `DATAMIND_SERVICE_ENABLE_DOCS` | `boolean` | `true` | 是否启用 API 文档。 |
| `DATAMIND_SERVICE_ENABLE_HEALTH_CHECK` | `boolean` | `true` | 是否启用健康检查。 |

校验规则：

- name 不能为空
- version 不能为空
- host 不能为空
- workers 必须大于等于 1
- port 必须在 1 到 65535 之间
- timeout 必须大于等于 1

## 本地存储

前缀：`DATAMIND_STORAGE_LOCAL_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/storage.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_STORAGE_LOCAL_BASE_DIR` | `string (path)` | `"data"` | 本地基础目录。 |

## MinIO 存储

前缀：`DATAMIND_STORAGE_MINIO_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/storage.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_STORAGE_MINIO_ENDPOINT` | `string` | `"localhost:9000"` | MinIO 服务地址。 |
| `DATAMIND_STORAGE_MINIO_BUCKET` | `string` | `"datamind"` | 存储桶名称。 |
| `DATAMIND_STORAGE_MINIO_ACCESS_KEY` | `string` | `""` | 访问密钥。 |
| `DATAMIND_STORAGE_MINIO_SECRET_KEY` | `string` | `""` | 秘密密钥。 |
| `DATAMIND_STORAGE_MINIO_SECURE` | `boolean` | `false` | 是否启用 TLS/SSL。 |
| `DATAMIND_STORAGE_MINIO_REGION` | `string \| null` | `null` | S3 兼容区域，可选。 |
| `DATAMIND_STORAGE_MINIO_BASE_PREFIX` | `string` | `"datamind"` | 对象存储基础前缀。 |

## 制品存储

前缀：`DATAMIND_STORAGE_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/storage.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_STORAGE_TYPE` | `local/minio` | `"local"` | 存储类型，local 或 minio。 |
| `DATAMIND_STORAGE_MAX_FILE_SIZE` | `integer` | `209715200` | 单个模型文件最大字节数。 |
| `DATAMIND_STORAGE_MODEL_DIR` | `string` | `"models"` | 模型存放的相对子目录。 |

校验规则：

- max_file_size 必须大于 0
- model_dir 不能为空
- model_dir 必须是相对目录
- model_dir 不能包含上级目录引用
- 使用 minio 存储时，endpoint 不能为空
- 使用 minio 存储时，bucket 不能为空
- 使用 minio 存储时，access_key 不能为空
- 使用 minio 存储时，secret_key 不能为空

## 任务 Worker

前缀：`DATAMIND_TASK_WORKER_`。[源码](https://github.com/zhongsheng-chen/Datamind/blob/main/datamind/config/worker.py)

| 环境变量 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `DATAMIND_TASK_WORKER_NAME` | `string` | `"datamind-task-worker"` | Worker 名称。 |
| `DATAMIND_TASK_WORKER_ROLE` | `all/batch/shadow` | `"all"` | Worker 处理的任务类型。 |
| `DATAMIND_TASK_WORKER_CONCURRENCY` | `integer` | `1` | Worker 并发数。 |
| `DATAMIND_TASK_WORKER_LOG_LEVEL` | `DEBUG/INFO/WARNING/ERROR/CRITICAL` | `"INFO"` | Worker 日志级别。 |

校验规则：

- name 不能为空
- name 不能包含 @
- concurrency 必须大于等于 1

## 运行时依赖

数据库连接必须指向 PostgreSQL（异步驱动 URL 使用 `postgresql+asyncpg://`）。选择 local 存储时所有加载进程必须能访问同一制品目录；选择 MinIO 时 endpoint 不带协议，TLS 由 `secure` 控制。

Task Queue 的 batch/shadow 队列必须不同。Runtime 和任务 Worker 使用相同 Broker URL 和队列名称，`visibility_timeout_seconds` 应覆盖任务运行时长。批量切片大小与 Celery 进程并发是两个不同设置。

日志的时区影响 CLI 时间显示和日志格式；数据库持久化时刻按时区感知时间处理。审计 `failure_mode=open` 允许业务在审计失败时继续，`closed` 会阻止受审计操作；此设置不同于关闭审计。

共 85 个环境变量。初始化步骤见[配置与初始化](../getting-started/configuration.md)，部署约束见[生产部署](../deployment/production.md)。
