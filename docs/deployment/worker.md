# 任务 Worker

任务 Worker 基于 Celery 执行批量预测和影子预测，通过 Redis 消息队列接收任务，并将执行状态和预测结果写入数据库。仅使用在线预测时，无需启动任务 Worker。

## 前置条件

- 已按[本地部署](local.md)或[Docker 部署](docker.md)准备运行环境，并完成数据库迁移与初始化。
- Worker 所在环境具备模型运行所需的依赖，并可访问模型文件。
- Worker 与预测服务使用同一数据库、运行环境和模型文件存储。

## 配置任务队列

在预测服务和 Worker 使用的 `.env` 中配置相同的 Redis 连接地址和队列名称：

```dotenv
DATAMIND_TASK_QUEUE_BROKER_URL=redis://default:password@127.0.0.1:6379/0
DATAMIND_TASK_QUEUE_BATCH_QUEUE=prediction.batch
DATAMIND_TASK_QUEUE_SHADOW_QUEUE=prediction.shadow
```

将 Redis 连接地址替换为实际地址。批量预测与影子预测须使用不同队列，生产、测试等环境之间也应隔离队列，避免任务被其他环境的 Worker 消费。

Worker 与预测服务应使用同一数据库和运行环境，并共享模型文件。模型文件可通过 MinIO 或共享目录提供；使用本地目录时，各进程的访问路径和文件内容须保持一致。

更多配置说明，请参阅[任务队列](../reference/environment-variables.md#任务队列)。

## 选择角色并启动

通过 `DATAMIND_TASK_WORKER_ROLE` 指定处理的任务类型：

| 角色     | 处理任务                     |
|----------|------------------------------|
| `all`    | 批量预测和影子预测，默认角色 |
| `batch`  | 批量预测                     |
| `shadow` | 影子预测                     |

一般开发和联调可使用默认配置：

```dotenv
DATAMIND_TASK_WORKER_ROLE=all
DATAMIND_TASK_WORKER_CONCURRENCY=1
```

启动 Worker：

```bash
datamind worker run
```

如需独立处理批量预测和影子预测，分别以 `batch` 和 `shadow` 角色启动 Worker：

```bash
datamind worker run --role batch
```

```bash
datamind worker run --role shadow
```

## 设置并发数

通过 `DATAMIND_TASK_WORKER_CONCURRENCY` 设置并发数，也可在启动时指定：

```bash
datamind worker run --role batch --concurrency 4
```

`--role` 和 `--concurrency` 优先于对应环境变量。提高并发数会增加内存占用和数据库连接开销，应结合模型大小、任务耗时及可用资源调整。批量任务的分片大小由 `DATAMIND_TASK_QUEUE_BATCH_CHUNK_SIZE` 单独控制。

> **注意**
>
> Windows 使用 `solo` 执行池，任务在单个进程中串行执行，增加并发参数不会获得多进程并行能力。

完整启动参数请参阅[`datamind worker run`](../cli/worker.md#datamind-worker-run)，环境变量请参阅[任务 Worker 配置](../reference/environment-variables.md#任务-worker)。

## 健康检查

在 Worker 所在主机或容器中执行健康检查：

```bash
datamind worker healthcheck
```

该命令检查 Worker 是否在线并消费所需队列。退出码 `0` 表示检查通过，`1` 表示检查失败。

> **提示**
>
> 健康检查使用的 Worker 名称、角色及任务队列配置应与启动时一致。

启动时指定 `--role batch` 的 Worker，可按以下方式检查：

**Linux / macOS**

```bash
DATAMIND_TASK_WORKER_ROLE=batch datamind worker healthcheck
```

**Windows PowerShell**

```powershell
$env:DATAMIND_TASK_WORKER_ROLE = "batch"
datamind worker healthcheck
```

检查通过后，提交实际任务验证预测结果：

- **批量预测**：按照[批量预测](../guides/batch-prediction.md)提交批次，确认任务执行并核对结果。
- **影子预测**：按照[影子发布](shadow.md)配置影子路由，发送命中路由的请求，确认生成影子执行记录。

## 常见问题

- **任务长期等待执行**：检查 Worker 运行状态、任务角色，以及 Redis 连接和队列名称。
- **模型加载失败**：核对数据库和运行环境，检查模型文件访问权限及框架依赖。
- **健康检查失败**：在 Worker 所在主机或容器中执行检查，并确认名称、角色及任务队列配置与启动时一致。

详细排查步骤，请参阅[常见故障排查](production.md#常见故障排查)。
