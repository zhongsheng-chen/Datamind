# Runtime 与 Worker

在线预测由 Runtime 处理，批量和影子预测由 Celery 任务 Worker 执行。两个进程分别启动，并共享数据库、制品存储和服务环境配置。

## Runtime 与 Console

```bash
datamind service run
```

默认 Runtime 端口为 8700。在另一个终端启动 Console：

```bash
datamind console run
```

默认 Console 端口为 8701。监听地址、进程数和超时见[配置](../reference/configuration.md)。

## 任务 Worker

配置 `DATAMIND_TASK_QUEUE_BROKER_URL` 后启动：

```bash
python -m datamind.runtime.task_queue.entrypoints.worker
```

`DATAMIND_TASK_WORKER_ROLE` 支持 `all`、`batch`、`shadow`，默认 `all`。`batch` 消费批量预测队列，`shadow` 消费影子队列。它们应使用与 Runtime 一致的数据库、环境、存储和 Broker 配置。

## 就绪与运行状态

Runtime 提供 `/health` 和 `/ready`。部署实际运行状态可通过 `datamind runtime list` 和 `datamind runtime show` 查询。启用 Deployment 后，应核对实际状态与预测结果。

容器进程、Worker 分角色配置和健康检查见[Docker](docker.md)。多实例共享与生产运维见[生产部署](production.md)。
