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

## 停止服务

在终端按 `Ctrl+C` 停止服务。基础设施的停止方式，请参阅[Docker 部署](docker.md#停止服务)。
