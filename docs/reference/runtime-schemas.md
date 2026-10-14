# 请求字段

本页是预测服务请求对象的字段参考。HTTP 路径、认证、响应与错误见[预测 API](runtime-api.md)，完整调用流程见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

除认证接口外，HTTP 请求将这里展示的对象放在外层 `request` 字段中，例如 `{"request":{"deployment_id":"<deployment_id>"}}`。`PredictionInstance` 只作为批量请求的嵌套元素。示例中的 `<model_name>`、`<deployment_id>`、`<batch_id>`、`<request_id>`、`<feature_name>` 和 `<value>` 均为占位符，调用前必须替换。

请求只接受下表声明的字段，字符串会去除首尾空白。表中约束由 Pydantic 在进入业务处理前校验；“业务条件”由路由、运行控制在后续阶段校验。可选字段省略时使用表中默认值。

## ControlRequest

运行控制请求。

适用接口：`POST /admin/reload`。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `deployment_id` | `string` | 是 | `—` | minLength=1 | 要重新加载的部署 ID。 |

业务条件：

- 部署必须存在，属于当前预测服务配置的运行环境，并且处于 `active` 状态。
- 重载请求会递增共享控制状态的 `generation`，由各运行实例协调并重新加载部署；受理后应通过 `/admin/status` 检查实际状态。

请求对象示例（不含外层 `request`）：

```json
{
  "deployment_id": "<deployment_id>"
}
```

## DeploymentRequest

部署查询请求。

适用接口：`POST /admin/status`。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `deployment_id` | `string` | 是 | `—` | minLength=1 | 要查询运行状态的部署 ID。 |

业务条件：

- 部署必须存在，并且属于当前预测服务配置的运行环境；启用和停用的部署均可查询。
- 响应同时包含共享控制状态、各运行实例状态和当前预测服务 Worker 的本地状态。

请求对象示例（不含外层 `request`）：

```json
{
  "deployment_id": "<deployment_id>"
}
```

## PredictRequest

单条预测请求。

适用接口：`POST /predict`。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | `—` | maxLength=100, minLength=1 | 已注册的模型名称。 |
| `features` | `object` | 是 | `—` | minProperties=1 | 本次预测的输入特征。 |
| `deployment_id` | `string \| null` | 否 | `null` | — | 显式指定的部署 ID；省略时由路由选择部署。 |
| `subject_key` | `string \| null` | 否 | `null` | — | 用于实验分组和路由匹配的稳定业务主体标识。 |
| `subject_type` | `string \| null` | 否 | `null` | — | 用于路由条件匹配的业务主体类型，例如 customer。 |

业务条件：

- `model_name` 必须对应已注册模型；`features` 的字段名和值类型由目标模型定义，请求模型本身只校验映射非空。
- 实验场景应提供稳定的 `subject_key`，使同一主体复用已有分组或获得稳定分桶。
- 提供 `deployment_id` 时绕过实验和普通路由；该部署仍须属于请求模型和当前环境、处于可路由状态及生效时间内，且不能是影子部署。

请求对象示例（不含外层 `request`）：

```json
{
  "model_name": "<model_name>",
  "features": {
    "<feature_name>": "<value>"
  },
  "subject_key": "borrower-001",
  "subject_type": "borrower"
}
```

## PredictionInstance

批量预测中的单条预测实例。

适用接口：作为 `BatchPredictRequest.instances` 的元素，不直接提交到独立路径。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `features` | `object` | 是 | `—` | minProperties=1 | 该实例的输入特征。 |
| `subject_key` | `string \| null` | 否 | `null` | — | 该实例用于实验分组和路由匹配的稳定业务主体标识。 |
| `subject_type` | `string \| null` | 否 | `null` | — | 该实例用于路由条件匹配的业务主体类型，例如 customer。 |

业务条件：

- 每个实例分别提供目标模型要求的 `features` 和可选主体信息；模型名称和显式部署由外层批量请求统一指定。
- 批量任务逐条路由；实验场景应为每个业务主体提供稳定且可区分的 `subject_key`。

实例结构示例：

```json
{
  "features": {
    "<feature_name>": "<value>"
  },
  "subject_key": "borrower-001",
  "subject_type": "borrower"
}
```

## BatchPredictRequest

批量预测请求。

适用接口：`POST /predict/batch`。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | `—` | maxLength=100, minLength=1 | 已注册的模型名称。 |
| `instances` | `array[PredictionInstance]` | 是 | `—` | minItems=1 | 需要预测的实例列表。 |
| `deployment_id` | `string \| null` | 否 | `null` | — | 批次内所有实例共用的部署 ID；省略时逐条路由。 |

业务条件：

- 批次内所有实例共用 `model_name` 和可选的 `deployment_id`，但各自保留特征和主体信息。
- 提交时先校验模型名称并持久化批次，再通过 Broker 投递任务；成功响应只表示已排队，实际预测由任务 Worker 异步执行。
- 单条实例失败不会撤销已经成功的实例，最终状态可能为 `partially_succeeded`。

请求对象示例（不含外层 `request`）：

```json
{
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
```

## BatchReferenceRequest

批次引用请求。

适用接口：`POST /predict/batch/status`、`POST /predict/batch/cancel`、`POST /predict/batch/retry`。

| 字段 | 类型 | 必需 | 默认值 | 约束 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `batch_id` | `string` | 是 | `—` | maxLength=64, minLength=1 | 批量预测提交返回的批次 ID。 |

业务条件：

- `batch_id` 必须使用批量提交响应返回的值；状态查询返回持久化的进度、计数以及可用的结果或错误。
- 取消适用于 `queued`、`retrying` 或 `running`，并可对 `cancelling`、`cancelled` 重复调用；重试只适用于 `partially_succeeded`、`failed` 或 `cancelled`。

请求对象示例（不含外层 `request`）：

```json
{
  "batch_id": "<batch_id>"
}
```
