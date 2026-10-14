# 请求字段

本文介绍预测服务请求对象的字段及约束。HTTP 路径、认证、响应与错误处理见[预测 API](runtime-api.md)，调用示例见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

## 约定

- 请求对象仅接受已声明的字段。
- 可选字段省略时使用默认值。
- 字符串字段会去除首尾空白，请求载荷中 `features` 对象的字符串值除外。

## ControlRequest

运行控制请求。

适用接口：`POST /admin/reload`。

| 字段            | 类型     | 必需 | 默认值 | 约束        | 说明                  |
|-----------------|----------|------|--------|-------------|-----------------------|
| `deployment_id` | `string` | 是   | `—`    | minLength=1 | 要重新加载的部署 ID。 |

使用说明：

- 部署必须存在、属于当前预测服务的运行环境，且状态为 `active`。运行控制记录必须存在，且 `desired_status` 为 `loaded`。
- 重载请求受理后，各预测服务 Worker 异步重新加载模型。可通过 `/admin/status` 查看实际加载状态。

请求载荷示例：

```json
{
  "request": {
    "deployment_id": "<deployment_id>"
  }
}
```

## DeploymentRequest

部署查询请求。

适用接口：`POST /admin/status`。

| 字段            | 类型     | 必需 | 默认值 | 约束        | 说明                      |
|-----------------|----------|------|--------|-------------|---------------------------|
| `deployment_id` | `string` | 是   | `—`    | minLength=1 | 要查询运行状态的部署 ID。 |

使用说明：

- 部署必须存在，并且属于当前预测服务的运行环境；启用和停用的部署均可查询。
- 响应同时包含共享控制状态、各运行实例状态和当前预测服务 Worker 的本地状态。

请求载荷示例：

```json
{
  "request": {
    "deployment_id": "<deployment_id>"
  }
}
```

## PredictRequest

单条预测请求。

适用接口：`POST /predict`。

| 字段            | 类型             | 必需 | 默认值 | 约束                       | 说明                                            |
|-----------------|------------------|------|--------|----------------------------|-------------------------------------------------|
| `model_name`    | `string`         | 是   | `—`    | maxLength=100, minLength=1 | 已注册的模型名称。                              |
| `features`      | `object`         | 是   | `—`    | minProperties=1            | 本次预测的输入特征。                            |
| `deployment_id` | `string \| null` | 否   | `null` | —                          | 显式指定的部署 ID；省略时由路由选择部署。       |
| `subject_key`   | `string \| null` | 否   | `null` | —                          | 用于实验分组和路由匹配的稳定业务主体标识。      |
| `subject_type`  | `string \| null` | 否   | `null` | —                          | 用于路由条件匹配的业务主体类型，例如 customer。 |

使用说明：

- `model_name` 必须对应已注册的模型。请求载荷中 `features` 对象的字段名和值类型须符合目标模型的输入要求。
- 参与实验时，应提供稳定的 `subject_key`，以保持同一业务主体的分组一致。
- 指定 `deployment_id` 时，直接使用该部署，跳过实验分配和普通路由。目标部署须属于请求模型和当前运行环境、状态为 `active` 且在生效时间内，并且不能是影子部署。

请求载荷示例：

```json
{
  "request": {
    "model_name": "<model_name>",
    "features": {
      "<feature_name>": "<value>"
    },
    "subject_key": "borrower-001",
    "subject_type": "borrower"
  }
}
```

## PredictionInstance

批量预测中的单条预测实例。

适用接口：作为 `BatchPredictRequest.instances` 的元素，不直接提交到独立路径。

| 字段           | 类型             | 必需 | 默认值 | 约束            | 说明                                                  |
|----------------|------------------|------|--------|-----------------|-------------------------------------------------------|
| `features`     | `object`         | 是   | `—`    | minProperties=1 | 该实例的输入特征。                                    |
| `subject_key`  | `string \| null` | 否   | `null` | —               | 该实例用于实验分组和路由匹配的稳定业务主体标识。      |
| `subject_type` | `string \| null` | 否   | `null` | —               | 该实例用于路由条件匹配的业务主体类型，例如 customer。 |

使用说明：

- 每个实例分别提供目标模型要求的 `features` 和可选主体信息；模型名称和显式部署由外层批量请求统一指定。
- 未指定 `deployment_id` 时，各实例分别选择部署；指定时，全部实例使用该部署。实验场景应为每个业务主体提供稳定且可区分的 `subject_key`。

在批量请求中的使用示例：

```json
{
  "request": {
    "model_name": "<model_name>",
    "instances": [
      {
        "features": {
          "<feature_name>": "<value>"
        },
        "subject_key": "borrower-001",
        "subject_type": "borrower"
      }
    ]
  }
}
```

## BatchPredictRequest

批量预测请求。

适用接口：`POST /predict/batch`。

| 字段            | 类型                        | 必需 | 默认值 | 约束                       | 说明                                          |
|-----------------|-----------------------------|------|--------|----------------------------|-----------------------------------------------|
| `model_name`    | `string`                    | 是   | `—`    | maxLength=100, minLength=1 | 已注册的模型名称。                            |
| `instances`     | `array[PredictionInstance]` | 是   | `—`    | minItems=1                 | 需要预测的实例列表。                          |
| `deployment_id` | `string \| null`            | 否   | `null` | —                          | 批次内所有实例共用的部署 ID；省略时逐条路由。 |

使用说明：

- 批次内所有实例共用 `model_name` 和可选的 `deployment_id`，但各自保留特征和主体信息。
- 提交成功仅表示批次已排队，预测由任务 Worker 异步执行；部署选择和模型输入校验在执行时完成。
- 单条实例失败不会撤销已经成功的实例，最终状态可能为 `partially_succeeded`。

请求载荷示例：

```json
{
  "request": {
    "model_name": "<model_name>",
    "instances": [
      {
        "features": {
          "<feature_name>": "<value>"
        },
        "subject_key": "borrower-001",
        "subject_type": "borrower"
      },
      {
        "features": {
          "<feature_name>": "<value>"
        },
        "subject_key": "borrower-002",
        "subject_type": "borrower"
      }
    ]
  }
}
```

## BatchReferenceRequest

批次引用请求。

适用接口：`POST /predict/batch/status`、`POST /predict/batch/cancel`、`POST /predict/batch/retry`。

| 字段       | 类型     | 必需 | 默认值 | 约束                      | 说明                        |
|------------|----------|------|--------|---------------------------|-----------------------------|
| `batch_id` | `string` | 是   | `—`    | maxLength=64, minLength=1 | 批量预测提交返回的批次 ID。 |

使用说明：

- `batch_id` 必须使用批量提交响应返回的值；状态查询返回持久化的进度、计数以及可用的结果或错误。
- 取消适用于 `queued`、`retrying` 或 `running`，并可对 `cancelling`、`cancelled` 重复调用；重试只适用于 `partially_succeeded`、`failed` 或 `cancelled`。

请求载荷示例：

```json
{
  "request": {
    "batch_id": "<batch_id>"
  }
}
```
