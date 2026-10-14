# 本地部署

使用 Docker 启动独立的 PostgreSQL、Redis 和 MinIO，再从源码运行 Datamind。基础设施使用默认端口并仅绑定本机地址，便于体验完整的 Console 操作流程。

## 基础设施

按 [Docker 部署中的“基础设施”](docker.md#基础设施)一节启动 PostgreSQL、Redis 和 MinIO，并创建 `datamind` 存储桶。随后返回本页，从项目根目录继续配置 Datamind。

本页从宿主机运行 Datamind，使用该节列出的本机地址，无需设置用于合并应用配置的 `COMPOSE_FILE`。

## 配置 Datamind

在项目根目录创建 `.env`，替换认证签名密钥和管理员密码。如已修改基础设施的账户、密码、数据库名或本机端口，同步调整以下连接配置：

```dotenv
DATAMIND_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://replace-with-postgres-username:replace-with-postgres-password@127.0.0.1:5432/replace-with-postgres-database
DATAMIND_STORAGE_TYPE=minio
DATAMIND_STORAGE_MINIO_ENDPOINT=127.0.0.1:9000
DATAMIND_STORAGE_MINIO_BUCKET=datamind
DATAMIND_STORAGE_MINIO_ACCESS_KEY=replace-with-minio-access-key
DATAMIND_STORAGE_MINIO_SECRET_KEY=replace-with-minio-secret-key
DATAMIND_STORAGE_MINIO_SECURE=false
DATAMIND_TASK_QUEUE_BROKER_URL=redis://default:replace-with-redis-password@127.0.0.1:6379/0
DATAMIND_TASK_WORKER_CONCURRENCY=4
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=replace-with-a-strong-password
DATAMIND_SERVICE_HOST=127.0.0.1
DATAMIND_SERVICE_PORT=8700
DATAMIND_CONSOLE_HOST=127.0.0.1
DATAMIND_CONSOLE_PORT=8701
```

## 初始化与启动

激活 Python 虚拟环境，使 `python`、`datamind` 和 `bentoml` 来自同一环境：

```bash
python -m pip install -e ".[sklearn,catboost,xgboost]"
npm ci
npm run build:console
datamind db upgrade
datamind init
datamind login --username admin
```

随后在三个终端、同一配置目录中分别运行：

```bash
datamind service run
```

```bash
datamind console run
```

```bash
datamind worker run
```

打开 `http://127.0.0.1:8701`，按[管理控制台](../guides/console.md)中的步骤注册模型并创建部署。

## 停止

在应用终端按 Ctrl+C 停止进程。停止 Compose 基础设施：

```bash
docker compose --env-file docker/.env.infrastructure -f docker/docker-compose.infrastructure.yml down
```

该命令保留命名数据卷，便于恢复演示。再次启动时可继续使用已有数据。
