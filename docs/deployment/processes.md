# 服务管理

在线预测由预测服务处理，批量和影子预测由 Celery 任务 Worker 执行。两类进程分别启动，并共享数据库、模型文件存储和服务环境配置。

## 预测服务与管理控制台

```bash
datamind service run
```

默认预测服务端口为 8700。在另一个终端启动管理控制台：

```bash
datamind console run
```

默认管理控制台端口为 8701。监听地址、进程数和超时见[环境变量](../reference/environment-variables.md)。

管理控制台健康检查使用 `DATAMIND_HEALTHCHECK_URL` 指定的地址：

```bash
datamind console healthcheck
```

检查成功返回退出码 `0`；地址未配置或控制台不可用时返回 `1`。该命令无需登录，默认不输出检查信息。

## 任务 Worker

配置 `DATAMIND_TASK_QUEUE_BROKER_URL` 后启动：

```bash
datamind worker run

# 仅处理批量预测任务
datamind worker run --role batch

# 仅处理影子预测任务，并设置并发数
datamind worker run --role shadow --concurrency 4
```

`DATAMIND_TASK_WORKER_ROLE` 支持 `all`、`batch`、`shadow`，默认 `all`。`batch` 消费批量预测队列，`shadow` 消费影子队列。它们应使用与预测服务一致的数据库、环境、存储和 Broker 配置。

`--role` 和 `--concurrency` 优先于环境配置，仅影响本次启动。未指定时，使用 `DATAMIND_TASK_WORKER_ROLE` 和 `DATAMIND_TASK_WORKER_CONCURRENCY` 的配置值。命令参数见[服务管理 CLI](../cli/processes.md#datamind-worker-run)。

任务 Worker 的健康检查会确认本机 Worker 在线，并消费配置角色要求的队列：

```bash
datamind worker healthcheck
```

健康检查应使用与 Worker 相同的名称、角色和 Broker 配置。若启动时使用 `--role` 覆盖角色，请将检查进程的 `DATAMIND_TASK_WORKER_ROLE` 设置为相同值。

## 就绪与运行状态

预测服务提供 `/health` 和 `/ready`。可通过 `datamind service healthcheck` 检查 `DATAMIND_HEALTHCHECK_URL` 指定的就绪地址。预测服务和任务 Worker 的检查命令无需登录，成功返回退出码 `0`，失败返回 `1`。部署实际运行状态可通过 `datamind runtime list` 和 `datamind runtime show` 查询。启用部署（`Deployment`）后，应核对实际状态与预测结果。

容器进程、任务 Worker 分角色配置和健康检查见[Docker](docker.md)。多实例共享与生产运维见[生产部署](production.md)。
