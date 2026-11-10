# 升级

本文介绍如何使用 Docker Compose 升级 Datamind，包括镜像准备、容器更新、状态检查和版本回退。 升级前，请查阅目标版本的发布说明，了解兼容性要求及数据库结构变更，并完成数据库备份。

## 准备镜像

Datamind 支持从镜像仓库拉取镜像，也支持使用已导入的本地镜像。根据部署环境选择其中一种方式即可。

### 方式一：从镜像仓库拉取（推荐）

在 `.env.docker` 中设置镜像标签：

```dotenv
DATAMIND_IMAGE_REPOSITORY=docker.io/zhongshengchen/datamind
DATAMIND_IMAGE_TAG=<tag>
```

将 `<tag>` 替换为实际发布的版本标签，然后拉取镜像：

```bash
docker compose --env-file .env.docker pull
```

更多关于镜像及标签的说明，请参阅[选择镜像](docker.md#选择镜像)。

### 方式二：使用本地镜像（离线部署）

适用于无法连接镜像仓库，或镜像已提前导入服务器的环境。

如果镜像以 tar 文件提供，先导入镜像：

```bash
docker load -i datamind-latest.tar
```

根据本地镜像的实际名称和标签，在 `.env.docker` 中设置：

```dotenv
DATAMIND_IMAGE_REPOSITORY=datamind
DATAMIND_IMAGE_TAG=<tag>
```

使用 `docker image ls` 确认镜像存在。此方式无需执行 `docker compose pull`。

### 验证镜像

查看 Docker Compose 配置中实际引用的镜像：

```bash
docker compose --env-file .env.docker config --images
```

检查本地镜像：

```bash
docker image inspect <repository>:<tag>
```

## 更新容器

重新创建容器并等待服务就绪：

```bash
docker compose --env-file .env.docker up -d \
  --no-deps \
  --pull never \
  --force-recreate \
  --wait \
  --wait-timeout 180
```

参数说明：

- `--no-deps`：不自动启动依赖服务。
- `--pull never`：使用本地镜像，不从镜像仓库拉取。
- `--force-recreate`：强制重新创建容器，使更新后的配置生效。
- `--wait`：等待服务进入运行或健康状态。
- `--wait-timeout 180`：最长等待 180 秒。

> **注意：** 上述命令会重新创建 `docker-compose.yml` 中所有启用的服务容器。如需仅更新部分服务，应在命令末尾指定服务名称，并通过 `--no-deps` 避免自动启动其依赖服务。

## 检查状态

查看容器状态，确认均为 `healthy`：

```bash
docker compose --env-file .env.docker ps
```

查看容器使用的镜像，确认标签与设置一致：

```bash
docker compose --env-file .env.docker images
```

## 回退

升级后如服务启动失败或运行异常，可先查看日志排查问题：

```bash
docker compose --env-file .env.docker logs --tail=100 \
  runtime console batch-worker-a batch-worker-b shadow-worker
```

容器重建后会生成新的 `service_id`，排查日志时应使用本次启动的标识。详见[服务、进程与运行实例标识](../concepts/architecture.md#服务进程与运行实例标识)。

如需回退，在 `.env.docker` 中恢复升级前的镜像仓库和版本标签，并确保原版本镜像可用。随后按照[更新容器](#更新容器)中的步骤重新创建容器，并通过[检查状态](#检查状态)验证运行结果。

> **注意：** 镜像回退不会自动恢复数据库结构。如升级涉及不兼容的数据库迁移，应先确认回退方案，避免旧版本程序与数据库结构不兼容。
