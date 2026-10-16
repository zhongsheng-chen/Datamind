# Docker 部署

本教程介绍如何使用 Docker Compose 和现成的 Datamind 镜像部署服务，无需在本地构建镜像。部署过程包括配置运行环境、初始化数据库、启动服务和验证部署结果。

## 前置条件

开始前，请确认已完成以下准备：

- 安装 [Docker](https://docs.docker.com/get-started/get-docker/) 和 [Docker Compose](https://docs.docker.com/compose/install/)，能够执行 `docker compose` 命令。
- 克隆 [Datamind 仓库](https://github.com/zhongsheng-chen/Datamind)。
- 准备 PostgreSQL、Redis 和 MinIO，可使用下节提供的基础设施配置部署。应用容器通过共享网络中的服务名连接。

## 共享网络

基础设施 Compose 创建并管理名为 `datamind` 的网络，应用 Compose 通过 `external: true` 使用该网络。两份配置保持独立，先启动基础设施，再启动应用，无需手动创建网络或合并 Compose 文件。

Datamind 容器通过 `postgres:5432`、`redis:6379` 和 `minio:9000` 连接基础设施。停止应用时会保留共享网络；停止基础设施前，应先停止应用，以释放网络连接。

两份 Compose 均使用项目名 `datamind`，分别操作时不要使用 `--remove-orphans`，以免删除另一份配置中的容器。

## 基础设施

已有可用的 PostgreSQL、Redis 和 MinIO 时，可跳过本节，但需确保它们已接入 `datamind` 网络，并分别可通过 `postgres`、`redis` 和 `minio` 访问。仓库提供了 [基础设施 Docker Compose 配置](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.infrastructure.yml)，可用于启动 PostgreSQL、Redis 和 MinIO。

1. 从项目根目录复制[基础设施环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.infrastructure.example)：

    ```bash
    cp docker/.env.infrastructure.example docker/.env.infrastructure
    ```

    修改 `.env.infrastructure`，设置 PostgreSQL 的账户、密码和数据库名，以及 Redis 密码和 MinIO 账户。Redis 使用默认用户 `default`。

    执行以下命令生成 Redis 密码，将输出填入 `.env.infrastructure` 中的 `REDIS_PASSWORD`：

    ```bash
    python -c "import secrets; print(secrets.token_urlsafe(64))"
    ```

    > **注意**
    >
    > PostgreSQL 初始化后，修改环境变量不会更新已有的账户、密码或数据库名。

2. 启动基础设施服务：

    ```bash
    docker compose --env-file docker/.env.infrastructure -f docker/docker-compose.infrastructure.yml up -d
    ```

服务启动后，可通过以下本机地址访问：

| 服务 | 地址 |
|------|------|
| PostgreSQL | `127.0.0.1:5432` |
| Redis | `127.0.0.1:6379` |
| MinIO API | `127.0.0.1:9000` |

MinIO 控制台访问地址为 `http://127.0.0.1:9001`。

端口默认仅绑定本机。如需修改端口或绑定地址，请调整 `docker-compose.infrastructure.yml` 中的 `ports` 配置。

## 准备配置

1. 从项目根目录进入 `docker` 目录，复制[环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.example)：

    ```bash
    cd docker
    cp .env.example .env.docker
    ```

    后续命令均在当前终端的 `docker` 目录下执行。

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

    再次执行以下命令生成独立的认证密钥，将输出填入 `.env.docker` 中的 `DATAMIND_AUTH_SECRET_KEY`：

    ```bash
    python -c "import secrets; print(secrets.token_urlsafe(64))"
    ```

    使用上节基础设施时，账户、密码和数据库名应与 `.env.infrastructure` 中的配置一致；MinIO 的访问密钥和秘密密钥分别对应 `MINIO_ROOT_USER` 和 `MINIO_ROOT_PASSWORD`。`DATAMIND_STORAGE_MINIO_BUCKET` 指定模型文件存储桶，Datamind 初始化 MinIO 存储后端时会自动创建不存在的存储桶，所用账户需具备相应权限。

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

## 停止服务

在 `docker` 目录下停止应用，基础设施和共享网络会保留：

```bash
docker compose down
```

如需停止基础设施，在应用停止后执行：

```bash
docker compose --env-file .env.infrastructure -f docker-compose.infrastructure.yml down
```

基础设施 Compose 会清理共享网络，命名数据卷仍然保留。
