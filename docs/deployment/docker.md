# Docker 部署

本教程介绍如何使用 Docker Compose 和现成的 Datamind 镜像部署服务，无需在本地构建镜像。部署过程包括配置运行环境、初始化数据库、启动服务和验证部署结果。

## 前置条件

开始前，请确认已完成以下准备：

- 安装 [Docker](https://docs.docker.com/get-started/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)，能够执行 `docker compose` 命令。
- 克隆 [Datamind 仓库](https://github.com/zhongsheng-chen/Datamind)。
- 准备 PostgreSQL、Redis 和 MinIO，并确保容器能够访问。使用 MinIO 前，需创建模型文件存储桶。上述服务部署在宿主机上时，连接配置中的主机名应设为 `host.docker.internal`。

## 基础设施

已有可用的 PostgreSQL、Redis 和 MinIO 时，可跳过本节。仓库提供了 [基础设施 Docker Compose 配置](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.infrastructure.yml)，可用于启动 PostgreSQL、Redis 和 MinIO。

1. 从项目根目录复制[基础设施环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.infrastructure.example)：

    ```bash
    cp docker/.env.infrastructure.example docker/.env.infrastructure
    ```

    修改 `.env.infrastructure`，设置 PostgreSQL 的账户、密码和数据库名，以及 Redis 密码和 MinIO 账户。Redis 使用默认用户 `default`。PostgreSQL 初始化后，修改环境变量不会更新已有的账户、密码或数据库名。

2. 启动服务并等待健康检查通过：

    ```bash
    docker compose --env-file docker/.env.infrastructure -f docker/docker-compose.infrastructure.yml up -d
    ```

3. 打开 MinIO Console（默认地址为 `http://127.0.0.1:9001`），使用配置的账户登录并创建模型文件存储桶。后续配置中的 `DATAMIND_STORAGE_MINIO_BUCKET` 应填写该存储桶的名称。

服务的默认连接地址如下，端口仅绑定本机。如需调整端口或绑定地址，修改 `docker-compose.infrastructure.yml` 中的 `ports`。

| 服务 | 容器内地址 | 本机地址 |
|------|------------|----------|
| PostgreSQL | `postgres:5432` | `127.0.0.1:5432` |
| Redis | `redis:6379` | `127.0.0.1:6379` |
| MinIO API | `minio:9000` | `127.0.0.1:9000` |
| MinIO Console | `minio:9001` | `127.0.0.1:9001` |

从源码运行 Datamind 时，使用表中的本机地址，继续参阅[本地部署](local.md#配置-datamind)。

继续使用本教程部署 Datamind 时，在同一终端设置以下变量，使后续 Compose 命令同时加载基础设施和应用配置：

```bash
export COMPOSE_FILE="docker-compose.infrastructure.yml:docker-compose.yml"
export COMPOSE_ENV_FILES=".env.infrastructure"
```

以上路径相对于 `docker` 目录，后续步骤将在该目录下执行。Datamind 与基础设施服务共享同一 Docker 网络，使用表中的容器内地址连接；应用配置在下一节的 `.env.docker` 中设置。

## 准备配置

1. 从项目根目录进入 `docker` 目录，复制[环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.example)：

    ```bash
    cd docker
    cp .env.example .env.docker
    ```

2. 修改 `.env.docker`，按实际环境调整以下连接参数和认证配置。示例通过服务名连接同一 Docker 网络中的 PostgreSQL、Redis 和 MinIO：

    ```dotenv
    DATAMIND_ENVIRONMENT=development

    DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/dbname
    DATAMIND_TASK_QUEUE_BROKER_URL=redis://default:password@redis:6379/0

    DATAMIND_STORAGE_TYPE=minio
    DATAMIND_STORAGE_MINIO_ENDPOINT=minio:9000
    DATAMIND_STORAGE_MINIO_BUCKET=minio-bucket-name
    DATAMIND_STORAGE_MINIO_ACCESS_KEY=minio-access-key
    DATAMIND_STORAGE_MINIO_SECRET_KEY=minio-secret-key
    DATAMIND_STORAGE_MINIO_SECURE=false

    DATAMIND_AUTH_ENABLED=true
    DATAMIND_AUTH_SECRET_KEY=auth-secret-key
    ```

    使用上节基础设施时，账户、密码和数据库名应与 `.env.infrastructure` 中的配置一致；MinIO 的访问密钥和秘密密钥分别对应 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD`。

3. 默认管理员用户名和密码均为 `admin`。首次初始化前，可在 `.env.docker` 中设置管理员账户：

    ```dotenv
    DATAMIND_INIT_ADMIN_USERNAME=replace-with-admin-username
    DATAMIND_INIT_ADMIN_PASSWORD=replace-with-admin-password
    ```

Docker Compose 从 `.env.docker` 加载应用配置。各配置项的含义见[环境变量](../reference/environment-variables.md)，生产环境的配置要求见[生产部署](production.md)。

## 选择镜像

Datamind 提供完整框架镜像和单框架镜像。镜像仓库为 `docker.io/zhongshengchen/datamind`，可选标签如下：

| 标签 | 包含的模型框架 |
|------|----------------|
| `<version>` | scikit-learn、XGBoost、LightGBM、CatBoost |
| `<version>-sklearn` | scikit-learn |
| `<version>-xgboost` | XGBoost |
| `<version>-lightgbm` | LightGBM |
| `<version>-catboost` | CatBoost |
| `latest` | 最新稳定版本的全部框架 |

将 `<version>` 替换为正式版本号，例如 `0.1.0`。正式版本标签不可变，`latest` 会随正式版本发布而更新；生产环境建议使用固定版本标签。

设置本次部署使用的镜像标签：

```bash
export DATAMIND_IMAGE_TAG="<tag>"
```

将 `<tag>` 替换为所需标签，例如 `0.1.0` 或 `0.1.0-sklearn`。该变量由当前终端提供，后续 Compose 命令均在同一终端的 `docker` 目录下执行。

## 迁移与初始化

执行数据库迁移：

```bash
docker compose --profile tools run --rm migrate
```

首次部署时，创建初始管理员账户和内置角色：

```bash
docker compose --profile tools run --rm init
```

## 启动服务

仓库中的 [docker/docker-compose.yml](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.yml) 定义了预测服务、管理控制台、两个批量任务 Worker 和一个影子任务 Worker，使用所选镜像启动这些服务。

在 `docker` 目录下执行以下命令，按所选 Compose 配置在后台启动服务：

```bash
docker compose up -d
```

## 验证部署

查看容器运行状态和健康检查结果：

```bash
docker compose ps
```

等待预测服务、管理控制台和任务 Worker 的状态均显示为 `healthy`。如有容器未正常启动，可查看日志：

```bash
docker compose logs --tail=100
```

默认访问地址如下：

| 服务 | 地址 |
|------|------|
| 预测服务 | `http://localhost:8700` |
| 管理控制台 | `http://localhost:8701` |

通过浏览器打开管理控制台，使用初始化时设置的管理员账户登录。在其他设备上访问时，将 `localhost` 替换为部署主机地址；调整端口映射后，使用对应端口。

预测服务和管理控制台均提供 `/health` 和 `/ready` 接口。`/ready` 返回 HTTP 200 表示服务就绪。模型加载状态及预测结果仍需单独验证，具体步骤见[生产部署](production.md#验证在线预测)。
