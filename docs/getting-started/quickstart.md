# 快速上手

本页给出 Datamind 的最短启动路径。生产环境应根据实际基础设施完成数据库、存储、认证和任务队列配置。

## 1. 配置环境

以仓库中的 [`.env.example`](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example) 为基础创建运行配置。

至少需要正确配置 PostgreSQL；如果使用 MinIO、Redis 或其他可选能力，也应配置对应连接信息。

## 2. 初始化数据库

执行数据库迁移：

```bash
alembic upgrade head
```

初始化 Datamind：

```bash
datamind init
```

## 3. 启动 Runtime Service

```bash
datamind service run
```

默认监听：

```text
http://127.0.0.1:8700
```

## 4. 启动管理控制台

```bash
datamind console run
```

默认监听：

```text
http://127.0.0.1:8701
```

## 下一步

Datamind 的模型交付链路由模型、版本、部署、路由和 Runtime 组成。

理解这些资源之间的关系后，再进行模型注册和部署会更清晰。请继续阅读 [架构](../concepts/architecture.md)。
