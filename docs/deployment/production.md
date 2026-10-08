# 生产部署

本页介绍生产环境的部署架构、部署步骤和日常维护，并提供常见故障的排查方法。容器部署步骤见[Docker 部署](docker.md)，环境变量说明见[环境变量](../reference/environment-variables.md)。

## 部署架构

预测服务、管理控制台和任务 Worker 应使用同一部署环境的数据库和文件存储，并保持认证参数一致。预测服务与任务 Worker 通过 Redis 消息队列传递批量预测和影子预测任务，需使用相同的连接地址和对应队列名称。

- **PostgreSQL** 保存平台配置、请求、执行和任务状态。使用持久卷或托管数据库保存数据。
- **Redis** 提供异步任务队列。
- **文件存储** 保存模型文件，可使用 MinIO 或共享本地目录。所有模型加载进程均需能够读取相同的文件；使用本地目录时，路径和内容也需保持一致。

预测服务由多个 Worker 接收 HTTP 请求并执行在线预测。每个 Worker 独立加载模型，通过数据库中的运行控制记录协调加载状态；运行实例记录反映某个部署在各 Worker 中的实际状态。模型内存占用随 Worker 数量增加。

管理控制台可以独立运行。任务 Worker 使用 Celery 执行批量预测和影子预测任务，可按 `all`、`batch` 或 `shadow` 角色分别扩容。负载均衡器将在线请求转发至预测服务。

## 部署步骤

### 安装

安装 Datamind，具体步骤见[安装](../getting-started/installation.md)。使用容器部署请参阅[Docker 部署](docker.md)。

### 准备

创建 PostgreSQL 数据库，启动 Redis 消息队列服务，并检查数据库和消息队列的连接是否正常。为模型文件准备持久化存储：

- 使用默认的本地存储时，将模型目录挂载到持久卷或共享目录；
- 使用 MinIO 时，提前创建存储桶，并确认应用具有读写权限。

### 配置

通过环境变量或 `.env` 文件设置以下内容：

- **环境**：将 `DATAMIND_SERVICE_ENVIRONMENT` 设为 `production`。
- **服务连接**：设置数据库、文件存储和 Redis 的连接参数。
- **身份认证**：将 `DATAMIND_AUTH_ENABLED` 设为 `true`，使用 `DATAMIND_AUTH_SECRET_KEY` 设置随机生成的签名密钥，并在 `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS` 中指定允许访问的网段。各应用进程应使用相同的认证参数。
- **管理员账户**：首次初始化前，通过 `DATAMIND_INIT_ADMIN_PASSWORD` 设置管理员密码。该变量仅用于创建初始账户；已有账户需通过密码重置更新密码。

> **注意**
>
> 生产环境的凭据建议通过部署系统的密钥管理功能提供。使用 `.env` 文件时，应限制其读取权限。

配置示例见[配置与初始化](../getting-started/configuration.md)，更多说明见[环境变量](../reference/environment-variables.md)。

### 数据库迁移与初始化

更新数据库结构：

```bash
datamind db upgrade
```

创建初始管理员账户和内置角色：

```bash
datamind init
```

> **注意**
>
> 数据库迁移应由单个进程执行。升级已有部署时，请先完成迁移，再更新应用。

### 启动服务

启动预测服务：

```bash
datamind service run --host 0.0.0.0 --port 8700
```

在另一个终端启动管理控制台：

```bash
datamind console run --host 0.0.0.0 --port 8701
```

使用批量预测或影子预测时，启动任务 Worker：

```bash
datamind worker run
```

默认角色为 `all`，同时处理批量和影子任务。可通过 `DATAMIND_TASK_WORKER_ROLE` 设为 `batch` 或 `shadow`。

### 验证在线预测

通过 `/health` 和 `/ready` 检查服务状态。服务就绪后，注册并激活模型、启用部署，再查看模型的实际加载状态：

```bash
datamind runtime list
```

确认目标部署的运行实例状态为 `running` 后，发送[在线预测](../guides/online-prediction.md)请求，确认服务正常返回预测结果。

### 验证异步任务

启用批量预测后，提交[批量预测](../guides/batch-prediction.md)请求，等待任务结束并核对每条预测结果。配置[影子发布](shadow.md)后，发送能够命中影子路由的请求，确认主请求正常返回，并生成独立的影子执行记录。

确认预测结果符合预期，日志和审计中没有异常，队列与文件存储正常后，再接入生产流量。

## 容量与监控

### 监控指标

持续关注以下指标：

- **在线预测**：请求延迟和失败率。
- **模型加载**：运行实例心跳、加载状态和错误信息。
- **异步任务**：批次进度、任务失败率和影子任务积压。
- **基础服务**：Redis 内存、数据库连接数和模型文件存储空间。

`/health` 和 `/ready` 用于检查预测服务的健康与就绪状态。模型是否已加载、预测是否正常，仍需通过运行实例和实际请求验证。

### 连接池和内存

每个进程维护独立的数据库连接池。设置 `DATAMIND_DATABASE_POOL_SIZE` 和 `DATAMIND_DATABASE_MAX_OVERFLOW` 时，应按预测服务、管理控制台和任务 Worker 的进程总数估算连接需求。

模型由各预测服务 Worker 和任务 Worker 分别加载。增加进程数量前，应评估各进程加载模型所需的内存。

### 任务队列

批量分片大小和任务并发数分别控制任务规模与执行能力：

- `DATAMIND_TASK_QUEUE_BATCH_CHUNK_SIZE`：每个批量分片包含的请求数。
- `DATAMIND_TASK_WORKER_CONCURRENCY`：任务 Worker 的并发数。

设置 `DATAMIND_TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS` 时，应为任务执行预留充足时间，避免长任务在完成前被重新投递。

批次状态为 `queued` 表示等待处理，不代表任务 Worker 已取得消息。应结合队列积压和 Worker 日志判断消费情况。

## 备份与恢复

备份应包含以下内容：

- PostgreSQL 数据库；
- MinIO 模型文件桶或本地模型目录；
- 应用版本与部署配置。

数据库和模型文件的备份应保持一致。只备份数据库无法恢复模型文件，只备份模型文件无法恢复版本、路由和实验关系。备份完成后，应在隔离环境中验证恢复流程。

恢复时按以下顺序操作：

1. 准备基础设施与凭据，还原数据库和模型文件。
2. 使用兼容的应用版本启动，检查数据库迁移和模型文件可读性。
3. 检查预测服务就绪状态和部署运行实例，完成一次实际预测。
4. 使用批量或影子能力时，提交新任务验证消息队列和任务 Worker。

模型加载出现问题时，应检查文件访问和运行依赖，不要直接编辑数据库状态。

## 升级和回滚

### 升级

升级前，记录当前镜像和数据库迁移版本，完成数据备份，并在测试环境验证迁移及已有模型的兼容性。生产镜像应使用固定版本标签，框架依赖应与模型匹配。

确认验证通过后，先执行数据库迁移，再滚动更新应用，最后验证在线预测与异步任务。

### 回滚

应用和数据库的回滚需要分别评估。新迁移可能不兼容旧应用，切换旧镜像也不会自动回退数据库。

Datamind CLI 支持通过以下命令降级到指定迁移版本：

```bash
datamind db downgrade --revision <revision>
```

将 `<revision>` 替换为目标迁移版本，使用 `-1` 可回退一步。命令默认要求确认，自动化执行时可添加 `--yes`。降级可能删除表或数据，应先备份并验证目标版本与应用的兼容性。当前仅有初始迁移，回退一步或降级到 `base` 会删除业务表。

迁移降级不会恢复已经丢失的数据。如需恢复数据，应使用已验证的备份。模型发布回滚见[金丝雀发布](canary.md)。

<a id="troubleshooting" name="troubleshooting"></a>

## 常见故障排查

先记录故障发生时间、`request_id`、`batch_id`、`deployment_id` 和服务环境。排查过程中同时检查部署状态和运行实例。部署为 `active` 表示已启用，运行实例状态才能反映各预测服务 Worker 是否已成功加载模型。

### `/ready` 返回 HTTP 503

1. 分别调用进程健康和就绪接口：

   ```bash
   curl -i -X POST http://127.0.0.1:8700/health \
     -H "Content-Type: application/json" \
     -d '{}'

   curl -i -X POST http://127.0.0.1:8700/ready \
     -H "Content-Type: application/json" \
     -d '{}'
   ```

2. 根据结果缩小范围：

   - `/health` 无法连接：检查预测服务 Worker、监听地址、端口和代理转发，尚未进入 Datamind 就绪检查。
   - `/health` 为 200、`/ready` 为 503：当前预测服务 Worker 可以响应，但数据库连接失败或协调循环未运行。检查预测服务日志、`DATAMIND_DATABASE_URL`、网络与数据库权限。
   - 两者均为 200：预测服务本身已就绪，继续检查具体部署的运行实例，而不是反复重启探针。

3. 修复后重新调用 `/ready`，确认 HTTP 200 和 `status=ready`；再运行 `datamind runtime list` 并完成一次真实预测。就绪检查只验证数据库可查询和协调循环运行，不验证数据库迁移是否完整，也不能证明目标部署已经加载。

### 部署已启用，但预测失败

1. 对照部署配置和实际加载状态：

   ```bash
   datamind deployment show <deployment_id>
   datamind runtime show <deployment_id>
   ```

2. 检查结果：

   - 部署应为 `active`，环境应与预测服务的 `DATAMIND_SERVICE_ENVIRONMENT` 一致。
   - 运行控制的 `desired_status` 应为 `loaded`。
   - 每个预期的预测服务 Worker 都应存在运行实例；正常实例状态为 `running`，`applied_generation` 应与 `control.generation` 一致，`error` 应为 `null`，心跳应持续更新。
   - `failed` 或非空 `error` 通常需要结合预测服务日志检查模型文件是否可读、文件摘要是否匹配、模型框架依赖是否安装，以及本地模型目录是否对所有实例可见。

3. 修复模型文件访问或运行依赖后，可请求重新加载当前部署：

   ```bash
   curl -sS http://127.0.0.1:8700/admin/reload \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{"request":{"deployment_id":"<deployment_id>"}}'
   ```

4. 等待 `datamind runtime show <deployment_id>` 中的目标实例恢复为 `running`。先使用显式 `deployment_id` 发起定向预测，确认模型可执行；再使用正常的模型路由请求，区分加载故障与路由配置问题。

### 返回 `RuntimeRouteError` 或“没有可用部署”

1. 使用同一份输入分别执行一次定向预测和一次普通预测。定向请求显式提供 `<deployment_id>`，普通请求不提供；请求格式见[在线预测](../guides/online-prediction.md)。如果定向预测成功而普通预测失败，模型加载链路可用，应继续检查路由决策。
2. 查看当前环境可用的部署与已启用路由，并逐一核对目标：

   ```bash
   datamind deployment list --model-id <model_id> --status active
   datamind route list --enabled
   datamind deployment show <deployment_id>
   datamind runtime show <deployment_id>
   ```

3. 如果错误明确为“没有可用部署”，应确认请求模型在当前环境至少存在一个处于生效时间内的 `active` 非影子部署。没有匹配的普通路由时，系统仍会尝试回退到可用部署，因此不能只补建路由而忽略部署状态。若错误指向路由比例或规则，则检查启用路由的比例约束和规则结构；实验请求还应检查实验和分组状态。具体决策顺序见[流量分配与决策优先级](../routing/index.md)。
4. 修正并启用有效路由后，重新发送不带 `deployment_id` 的请求。确认响应为 `success=true`，再根据返回的 `request_id` 在管理控制台的请求与执行记录中核对实际部署和版本；不要用定向请求代替路由恢复验证。

### 批次长时间停留在 `queued`

1. 使用提交时返回的 ID 查询批次：

   ```bash
   curl -sS http://127.0.0.1:8700/predict/batch/status \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{"request":{"batch_id":"<batch_id>"}}'
   ```

2. 同时检查预测服务与任务 Worker 的 `DATAMIND_TASK_QUEUE_BROKER_URL` 是否指向同一 Redis 消息队列；消费批量任务的进程角色应为 `batch` 或 `all`，并与生产者使用相同的 `DATAMIND_TASK_QUEUE_BATCH_QUEUE`。查看任务 Worker 日志，确认它已经连接 Redis 并消费目标队列。

3. 区分不同结果：投递阶段出现 `TaskDispatchError` 表示预测服务没有成功发布任务；持续 `queued` 且计数不变化通常表示没有匹配的任务 Worker 或队列名不一致；进入 `running` 后停滞则应检查任务 Worker 日志、模型执行耗时和 `DATAMIND_TASK_QUEUE_VISIBILITY_TIMEOUT_SECONDS`。

4. 修复 Redis 连接 或启动正确角色的任务 Worker 后，原有 `queued` 消息应开始推进。只有 `cancelled`、`partially_succeeded` 或 `failed` 批次允许客户端重试，不能对仍为 `queued` 的批次调用重试。最终确认状态进入终态，并核对完成数、成功数、失败数和逐条结果。

### 没有影子执行结果

1. 确认预测服务启用了 `DATAMIND_RUNTIME_SHADOW_ENABLED`，并检查当前环境的影子路由：

   ```bash
   datamind route list --rollout shadow --enabled
   ```

2. 核对影子路由的部署、比例、规则和生效时间。影子比例小于 1 时，单次请求没有命中并不代表配置失效。
3. 确认任务 Worker 角色为 `shadow` 或 `all`，且生产者和消费者使用相同的 Redis 消息队列 与 `DATAMIND_TASK_QUEUE_SHADOW_QUEUE`。按主请求的 `request_id` 在执行记录中检查影子任务是未创建、仍在队列中还是执行失败。
4. 修复后发送一个符合路由规则的新请求。主响应仍应来自主部署，同时应新增独立的 `shadow` 执行记录；系统不提供针对任意历史影子执行的公开重试接口。

### 出现 401 或 403

1. 保留原请求的 HTTP 状态、`error_type` 和 `request_id`。401 表示凭据缺失、过期或签名校验失败；403 表示身份已通过认证，但缺少接口要求的权限。
2. 对于 401，重新调用 `/auth/login` 获取 HTTP 访问令牌。如果同一令牌经过负载均衡后间歇性失败，核对所有预测服务进程使用的认证签名密钥。
3. 对于 403，核对用户、角色和权限：

   ```bash
   datamind user show <username>
   datamind role show <role_name>
   ```

4. 修复后重复原受保护请求并确认其成功。只验证登录接口不能证明目标权限已经恢复。


### 审计写入失败

`DATAMIND_AUDIT_FAILURE_MODE=closed` 时，审计写入失败会阻止受审计的管理操作。此类失败应根据响应中的错误类型和审计日志排查，不应仅凭操作失败判断为认证或权限问题。

检查数据库连接、写入权限和审计日志，修复后重新执行原操作。避免直接修改数据库状态绕过审计和生命周期校验。
