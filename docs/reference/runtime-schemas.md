# Runtime 请求字段

本页从当前 Pydantic 请求模型生成。HTTP 外层封装、响应与错误见 [Runtime API](runtime-api.md)。所有模型拒绝未知字段并去除字符串首尾空白。

## ControlRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `deployment_id` | `string` | 是 | `—` | minLength=1 |

## DeploymentRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `deployment_id` | `string` | 是 | `—` | minLength=1 |

## PredictRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | `—` | maxLength=100, minLength=1 |
| `features` | `object` | 是 | `—` | minProperties=1 |
| `deployment_id` | `string \| null` | 否 | `null` |  |
| `subject_key` | `string \| null` | 否 | `null` |  |
| `subject_type` | `string \| null` | 否 | `null` |  |

## PredictionInstance

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `features` | `object` | 是 | `—` | minProperties=1 |
| `subject_key` | `string \| null` | 否 | `null` |  |
| `subject_type` | `string \| null` | 否 | `null` |  |

## BatchPredictRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `model_name` | `string` | 是 | `—` | maxLength=100, minLength=1 |
| `instances` | `array[PredictionInstance]` | 是 | `—` | minItems=1 |
| `deployment_id` | `string \| null` | 否 | `null` |  |

## BatchReferenceRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `batch_id` | `string` | 是 | `—` | maxLength=64, minLength=1 |

## OutcomeFeedbackRequest

| 字段 | 类型 | 必需 | 默认值 | 约束 |
| --- | --- | --- | --- | --- |
| `outcome_id` | `string` | 是 | `—` | maxLength=64, minLength=1 |
| `subject_key` | `string` | 是 | `—` | maxLength=128, minLength=1 |
| `decision_id` | `string \| null` | 否 | `null` |  |
| `request_id` | `string \| null` | 否 | `null` |  |
| `subject_type` | `string \| null` | 否 | `null` |  |
| `approved` | `boolean \| null` | 否 | `null` |  |
| `converted` | `boolean \| null` | 否 | `null` |  |
| `defaulted` | `boolean \| null` | 否 | `null` |  |
| `overdue_days` | `integer \| null` | 否 | `null` | minimum=0 |
| `amount` | `number \| null` | 否 | `null` | minimum=0 |
| `label` | `string \| null` | 否 | `null` |  |
| `context` | `object \| null` | 否 | `null` |  |
| `outcome_time` | `string (date-time) \| null` | 否 | `null` |  |
