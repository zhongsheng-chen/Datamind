# Docker 部署

Datamind 提供正式 Docker 镜像，并支持按模型框架选择镜像。

## 镜像标签

`latest` 指向最新稳定正式版本的完整框架镜像：

```text
docker.io/zhongshengchen/datamind:latest
```

该标签会随正式版本发布而更新。生产环境建议固定明确版本，避免镜像内容随新版本发布发生变化。

完整框架镜像的正式版本使用不可变标签：

```text
docker.io/zhongshengchen/datamind:<version>
```

单框架镜像的正式版本同样不可变，并使用对应后缀：

```text
docker.io/zhongshengchen/datamind:<version>-sklearn
docker.io/zhongshengchen/datamind:<version>-xgboost
docker.io/zhongshengchen/datamind:<version>-lightgbm
docker.io/zhongshengchen/datamind:<version>-catboost
```

## Docker Compose

仓库中的 Docker Compose 配置用于启动 Datamind Runtime、管理控制台以及相关 Worker。

配置文件：

- [Docker Compose](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/docker-compose.yml)
- [Docker 环境变量模板](https://github.com/zhongsheng-chen/Datamind/blob/main/docker/.env.example)

准备配置：

```bash
cd docker
cp .env.example .env.docker
export DATAMIND_IMAGE_TAG=<version>
```

执行数据库迁移：

```bash
docker compose --profile tools run --rm migrate
```

创建首个管理员并完成系统初始化：

```bash
docker compose --profile tools run --rm init
```

启动服务：

```bash
docker compose up -d
```

PostgreSQL、Redis 和 MinIO 作为外部基础设施提供，具体地址和认证信息应通过运行环境配置。

!!! note

    容器访问宿主机上的基础设施时，可根据运行环境使用 `host.docker.internal` 或对应的可解析主机名。
