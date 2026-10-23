# Docker 部署

本教程介绍如何使用 Docker Compose 部署 Datamind，包括环境配置、数据库初始化、服务启动和部署验证。

## 前置条件

开始前，请确认已完成以下准备：

- 安装 [Docker](https://docs.docker.com/get-started/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)，能够执行 `docker compose` 命令。
- 克隆 [Datamind 仓库](https://github.com/zhongsheng-chen/Datamind)。
- 准备 PostgreSQL、Redis 和 MinIO，可使用下节提供的基础设施配置部署。应用容器通过共享网络中的服务名连接。

## 基础设施

仓库提供了[基础设施 Docker Compose 配置](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.infrastructure.yml)，可用于启动 PostgreSQL、Redis 和 MinIO。

1. 从项目根目录复制[基础设施环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.infrastructure.example)，配置 PostgreSQL、Redis 和 MinIO：

    ```bash
    cp docker/.env.infrastructure.example docker/.env.infrastructure
    ```

    在 `.env.infrastructure` 中设置 PostgreSQL 的账户、密码和数据库名，以及 Redis 密码和 MinIO 账户。Redis 使用默认用户 `default`，密码可通过以下命令生成：

    ```bash
    python -c "import secrets; print(secrets.token_urlsafe(64))"
    ```

    将生成的密码填入 `REDIS_PASSWORD`。

    > **注意**
    >
    > PostgreSQL 初始化后，修改环境变量不会更新已有的账户、密码或数据库名。

2. 启动基础设施：

    ```bash
    docker compose --env-file docker/.env.infrastructure -f docker/docker-compose.infrastructure.yml up -d
    ```

    服务启动后，可通过以下地址在本机访问：

    | 服务         | 地址                    |
    |--------------|-------------------------|
    | PostgreSQL   | `127.0.0.1:5432`        |
    | Redis        | `127.0.0.1:6379`        |
    | MinIO API    | `http://127.0.0.1:9000` |
    | MinIO 控制台 | `http://127.0.0.1:9001` |

    服务端口默认绑定到 `127.0.0.1`，仅供本机访问。可修改 `docker-compose.infrastructure.yml` 中的 `ports` 配置，调整端口映射。

## 准备配置

1. 从项目根目录进入 `docker` 目录，复制[环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.example)：

    ```bash
    cd docker
    cp .env.example .env.docker
    ```

2. 修改 `.env.docker`，根据实际环境设置以下连接参数和认证配置：

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

    其中，`DATAMIND_AUTH_SECRET_KEY` 为认证密钥，可通过以下命令生成：

    ```bash
    python -c "import secrets; print(secrets.token_urlsafe(64))"
    ```

3. 默认管理员用户名和密码均为 `admin`。首次初始化前，可在 `.env.docker` 中设置管理员账户：

    ```dotenv
    DATAMIND_INIT_ADMIN_USERNAME=admin-username
    DATAMIND_INIT_ADMIN_PASSWORD=admin-password
    ```

Docker Compose 从 `.env.docker` 加载应用配置。各配置项的含义见[环境变量](../reference/environment-variables.md)，生产环境的配置要求见[生产部署](production.md)。

## 选择镜像

Datamind 提供完整框架镜像和单框架镜像，可选镜像如下：

- `docker.io/zhongshengchen/datamind:latest`
- `docker.io/zhongshengchen/datamind:<version>`
- `docker.io/zhongshengchen/datamind:<version>-sklearn`
- `docker.io/zhongshengchen/datamind:<version>-xgboost`
- `docker.io/zhongshengchen/datamind:<version>-lightgbm`
- `docker.io/zhongshengchen/datamind:<version>-catboost`

设置部署使用的镜像标签：

```bash
export DATAMIND_IMAGE_TAG="<tag>"
```

将 `<tag>` 替换为所需标签，例如 `latest`、`0.1.0` 或 `0.1.0-sklearn`。

> **提示**
>
> `latest` 始终指向最新稳定版本，生产环境建议使用固定版本标签。

## 数据库迁移与系统初始化

执行数据库迁移：

```bash
docker compose --profile setup run --rm migrate
```

首次部署还需初始化系统，创建管理员账户和内置角色：

```bash
docker compose --profile setup run --rm init
```

## 启动服务

在 `docker` 目录下启动服务：

```bash
docker compose up -d
```

## 验证部署

查看容器状态：

```bash
docker compose ps
```

等待预测服务、管理控制台和任务 Worker 均显示为 `healthy`。如有服务未正常启动，可查看日志排查：

```bash
docker compose logs --tail=100
```

服务就绪后，可通过以下地址访问：

| 服务       | 地址                    |
|------------|-------------------------|
| 预测服务   | `http://localhost:8700` |
| 管理控制台 | `http://localhost:8701` |

打开[管理控制台](http://localhost:8701)，使用初始化时设置的管理员账户登录。

> **提示**
>
> 从其他设备访问时，将 `localhost` 替换为服务器的 IP 地址或域名。端口以 [docker-compose.yml](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.yml) 中的映射配置为准。

## 停止服务

在 `docker` 目录下停止应用服务：

```bash
docker compose down
```

如需同时停止基础设施，再执行：

```bash
docker compose --env-file .env.infrastructure -f docker-compose.infrastructure.yml down
```

> **提示**
>
> 停止应用不会影响基础设施和共享网络；停止基础设施会移除共享网络，但保留数据卷。上述两条命令均不要添加 `--remove-orphans`，以免删除另一份配置中的容器。
