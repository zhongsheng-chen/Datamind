# 本地部署

本节介绍如何从源码完成本地部署，包括服务配置、系统初始化，以及预测服务、管理控制台和任务 Worker 的启动与检查。

## 前置条件

部署前，请完成以下准备：

- 安装 [Python 3.12](https://www.python.org/downloads/) 和 [Node.js 24](https://nodejs.org/en/download)。
- 克隆 [Datamind 仓库](https://github.com/zhongsheng-chen/Datamind)，并[创建、激活 Python 虚拟环境](https://docs.python.org/zh-cn/3.12/library/venv.html)。
- 安装并启动 PostgreSQL、Redis 和 MinIO，具体步骤请参阅[基础设施](docker.md#基础设施)。

## 配置

在项目根目录创建 `.env` 文件：

```dotenv
# 运行环境
DATAMIND_ENVIRONMENT=development

# 数据库
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@127.0.0.1:5432/dbname

# 文件存储
DATAMIND_STORAGE_TYPE=minio
DATAMIND_STORAGE_MINIO_ENDPOINT=127.0.0.1:9000
DATAMIND_STORAGE_MINIO_BUCKET=minio-bucket-name
DATAMIND_STORAGE_MINIO_ACCESS_KEY=minio-access-key
DATAMIND_STORAGE_MINIO_SECRET_KEY=minio-secret-key
DATAMIND_STORAGE_MINIO_SECURE=false

# 任务队列
DATAMIND_TASK_QUEUE_BROKER_URL=redis://default:password@127.0.0.1:6379/0
DATAMIND_TASK_WORKER_CONCURRENCY=4

# 身份认证
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=auth-secret-key

# 管理员账户
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=admin

# 服务地址
DATAMIND_SERVICE_HOST=127.0.0.1
DATAMIND_SERVICE_PORT=8700
DATAMIND_CONSOLE_HOST=127.0.0.1
DATAMIND_CONSOLE_PORT=8701
```

将数据库、Redis 和 MinIO 的连接信息替换为实际值，并设置认证签名密钥和管理员密码。签名密钥可通过以下命令生成：

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

更多配置说明，请参阅[环境变量](../reference/environment-variables.md)。

## 安装依赖

激活虚拟环境后，以可编辑模式安装，并安装所需的模型框架依赖：

```bash
python -m pip install -e ".[sklearn,catboost,xgboost]"
```

安装前端依赖并构建管理控制台资源：

```bash
npm ci
npm run build:console
```

## 数据库迁移与系统初始化

执行数据库迁移：

```bash
datamind db upgrade
```

首次部署还需初始化系统，创建管理员账户和内置角色：

```bash
datamind init
```

使用初始化时创建的管理员账户登录：

```bash
datamind login --username admin
```

按提示输入初始化时设置的密码。

## 启动服务

启动预测服务：

```bash
datamind service run
```

在另一个终端启动管理控制台：

```bash
datamind console run
```

使用批量预测或影子预测时，启动任务 Worker：

```bash
datamind worker run
```

服务启动后，打开[管理控制台](http://127.0.0.1:8701)，使用初始化时创建的管理员账户登录。具体操作请参阅[管理控制台](../guides/console.md)。

## 健康检查

通过 `DATAMIND_HEALTHCHECK_URL` 指定就绪检查地址。退出码 `0` 表示检查通过，`1` 表示检查失败。

**Linux / macOS**

```bash
# 预测服务
DATAMIND_HEALTHCHECK_URL=http://127.0.0.1:8700/ready datamind service healthcheck

# 管理控制台
DATAMIND_HEALTHCHECK_URL=http://127.0.0.1:8701/ready datamind console healthcheck
```

**Windows PowerShell**

```powershell
# 预测服务
$env:DATAMIND_HEALTHCHECK_URL = "http://127.0.0.1:8700/ready"
datamind service healthcheck

# 管理控制台
$env:DATAMIND_HEALTHCHECK_URL = "http://127.0.0.1:8701/ready"
datamind console healthcheck
```

探针接口说明请参阅[健康与就绪探针](../reference/runtime-api.md#健康与就绪探针)，Worker 健康检查请参阅[任务 Worker](worker.md#健康检查)。

## 检查运行状态

启用部署后，查看运行实例：

```bash
datamind runtime list
```

查看指定部署的运行状态：

```bash
datamind runtime show <deployment_id>
```

确认目标实例状态为 `running`，并发送预测请求验证模型可用。服务健康检查不能代替模型运行状态和预测结果验证。

## 日志中的操作结果

HTTP 完成日志的 `success` 来自当前接口操作的响应结果，不由 HTTP 状态码推断：

- 实时预测：表示预测执行是否成功，与评分高低无关。
- 批量提交：`success=True` 表示提交成功，HTTP 202 不代表批次已完成。
- 状态查询：`success=True` 表示查询成功，即使查到的批次已经失败。
- 尚无操作结果或不适用时省略 `success`，例如健康探针的访问日志。

批量任务自身日志使用 `status`，并保留 `total_count`、`succeeded_count` 和 `failed_count`；
HTTP 日志附带批次状态时使用 `batch_status`，HTTP 状态码始终使用 `status_code`。
通过 `batch_id` 关联提交、查询和 Worker 执行，通过 `request_id` 定位一次 HTTP 调用。

以下是省略时间戳和部分关联字段的文本日志示例：

```text
INFO     | 运行时服务已就绪 | workers=4
INFO     | 模型加载成功 | worker_id=w1, deployment_id=dep1, version_id=ver1, generation=2, duration_ms=45.6
DEBUG    | 主路由解析完成 | deployment_id=dep1, version_id=ver1, route_source=experiment, strategy=hash
INFO     | 批量预测任务开始执行 | batch_id=bat1, status=running, total_count=24
INFO     | 批量预测任务执行完成 | batch_id=bat1, status=partially_succeeded, total_count=24, succeeded_count=23, failed_count=1
INFO     | HTTP 请求完成 | path=/predict/batch/status, status_code=200, success=True, batch_id=bat1, batch_status=partially_succeeded
```

## 第三方诊断日志

运行时、管理控制台和批量/影子 Worker 在各自进程初始化日志组件。
CVXPY 的原始 logger 为 `__cvxpy__`，其默认 stderr handler 不向 root 传播；
应用直接接入该 logger，兼容 CVXPY 延迟导入时添加的默认 handler，避免同一记录重复输出。
Python warnings 使用标准 `logging.captureWarnings(True)` 接入 `py.warnings`。
既有 warnings 过滤规则、warnings-as-errors 和异常传播保持不变，不额外采样或跨 Worker 去重。

接入后的文本第一行包含原始消息第一行、原始级别和 logger、真实 `pid`，以及可用的 `worker_id`、`service_id`。
后续消息行、已有异常堆栈和 stack_info 保留顺序，不重复加前缀。
JSON 沿用现有 `event` 字段保存完整多行消息，换行进行 JSON 转义，异常与堆栈分别保存在 `exception`、`stack` 中。
消息格式化参数在消费时处理；同步和异步输出均保留完整 LogRecord 诊断内容。
结构化敏感字段沿用既有脱敏机制，不将原始消息翻译或替换成摘要，不解析版本号等内容重建消息。

```text
2026-10-30T16:40:39+08:00 | WARNING | Encountered unexpected exception importing solver HIGHS: | logger=__cvxpy__, pid=187, worker_id=host-187
ImportError('/usr/local/lib/python3.12/site-packages/highspy/_core.so: undefined symbol: _ZN5Highs13releaseMemoryEv')
```

接入只使用已有 handler/formatter，不接管 root logger 或其他依赖的输出策略。
日志输出目标仍由配置控制；没有可用 handler 时不接管第三方输出。
Celery 重定向 stdout 时，日志 handler 使用原始输出流，避免将已经格式化的 INFO/DEBUG 重发为 WARNING；
不替换全局 stdout/stderr。原生库直接写入 stdout/stderr 的内容继续原样输出，初始化前的诊断不会重放。
不同进程同时写入终端时，多行内容仍可能交错；格式统一不等于跨进程日志聚合。

上述接入不修复 HIGHS 动态库或 scikit-learn 模型持久化的版本兼容性。
CVXPY 自身只记录异常摘要时，不会凭空生成它未提供的调用栈。

## 停止服务

交互式前台启动运行时或管理控制台时，就绪后仅提示一次“按 Ctrl+C 停止服务”。
提示只写入终端，不写入结构化日志文件。常规容器运行、重定向输出等非交互式场景不显示提示；
`--verbose` 保留第三方启动日志，但不重复输出停止提示。

在前台终端按 `Ctrl+C` 停止服务。`docker logs -f` 中按 `Ctrl+C` 只结束日志跟踪，不会停止容器。
容器及基础设施的停止方式，请参阅[Docker 部署](docker.md#停止服务)。
