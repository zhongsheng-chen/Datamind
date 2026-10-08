# 预测 API

预测服务（`Runtime`）默认监听 `http://127.0.0.1:8700`，负责在线预测、批量任务提交和部署运行控制。预测服务可以启动多个 Worker：每个预测服务 Worker 都能接收 HTTP 请求并协调模型加载；运行实例表示某个部署在某个预测服务 Worker 中的加载与运行状态。异步批量预测和影子预测由独立的任务 Worker 执行。

本页说明 HTTP 协议、认证、权限、响应和错误。请求对象的字段、类型和约束见[请求字段](runtime-schemas.md)，完整操作流程见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

## 协议约定

- 本页列出的接口均使用 `POST`。`/health` 和 `/ready` 也是 BentoML API，不支持 `GET`。
- `/auth/*` 直接接收认证字段。预测、反馈和运行控制接口将请求对象放在外层 `request` 字段中。
- `/admin/services`、`/health` 和 `/ready` 没有请求字段，调用时发送空 JSON 对象 `{}`，不添加外层 `request`。
- 启用认证后，受保护接口要求 `Authorization: Bearer <access_token>`，并校验接口表中列出的权限。
- 时间字段使用带时区的 ISO 8601 字符串。资源 ID、请求 ID 和令牌均应视为不透明字符串。
- 对于包含 `success` 的响应，客户端应同时检查 HTTP 状态码和 `success`。批量提交返回 HTTP 202 只表示任务已排队。

示例中的 `<access_token>`、`<model_name>`、`<deployment_id>`、`<batch_id>`、`<request_id>` 和其他尖括号内容均为占位符，调用前必须替换。

## 认证

登录请求不使用外层 `request`：

```bash
curl -sS http://127.0.0.1:8700/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<password>"}'
```

成功响应：

```json
{
  "access_token": "<access_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

`expires_in` 的单位为秒。应急账户可能不签发 `refresh_token`。刷新操作会轮换刷新令牌，客户端必须保存响应中的新令牌：

```bash
curl -sS http://127.0.0.1:8700/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

退出时提交当前刷新令牌。成功返回 HTTP 204，响应体为空：

```bash
curl -i http://127.0.0.1:8700/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

在 `development` 和 `testing` 环境中关闭认证时，受保护接口以系统身份执行，不需要 Bearer 令牌。`staging` 和 `production` 环境必须启用认证，否则受保护接口返回 HTTP 503。

## 接口与权限

| 方法 | 路径 | 输入 | 权限 | 成功结果 |
| --- | --- | --- | --- | --- |
| `POST` | `/auth/login` | `username`、`password` | 本地账户认证 | 访问令牌和可选刷新令牌 |
| `POST` | `/auth/refresh` | `refresh_token` | 有效刷新令牌 | 轮换后的令牌 |
| `POST` | `/auth/logout` | `refresh_token` | 刷新令牌校验 | HTTP 204，无响应体 |
| `POST` | `/predict` | `PredictRequest` | `prediction.invoke` | 主预测结果和 `request_id` |
| `POST` | `/predict/batch` | `BatchPredictRequest` | `prediction.invoke` | HTTP 202、`batch_id` 和排队状态 |
| `POST` | `/predict/batch/status` | `BatchReferenceRequest` | `prediction.invoke` | 批次状态、计数和可用结果 |
| `POST` | `/predict/batch/cancel` | `BatchReferenceRequest` | `prediction.invoke` | 取消请求后的批次状态 |
| `POST` | `/predict/batch/retry` | `BatchReferenceRequest` | `prediction.invoke` | HTTP 202、重新排队后的状态 |
| `POST` | `/admin/reload` | `ControlRequest` | `runtime.manage` | 递增控制代次并请求重新加载 |
| `POST` | `/admin/status` | `DeploymentRequest` | `runtime.read` | 控制状态、各运行实例及当前 Worker 的本地状态 |
| `POST` | `/admin/services` | 空 JSON 对象 `{}` | `runtime.read` | 当前预测服务 Worker 已加载的服务信息 |
| `POST` | `/health` | 空 JSON 对象 `{}` | 无资源权限 | 当前预测服务 Worker 能否响应 |
| `POST` | `/ready` | 空 JSON 对象 `{}` | 无资源权限 | 数据库和协调循环状态；未就绪时为 HTTP 503 |

## 健康与就绪探针

`/health` 用于确认当前预测服务 Worker 可以响应请求；`/ready` 还检查数据库连接和协调循环。两者均使用 `POST`：

```bash
curl -fsS -X POST http://127.0.0.1:8700/health \
  -H "Content-Type: application/json" \
  -d '{}'

curl -fsS -X POST http://127.0.0.1:8700/ready \
  -H "Content-Type: application/json" \
  -d '{}'
```

就绪响应包含以下字段：

```json
{
  "status": "ready",
  "database_ready": true,
  "reconciler_running": true,
  "worker_id": "<worker_id>",
  "environment": "production"
}
```

数据库不可用或协调循环未运行时，`/ready` 返回 HTTP 503，`status` 为 `not_ready`。`/ready` 成功不表示所有部署都已加载；发布后仍需检查运行控制状态并执行真实预测。

容器探针可以运行 `datamind service healthcheck`。该入口读取 `DATAMIND_HEALTHCHECK_URL`，使用 `POST` 和空 JSON 对象调用配置的就绪地址。只支持 HTTP GET 的探针不能直接调用这两个预测服务路径。

## 单条预测

以下请求展示协议结构。`features` 必须替换为目标模型要求的字段和值：

```bash
curl -sS http://127.0.0.1:8700/predict \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "model_name": "<model_name>",
      "subject_key": "<stable_subject_key>",
      "subject_type": "customer",
      "features": {"feature_0": 0.75, "feature_1": 1.25}
    }
  }'
```

分类响应包含预测类别、标签、概率和阈值。以下标签和数值仅说明响应结构：

```json
{
  "success": true,
  "task_type": "classification",
  "prediction": 1,
  "label": "positive",
  "probability": 0.83,
  "threshold": 0.5,
  "request_id": "<request_id>"
}
```

评分响应还包含决策、评分截距和逐特征明细。以下使用单特征评分模型说明字段关系，并非快速上手模型对某条业务输入的实际结果：

```json
{
  "success": true,
  "task_type": "scoring",
  "score": 600.0,
  "probability": 0.2,
  "decision": "approve",
  "threshold": 600.0,
  "score_intercept": 0.0,
  "features": {
    "age": {
      "value": 35,
      "bin": "[30, 40)",
      "woe": 6.0,
      "points": 600.0
    }
  },
  "request_id": "<request_id>"
}
```

评分总分等于 `score_intercept` 加上各特征的 `points`。具体业务输入见[评分与分类](../guides/scoring-and-classification.md)。显式提供 `deployment_id` 会绕过实验和普通路由，但仍校验模型、环境、部署状态和生效时间，且不能指向影子部署。

## 批量预测

### 提交批次

批量接口持久化请求并向 Broker 投递任务。提交成功返回 HTTP 202：

```bash
curl -sS http://127.0.0.1:8700/predict/batch \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "model_name": "<model_name>",
      "instances": [
        {
          "features": {"<feature_name>": "<value>"},
          "subject_key": "customer-001",
          "subject_type": "customer"
        }
      ]
    }
  }'
```

```json
{
  "success": true,
  "batch_id": "<batch_id>",
  "status": "queued",
  "submitted_count": 1,
  "status_url": "/predict/batch/status"
}
```

该响应不包含预测结果。Broker 投递失败时返回 HTTP 503，并将批次标记为 `failed`。

### 查询批次

```bash
curl -sS http://127.0.0.1:8700/predict/batch/status \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

状态响应始终包含总数、完成数、成功数、失败数和尝试次数。`error` 和 `result` 仅在对应内容已经产生时出现：

```json
{
  "success": true,
  "batch_id": "<batch_id>",
  "status": "succeeded",
  "total_count": 1,
  "completed_count": 1,
  "succeeded_count": 1,
  "failed_count": 0,
  "attempt_count": 1,
  "created_at": "2026-10-08T10:00:00.000Z",
  "started_at": "2026-10-08T10:00:01.000Z",
  "finished_at": "2026-10-08T10:00:02.000Z",
  "result": {
    "success": true,
    "count": 1,
    "succeeded_count": 1,
    "failed_count": 0,
    "predictions": [
      {
        "success": true,
        "task_type": "classification",
        "prediction": 1,
        "label": "positive",
        "probability": 0.83,
        "threshold": 0.5,
        "request_id": "<request_id>"
      }
    ],
    "batch_id": "<batch_id>"
  }
}
```

示例时间、标签和预测数值只说明字段结构。客户端应查询到 `succeeded`、`partially_succeeded`、`failed` 或 `cancelled`，并逐条检查 `result.predictions[*].success`。

### 取消与重试

两个操作使用相同的请求对象：

```bash
curl -sS http://127.0.0.1:8700/predict/batch/cancel \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"batch_id":"<batch_id>"}}'

curl -sS http://127.0.0.1:8700/predict/batch/retry \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

| 操作 | 可接受状态 | 结果 |
| --- | --- | --- |
| 取消 | `queued`、`retrying` | 直接进入 `cancelled` |
| 取消 | `running` | 进入 `cancelling`，等待任务 Worker 协作停止 |
| 重复取消 | `cancelling`、`cancelled` | 保持当前状态 |
| 重试 | `partially_succeeded`、`failed`、`cancelled` | 返回 HTTP 202，并以同一 `batch_id` 重新排队 |

其他状态返回 HTTP 409。手动重试保留已成功实例，只重新处理尚未成功的实例。完整操作建议见[批量预测](../guides/batch-prediction.md)。

## 运行控制

部署的启用与停用由 `datamind deployment enable` 和 `datamind deployment disable` 管理。这两个命令会同步部署状态和共享控制状态；Runtime API 不另行提供加载或卸载入口。

### 重新加载启用中的部署

`/admin/reload` 递增共享控制状态的 `generation`，使各运行实例重新加载部署。目标部署必须属于当前预测服务环境，并且处于 `active` 状态。

```bash
curl -sS http://127.0.0.1:8700/admin/reload \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"deployment_id":"<deployment_id>"}}'
```

成功响应表示期望状态已经更新，不表示所有运行实例已经完成协调：

```json
{
  "success": true,
  "request_id": "<request_id>",
  "action": "reload",
  "accepted": true,
  "control": {
    "control_id": "<control_id>",
    "deployment_id": "<deployment_id>",
    "environment": "production",
    "desired_status": "loaded",
    "generation": 2,
    "created_by": "admin",
    "updated_by": "admin",
    "created_at": "2026-10-08T02:00:00+00:00",
    "updated_at": "2026-10-08T02:00:00+00:00"
  }
}
```

### 检查协调结果

```bash
curl -sS http://127.0.0.1:8700/admin/status \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"deployment_id":"<deployment_id>"}}'
```

以下示例表示两个预测服务 Worker 都已应用控制代次 `2`。时间、ID 和文件路径仅展示返回结构，不是固定值：

```json
{
  "success": true,
  "request_id": "<request_id>",
  "deployment_id": "<deployment_id>",
  "environment": "production",
  "control": {
    "control_id": "<control_id>",
    "deployment_id": "<deployment_id>",
    "environment": "production",
    "desired_status": "loaded",
    "generation": 2,
    "created_by": "admin",
    "updated_by": "admin",
    "created_at": "2026-10-08T02:00:00+00:00",
    "updated_at": "2026-10-08T02:05:00+00:00"
  },
  "runtimes": [
    {
      "runtime_id": "<runtime_id_worker_1>",
      "deployment_id": "<deployment_id>",
      "model_id": "<model_id>",
      "version_id": "<version_id>",
      "framework": "sklearn",
      "status": "running",
      "worker_id": "<worker_id_1>",
      "applied_generation": 2,
      "loaded_at": "2026-10-08T02:05:01+00:00",
      "unloaded_at": null,
      "last_heartbeat_at": "2026-10-08T02:05:20+00:00",
      "error": null,
      "context": null
    },
    {
      "runtime_id": "<runtime_id_worker_2>",
      "deployment_id": "<deployment_id>",
      "model_id": "<model_id>",
      "version_id": "<version_id>",
      "framework": "sklearn",
      "status": "running",
      "worker_id": "<worker_id_2>",
      "applied_generation": 2,
      "loaded_at": "2026-10-08T02:05:02+00:00",
      "unloaded_at": null,
      "last_heartbeat_at": "2026-10-08T02:05:20+00:00",
      "error": null,
      "context": null
    }
  ],
  "local": {
    "deployment_id": "<deployment_id>",
    "worker_id": "<worker_id_1>",
    "loaded_in_memory": true,
    "memory": {
      "deployment_id": "<deployment_id>",
      "model_id": "<model_id>",
      "version_id": "<version_id>",
      "framework": "sklearn",
      "metadata": {
        "runtime_id": "<runtime_id_worker_1>",
        "worker_id": "<worker_id_1>",
        "bento_tag": "<bento_tag>",
        "model_path": "<model_path>",
        "model_key": "model",
        "model_type": "logistic_regression",
        "task_type": "scoring",
        "environment": "production",
        "rollout_type": "full",
        "role": "champion",
        "threshold": 0.5
      },
      "loaded_at": "2026-10-08T02:05:01+00:00",
      "last_used_at": null,
      "access_count": 0
    },
    "runtime": {
      "runtime_id": "<runtime_id_worker_1>",
      "deployment_id": "<deployment_id>",
      "model_id": "<model_id>",
      "version_id": "<version_id>",
      "framework": "sklearn",
      "status": "running",
      "worker_id": "<worker_id_1>",
      "loaded_at": "2026-10-08T02:05:01+00:00",
      "unloaded_at": null,
      "last_heartbeat_at": "2026-10-08T02:05:20+00:00",
      "error": null,
      "context": null
    }
  },
  "local_generation": 2
}
```

`control` 是共享期望状态，`runtimes` 是数据库记录的各运行实例状态。`runtimes[*].applied_generation` 保留每个运行实例实际应用的控制代次；协调尚未完成时可以为 `null`，不能用 `control.generation` 推断或填充。

`local` 描述目标部署在本次 HTTP 请求命中的预测服务 Worker 中的本地状态。`local_generation` 也只表示该 Worker 已应用的目标部署控制代次，不能代表其他 Worker，更不能作为全部 Worker 已完成重载的汇总结果。

判断本次变更完成时，先确定预期参与该部署的 Worker。每个预期 Worker 都必须有对应运行实例，心跳有效，`status` 为 `running`，`applied_generation` 与 `control.generation` 一致，并且 `error` 为 `null`；全部满足后，再执行一次真实预测并核对结果。当前没有全局“重载完成”接口。停用部署后仍可调用 `/admin/status`，用于确认各运行实例已停止。

如需查看本次请求命中的预测服务 Worker 已加载的全部服务，可调用：

```bash
curl -sS http://127.0.0.1:8700/admin/services \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

该响应没有 `success` 包装，直接返回 `worker_id`、`environment`、`runtime_count`、`service_cache_count`、`applied_generations`、`runtimes` 和 `services`。

## 错误处理

进入业务处理后，错误响应通常包含追踪请求 ID：

```json
{
  "success": false,
  "error": "没有可用部署: model_id=<model_id>, environment=production",
  "error_type": "RuntimeRouteError",
  "request_id": "<request_id>"
}
```

输入模型校验发生在业务方法调用前，其错误结构由 BentoML/Pydantic 生成，可能不包含上述业务字段。认证接口和 Bearer 认证错误也使用各自的响应结构。客户端应以 HTTP 状态码作为首要分类，再记录完整响应体。

| HTTP 状态 | 代表性原因 | 处理方向 |
| --- | --- | --- |
| 400 | 请求字段、模型名、路由或普通业务参数非法 | 检查请求字段、模型、规则和部署可用性 |
| 401 | 缺少、过期或无效的认证凭据 | 重新登录或刷新令牌 |
| 403 | 当前身份缺少接口要求的权限 | 为角色授予精确权限 |
| 404 | 部署或批次不存在 | 检查 ID 和服务环境 |
| 409 | 部署环境、部署状态或批次状态冲突 | 遵循资源生命周期后重试 |
| 503 | Broker 投递失败、服务未就绪，或预发布/生产环境未启用认证 | 检查 Redis、数据库、认证配置和相关进程 |
| 504 | 预测超过服务超时预算 | 检查模型耗时和服务超时配置 |
| 500 | 未映射的服务异常 | 保留追踪 ID 并检查服务日志 |

错误类型与 HTTP 状态的精确映射可能随接口处理阶段不同。自动化客户端不要根据错误文案分支，应根据状态码和 `error_type` 处理。
