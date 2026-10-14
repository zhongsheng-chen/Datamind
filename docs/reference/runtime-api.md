# 预测 API

本文介绍预测 API 的认证方式、接口权限、请求响应及错误处理。请求字段和约束见[请求字段](runtime-schemas.md)，调用示例见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

## 约定

- 本页接口均使用 `POST`，包括 `/health` 和 `/ready`。
- 认证接口直接接收请求字段；预测和运行控制接口使用外层 `request` 对象。
- `/admin/services`、`/health` 和 `/ready` 发送空 JSON 对象 `{}`，无需 `request` 包装。
- 启用认证后，受保护接口需携带 `Authorization: Bearer <access_token>`，并具备对应权限。
- 时间采用带时区的 ISO 8601 格式，ID 和令牌均视为不透明字符串。
- 对于包含 `success` 的响应，客户端应同时检查 HTTP 状态码和 `success`。HTTP 202 仅表示批量任务已排队。

## 认证

### 获取令牌

使用用户名和密码获取访问令牌：

```bash
curl -sS http://127.0.0.1:8700/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"<password>"}'
```

认证成功后，接口返回：

```json
{
  "access_token": "<access_token>",
  "refresh_token": "<refresh_token>",
  "token_type": "bearer",
  "expires_in": 1800
}
```

`expires_in` 表示访问令牌的有效期，单位为秒。

### 刷新令牌

使用刷新令牌获取新的访问令牌：

```bash
curl -sS http://127.0.0.1:8700/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

> **提示**
>
> 刷新操作会轮换刷新令牌，请保存响应中的新令牌，用于后续刷新和退出登录。应急账户可能不签发 `refresh_token`。

### 退出登录

提交当前刷新令牌退出登录：

```bash
curl -i http://127.0.0.1:8700/auth/logout \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh_token>"}'
```

成功返回 HTTP 204，响应体为空。

> **注意**
>
> 在 `development` 和 `testing` 环境中关闭认证时，受保护接口以系统身份执行，无需 Bearer 令牌。`staging` 和 `production` 环境必须启用认证，否则受保护接口返回 HTTP 503。

## 接口与权限

| 路径                    | 输入                                                              | 权限                | 返回                                         |
|-------------------------|-------------------------------------------------------------------|---------------------|----------------------------------------------|
| `/auth/login`           | `username`、`password`                                            | 无需访问令牌        | 访问令牌                                     |
| `/auth/refresh`         | `refresh_token`                                                   | 无需访问令牌        | 新的访问令牌和刷新令牌                       |
| `/auth/logout`          | `refresh_token`                                                   | 无需访问令牌        | HTTP 204，无响应体                           |
| `/predict`              | [PredictRequest](runtime-schemas.md#predictrequest)               | `prediction.invoke` | 主预测结果和 `request_id`                    |
| `/predict/batch`        | [BatchPredictRequest](runtime-schemas.md#batchpredictrequest)     | `prediction.invoke` | HTTP 202、`batch_id` 和排队状态              |
| `/predict/batch/status` | [BatchReferenceRequest](runtime-schemas.md#batchreferencerequest) | `prediction.invoke` | 批次状态、执行统计及可用结果                 |
| `/predict/batch/cancel` | [BatchReferenceRequest](runtime-schemas.md#batchreferencerequest) | `prediction.invoke` | 取消请求后的批次状态                         |
| `/predict/batch/retry`  | [BatchReferenceRequest](runtime-schemas.md#batchreferencerequest) | `prediction.invoke` | HTTP 202、重新排队后的状态                   |
| `/admin/reload`         | [ControlRequest](runtime-schemas.md#controlrequest)               | `runtime.manage`    | 重载请求受理结果和控制状态                   |
| `/admin/status`         | [DeploymentRequest](runtime-schemas.md#deploymentrequest)         | `runtime.read`      | 控制状态、各运行实例及当前 Worker 的本地状态 |
| `/admin/services`       | 空 JSON 对象 `{}`                                                 | `runtime.read`      | 当前预测服务 Worker 已加载的服务信息         |
| `/health`               | 空 JSON 对象 `{}`                                                 | 无需认证            | 健康状态及当前 Worker 信息                   |
| `/ready`                | 空 JSON 对象 `{}`                                                 | 无需认证            | 就绪状态及检查结果                           |

## 健康与就绪探针

`/health` 检查当前预测服务 Worker 是否正常响应；`/ready` 进一步检查数据库连接和协调循环。两者均使用 `POST`：

检查健康状态：

```bash
curl -fsS -X POST http://127.0.0.1:8700/health \
  -H "Content-Type: application/json" \
  -d '{}'
```

检查就绪状态：

```bash
curl -fsS -X POST http://127.0.0.1:8700/ready \
  -H "Content-Type: application/json" \
  -d '{}'
```

服务就绪时，响应示例如下：

```json
{
  "status": "ready",
  "database_ready": true,
  "reconciler_running": true,
  "worker_id": "<worker_id>",
  "environment": "production"
}
```

数据库连接异常或协调循环未运行时，`/ready` 返回 HTTP 503，`status` 为 `not_ready`。就绪检查不验证模型加载状态，仍需查看运行实例状态并发起预测请求，以确认模型可用。

## 单条预测

通过 `POST /predict` 发起单条预测，请求字段及载荷示例请参阅[PredictRequest](runtime-schemas.md#predictrequest)。

成功响应包含以下公共字段：

| 字段         | 类型    | 说明                                      |
|--------------|---------|-------------------------------------------|
| `success`    | boolean | 本次预测是否成功                          |
| `task_type`  | string  | 任务类型：`classification` 或 `scoring`   |
| `request_id` | string  | 预测请求 ID，用于关联请求、决策和执行记录 |

除公共字段外，响应还包含对应任务的预测结果。

**分类任务**

| 字段          | 类型    | 说明                                      |
|---------------|---------|-------------------------------------------|
| `prediction`  | integer | 根据分类阈值确定的类别，取值为 `0` 或 `1` |
| `label`       | string  | 与预测类别对应的标签，由模型配置定义      |
| `probability` | number  | 正类概率                                  |
| `threshold`   | number  | 分类阈值                                  |

**评分任务**

| 字段                       | 类型         | 说明                                        |
|----------------------------|--------------|---------------------------------------------|
| `score`                    | number       | 评分结果                                    |
| `probability`              | number       | 正类概率，具体业务含义由模型定义            |
| `decision`                 | string       | 评分达到阈值时为 `approve`，否则为 `reject` |
| `threshold`                | number       | 评分阈值                                    |
| `score_intercept`          | number       | 评分截距                                    |
| `features`                 | object       | 以特征名为键的逐特征评分明细                |
| `features.<特征名>.value`  | 任意 JSON 值 | 输入特征值                                  |
| `features.<特征名>.bin`    | string       | 特征所属分箱                                |
| `features.<特征名>.woe`    | number       | 模型使用的 WoE 值                           |
| `features.<特征名>.points` | number       | 该特征对应的评分                            |

请求与响应示例请参阅[评分与分类](../guides/scoring-and-classification.md)，失败响应请参阅[错误处理](#错误处理)。

## 批量预测

### 提交批次

通过 `POST /predict/batch` 提交批次，请求字段及载荷示例请参阅[BatchPredictRequest](runtime-schemas.md#batchpredictrequest)。

提交成功返回 HTTP 202，响应包含以下字段：

| 字段              | 类型    | 说明                          |
|-------------------|---------|-------------------------------|
| `success`         | boolean | 批次是否提交成功              |
| `batch_id`        | string  | 批次 ID，用于查询、取消和重试 |
| `status`          | string  | 提交成功时为 `queued`         |
| `submitted_count` | integer | 提交的实例数                  |
| `status_url`      | string  | 批次查询接口路径              |

响应示例：

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

通过 `POST /predict/batch/status` 查询批次，请求字段及载荷示例请参阅[BatchReferenceRequest](runtime-schemas.md#batchreferencerequest)。

**响应字段**

| 字段              | 类型           | 说明                                         |
|-------------------|----------------|----------------------------------------------|
| `success`         | boolean        | 本次查询是否成功，不代表批次中的预测全部成功 |
| `batch_id`        | string         | 批次 ID                                      |
| `status`          | string         | 当前批次状态，见下表                         |
| `total_count`     | integer        | 实例总数                                     |
| `completed_count` | integer        | 已完成的实例数                               |
| `succeeded_count` | integer        | 预测成功的实例数                             |
| `failed_count`    | integer        | 预测失败的实例数                             |
| `attempt_count`   | integer        | 执行尝试次数                                 |
| `created_at`      | string         | 批次创建时间                                 |
| `started_at`      | string 或 null | 本次执行开始时间，尚未开始时为 `null`        |
| `finished_at`     | string 或 null | 本次执行结束时间，尚未结束时为 `null`        |
| `error`           | string         | 批次错误信息，仅在存在错误时返回             |
| `result`          | object         | 批次预测结果，仅在结果已生成时返回           |

**批次状态**

| `status`              | 含义                   |
|-----------------------|------------------------|
| `queued`              | 等待执行               |
| `running`             | 执行中                 |
| `retrying`            | 等待自动重试           |
| `cancelling`          | 等待取消完成           |
| `succeeded`           | 全部实例预测成功       |
| `partially_succeeded` | 部分实例预测成功       |
| `failed`              | 批次执行或任务投递失败 |
| `cancelled`           | 批次已取消             |

**预测结果**

结果生成后，响应通过 `result` 对象返回以下字段：

| 字段              | 类型    | 说明                                                                                    |
|-------------------|---------|-----------------------------------------------------------------------------------------|
| `success`         | boolean | 结果中的实例是否全部预测成功                                                            |
| `task_type`       | string  | 任务类型，存在时返回                                                                    |
| `count`           | integer | 结果中的实例数                                                                          |
| `succeeded_count` | integer | 结果中预测成功的实例数                                                                  |
| `failed_count`    | integer | 结果中预测失败的实例数                                                                  |
| `predictions`     | array   | 逐条预测结果；成功项结构见[单条预测](#单条预测)，失败项包含 `success: false` 和错误信息 |
| `batch_id`        | string  | 批次 ID                                                                                 |

批次执行成功后，接口返回的响应示例如下：

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

### 取消与重试

取消批次使用 `POST /predict/batch/cancel`，重试批次使用 `POST /predict/batch/retry`。两个接口的请求字段及载荷示例请参阅[BatchReferenceRequest](runtime-schemas.md#batchreferencerequest)。

取消成功返回 HTTP 200，重试成功返回 HTTP 202，响应结构均与[查询批次](#查询批次)一致。各状态下的操作结果如下：

| 操作     | 可接受状态                                   | 结果                                        |
|----------|----------------------------------------------|---------------------------------------------|
| 取消     | `queued`、`retrying`                         | 直接进入 `cancelled`                        |
| 取消     | `running`                                    | 进入 `cancelling`，等待任务 Worker 协作停止 |
| 重复取消 | `cancelling`、`cancelled`                    | 保持当前状态                                |
| 重试     | `partially_succeeded`、`failed`、`cancelled` | 使用原 `batch_id` 重新排队                  |

当前状态不允许取消或重试时，返回 HTTP 409。重试保留已成功实例的结果，仅处理尚未成功的实例。

## 运行控制

运行控制接口用于重新加载部署、查询运行状态和已加载服务。

### 重新加载部署

通过 `POST /admin/reload` 请求重新加载部署，请求字段及载荷示例请参阅[ControlRequest](runtime-schemas.md#controlrequest)。目标部署须属于当前预测服务的运行环境，处于 `active` 状态，且运行控制的 `desired_status` 为 `loaded`。

```bash
curl -sS http://127.0.0.1:8700/admin/reload \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"deployment_id":"<deployment_id>"}}'
```

请求受理后，`control.generation` 递增，各预测服务 Worker 异步重新加载模型。成功响应如下：

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

### 查询运行状态

通过 `POST /admin/status` 查询部署的运行状态，请求字段及载荷示例请参阅[DeploymentRequest](runtime-schemas.md#deploymentrequest)。

| 字段                             | 类型            | 说明                                                  |
|----------------------------------|-----------------|-------------------------------------------------------|
| `success`                        | boolean         | 本次查询是否成功                                      |
| `request_id`                     | string          | 本次查询的请求 ID                                     |
| `deployment_id`                  | string          | 部署 ID                                               |
| `environment`                    | string          | 预测服务的运行环境                                    |
| `control`                        | object 或 null  | 共享的期望运行状态，无控制记录时为 `null`             |
| `control.generation`             | integer         | 当前控制代次                                          |
| `runtimes`                       | array           | 数据库记录的各预测服务 Worker 的运行实例状态          |
| `runtimes[*].applied_generation` | integer 或 null | 对应运行实例已应用的控制代次，尚未应用时可能为 `null` |
| `local`                          | object          | 本次请求命中的 Worker 的本地运行状态                  |
| `local_generation`               | integer 或 null | 本次请求命中的 Worker 已应用的控制代次                |

查询示例：

```bash
curl -sS http://127.0.0.1:8700/admin/status \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"request":{"deployment_id":"<deployment_id>"}}'
```

查询成功后，接口返回的响应示例如下：

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
        "threshold": 600.0
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

运行实例满足以下条件时，表示已完成当前代次的模型加载：

- `status` 为 `running`。
- `error` 为 `null`。
- `applied_generation` 与 `control.generation` 一致。

### 查询已加载服务

通过 `POST /admin/services` 查询当前预测服务 Worker 已加载的服务。

```bash
curl -sS http://127.0.0.1:8700/admin/services \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{}'
```

响应包含以下字段：

| 字段                  | 类型    | 说明                                 |
|-----------------------|---------|--------------------------------------|
| `worker_id`           | string  | Worker ID                            |
| `environment`         | string  | 运行环境                             |
| `runtime_count`       | integer | 已注册的运行实例数                   |
| `service_cache_count` | integer | 缓存的服务数                         |
| `applied_generations` | object  | 已应用的部署控制代次，以部署 ID 为键 |
| `runtimes`            | array   | 运行实例快照                         |
| `services`            | array   | 已缓存的服务信息                     |

## 错误处理

错误响应示例如下：

```json
{
  "success": false,
  "error": "没有可用部署: model_id=<model_id>, environment=production",
  "error_type": "RuntimeRouteError",
  "request_id": "<request_id>"
}
```

参数校验和认证失败时，响应结构可能与上述示例不同。客户端应先检查 HTTP 状态码，再读取响应中的错误信息。

| HTTP 状态 | 常见原因                                                 | 处理建议                                   |
|-----------|----------------------------------------------------------|--------------------------------------------|
| 400       | 请求字段、模型名、路由或普通业务参数非法                 | 检查请求字段、模型、规则和部署可用性       |
| 401       | 缺少、过期或无效的认证凭据                               | 重新登录或刷新令牌                         |
| 403       | 当前身份缺少接口要求的权限                               | 为角色授予精确权限                         |
| 404       | 部署或批次不存在                                         | 检查 ID 和服务环境                         |
| 409       | 部署环境、部署状态或批次状态冲突                         | 检查当前环境和资源状态，满足操作条件后重试 |
| 503       | Broker 投递失败、服务未就绪，或预发布/生产环境未启用认证 | 检查 Redis、数据库、认证配置和相关进程     |
| 504       | 预测超过服务超时预算                                     | 检查模型耗时和服务超时配置                 |
| 500       | 未映射的服务异常                                         | 保留追踪 ID 并检查服务日志                 |

自动化处理应依据 HTTP 状态码和 `error_type`，避免依赖错误消息文本。
