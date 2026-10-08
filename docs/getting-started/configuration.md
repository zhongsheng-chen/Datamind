# 配置与初始化

安装完成后，配置数据库、文件存储和身份认证，再执行数据库迁移与系统初始化。

## 准备

- **PostgreSQL**：数据库服务，用于保存平台配置和运行数据。
- **Redis**：消息队列服务，用于为批量预测和影子预测提供异步任务队列。
- **MinIO（可选）**：文件存储服务，用于集中存储模型文件。默认使用本地文件存储。

容器部署可使用以下镜像：

- **PostgreSQL**：[Docker 官方镜像](https://hub.docker.com/_/postgres)，例如 `postgres:17.11`。
- **Redis**：[Docker 官方镜像](https://hub.docker.com/_/redis)，例如 `redis:8.8.2`。
- **MinIO**：社区版官方镜像已不再通过 [Docker Hub](https://hub.docker.com/r/minio/minio) 和 [Quay](https://quay.io/repository/minio/minio) 提供，可参考[官方源码构建说明](https://github.com/minio/minio#source-only-distribution)自行构建。项目持续集成（CI）测试使用 `ghcr.io/zhongsheng-chen/minio:RELEASE.2025-09-07T16-13-09Z`，该镜像由项目维护，并非 MinIO 官方镜像。

持续集成使用的完整镜像配置见[测试工作流](https://github.com/zhongsheng-chen/Datamind/blob/main/.github/workflows/test.yml)。

## 配置

在工作目录下创建 `.env` 文件：

```dotenv
# 环境
DATAMIND_SERVICE_ENVIRONMENT=development

# 数据库连接地址
DATAMIND_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname

# 身份认证
DATAMIND_AUTH_ENABLED=true
DATAMIND_AUTH_SECRET_KEY=replace-with-a-long-random-secret
```

将配置示例中的数据库连接地址替换为实际地址，并设置随机生成的签名密钥。执行迁移前，请确保数据库已创建。 模型文件默认保存在本地。有关文件存储和环境变量的更多说明，请参阅[生产部署](../deployment/production.md)和[环境变量](../reference/environment-variables.md)。配置示例见项目根目录的 [`.env.example`](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example)。

## 数据库迁移与系统初始化

```bash
datamind db upgrade
datamind init
```

默认管理员用户名和密码均为 `admin`。如需自定义，请在执行 `datamind init` 前将以下配置写入 `.env`：

```dotenv
DATAMIND_INIT_ADMIN_USERNAME=admin
DATAMIND_INIT_ADMIN_PASSWORD=replace-with-a-strong-password
```

迁移负责创建或更新数据库结构，初始化负责创建管理员及内置角色，两者不能相互替代。

## CLI 登录

使用初始化时创建的管理员账号登录：

```bash
datamind login --username admin
```

按提示输入初始化时设置的密码，CLI 将保存登录凭据。登录后，确认当前身份：

```bash
datamind whoami
```

配置完成后，请参阅[快速上手](quickstart.md)，开始使用 Datamind。
