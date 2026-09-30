# 本地演示环境

使用 Docker 启动独立的 PostgreSQL、Redis 和 MinIO，再从源码运行 Datamind。服务仅绑定本机地址，并使用独立端口，便于体验完整的 Console 操作流程。

## 启动基础设施

克隆仓库并在项目根目录执行：

```bash
docker compose -f docs/assets/demo-infrastructure.yml up -d --wait
```

也可下载[演示 Compose 文件](../assets/demo-infrastructure.yml)。文件中的凭据仅用于本地演示。

| 服务 | 本机端口 | 用途 |
| --- | --- | --- |
| PostgreSQL | 15432 | 演示数据库 |
| Redis | 16379 | 批量与影子队列 |
| MinIO API | 19000 | 模型制品 |
| MinIO Console | 19001 | 对象存储管理 |
| Datamind 预测服务（`Runtime`） | 18700 | 预测接口 |
| Datamind Console | 18701 | 操作手册截图对应界面 |

若端口已被占用，请修改 Compose 和对应连接配置。

## 配置 Datamind

在项目根目录创建 `.env`，替换认证签名密钥和管理员密码：

```dotenv
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://datamind_docs:datamind_docs_local@127.0.0.1:15432/datamind_docs
DATAMIND_STORAGE_TYPE=minio
DATAMIND_STORAGE_MINIO_ENDPOINT=127.0.0.1:19000
DATAMIND_STORAGE_MINIO_BUCKET=datamind-docs
DATAMIND_STORAGE_MINIO_ACCESS_KEY=datamind_docs
DATAMIND_STORAGE_MINIO_SECRET_KEY=datamind_docs_local
DATAMIND_STORAGE_MINIO_SECURE=false
DATAMIND_TASK_QUEUE_BROKER_URL=redis://127.0.0.1:16379/0
DATAMIND_TASK_WORKER_CONCURRENCY=4
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=replace-with-a-strong-password
DATAMIND_SERVICE_HOST=127.0.0.1
DATAMIND_SERVICE_PORT=18700
DATAMIND_CONSOLE_HOST=127.0.0.1
DATAMIND_CONSOLE_PORT=18701
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
python -m datamind.runtime.task_queue.entrypoints.worker
```

打开 `http://127.0.0.1:18701`，继续[Console 操作手册](../guides/console.md)。HTTP 示例使用本页环境时，请将默认 8700 端口替换为 18700。

## 停止

在应用终端按 Ctrl+C 停止进程。停止 Compose 基础设施：

```bash
docker compose -f docs/assets/demo-infrastructure.yml down
```

该命令保留命名数据卷，便于恢复演示。再次启动时可继续使用已有数据。
