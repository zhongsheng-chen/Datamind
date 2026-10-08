# 本地部署

使用 Docker 启动独立的 PostgreSQL、Redis 和 MinIO，再从源码运行 Datamind。基础设施使用默认端口并仅绑定本机地址，便于体验完整的 Console 操作流程。

## 启动基础设施

克隆仓库并在项目根目录执行：

```bash
docker compose -f docker/docker-compose.infrastructure.yml up -d --wait
```

也可查看[演示 Compose 文件](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.infrastructure.yml)。文件中的凭据仅用于本地演示。

| 服务 | 本机端口 | 用途 |
| --- | --- | --- |
| PostgreSQL | 5432 | 演示数据库 |
| Redis | 6379 | 批量与影子队列 |
| MinIO API | 9000 | 模型文件存储 |
| MinIO Console | 9001 | 对象存储管理 |
| Datamind 预测服务 | 8700 | 预测接口 |
| Datamind 管理控制台 | 8701 | 模型与部署管理 |

若端口已被占用，请修改 Compose 和对应连接配置。

## 配置 Datamind

在项目根目录创建 `.env`，替换认证签名密钥和管理员密码：

```dotenv
DATAMIND_SERVICE_ENVIRONMENT=development
DATAMIND_DATABASE_URL=postgresql+asyncpg://datamind:datamind@127.0.0.1:5432/datamind
DATAMIND_STORAGE_TYPE=minio
DATAMIND_STORAGE_MINIO_ENDPOINT=127.0.0.1:9000
DATAMIND_STORAGE_MINIO_BUCKET=datamind
DATAMIND_STORAGE_MINIO_ACCESS_KEY=datamind
DATAMIND_STORAGE_MINIO_SECRET_KEY=datamind
DATAMIND_STORAGE_MINIO_SECURE=false
DATAMIND_TASK_QUEUE_BROKER_URL=redis://127.0.0.1:6379/0
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
docker compose -f docker/docker-compose.infrastructure.yml down
```

该命令保留命名数据卷，便于恢复演示。再次启动时可继续使用已有数据。
