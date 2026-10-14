# 批量预测

批量预测通过 `POST /predict/batch` 提交多条输入，由任务 Worker 异步执行。提交成功后，使用返回的 `batch_id` 查询执行进度和预测结果。

## 前置条件

提交批次前，请完成以下准备：

- 按[模型训练示例](../examples/index.md)准备模型，激活模型版本并启用部署，确认模型已成功加载。
- 配置 Redis，并启动角色为 `batch` 或 `all` 的[任务 Worker](../deployment/worker.md)。
- 启用认证时，获取访问令牌，并确认当前账户具备 `prediction.invoke` 权限。

首次使用见[快速上手](../getting-started/quickstart.md)，令牌获取方式见[预测 API](../reference/runtime-api.md#认证)。

## 提交批次

以[快速上手](../getting-started/quickstart.md)中的 `scorecard-demo` 为例，将 `<access_token>` 替换为实际访问令牌：

```bash
curl -sS http://127.0.0.1:8700/predict/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "request": {
      "model_name": "scorecard-demo",
      "instances": [
        {
          "subject_key": "borrower-002",
          "subject_type": "borrower",
          "features": {
            "age": 35,
            "annual_income": 120000,
            "debt_to_income_ratio": 0.3,
            "credit_utilization_ratio": 0.4,
            "delinquency_count": 0,
            "credit_history_years": 8,
            "employment_type": "salaried",
            "residence_status": "mortgage"
          }
        },
        {
          "subject_key": "borrower-003",
          "subject_type": "borrower",
          "features": {
            "age": 42,
            "annual_income": 90000,
            "debt_to_income_ratio": 0.4,
            "credit_utilization_ratio": 0.5,
            "delinquency_count": 1,
            "credit_history_years": 8,
            "employment_type": "salaried",
            "residence_status": "mortgage"
          }
        }
      ]
    }
  }'
```

提交成功返回 HTTP 202，响应示例如下：

```json
{
  "success": true,
  "batch_id": "<batch_id>",
  "status": "queued",
  "submitted_count": 2,
  "status_url": "/predict/batch/status"
}
```

该响应仅表示批次已排队，可通过 `batch_id` 查询预测结果、取消批次或发起重试。

## 查询结果

使用提交时返回的 `batch_id` 查询批次状态和预测结果：

```bash
curl -sS http://127.0.0.1:8700/predict/batch/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

批次执行成功后，接口返回的响应如下：

```json
{
  "success": true,
  "batch_id": "<batch_id>",
  "status": "succeeded",
  "total_count": 2,
  "completed_count": 2,
  "succeeded_count": 2,
  "failed_count": 0,
  "attempt_count": 1,
  "result": {
    "success": true,
    "count": 2,
    "succeeded_count": 2,
    "failed_count": 0,
    "predictions": [
      {
        "success": true,
        "task_type": "scoring",
        "request_id": "<request_id_1>"
      },
      {
        "success": true,
        "task_type": "scoring",
        "request_id": "<request_id_2>"
      }
    ],
    "batch_id": "<batch_id>"
  }
}
```

通过响应中的 `status` 查看执行进度。批次结束后，该字段为以下状态之一：

| 状态                  | 含义                   |
|-----------------------|------------------------|
| `succeeded`           | 全部实例预测成功       |
| `partially_succeeded` | 部分实例预测成功       |
| `failed`              | 批次执行或任务投递失败 |
| `cancelled`           | 批次已取消             |

查询响应中的 `result.predictions` 包含各输入实例的预测结果和错误信息；结果尚未生成时，响应不包含 `result`。也可在管理控制台的**批量任务**中查看批次和执行记录。

## 选择部署

通过 `deployment_id` 可显式指定批次内所有实例使用的部署；未指定时，系统按实验分配、普通路由和默认部署的顺序，为每条实例选择目标。具体规则见[流量分配与决策优先级](../routing/index.md)。

## 取消与重试

取消批次：

```bash
curl -sS http://127.0.0.1:8700/predict/batch/cancel \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

重试批次：

```bash
curl -sS http://127.0.0.1:8700/predict/batch/retry \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

取消和重试的行为取决于批次状态：

| 当前状态                        | 取消                                    | 重试     |
|---------------------------------|-----------------------------------------|----------|
| `queued`、`retrying`            | 转为 `cancelled`                        | 不允许   |
| `running`                       | 转为 `cancelling`，等待 Worker 协作停止 | 不允许   |
| `cancelling`                    | 保持当前状态                            | 不允许   |
| `cancelled`                     | 保持当前状态                            | 重新排队 |
| `partially_succeeded`、`failed` | 不允许                                  | 重新排队 |
| `succeeded`                     | 不允许                                  | 不允许   |

- **取消**：不会强制中断正在执行的模型计算，需继续查询以确认取消完成。已成功的结果会保留。
- **重试**：沿用原 `batch_id`，仅处理尚未成功的实例。重试成功返回 HTTP 202，后续仍需查询执行结果。

> **提示**
>
> `TaskDispatchError` 表示任务发布失败，应检查 Redis 连接和任务发布日志。若批次长期停留在 `queued`，则检查 Worker 是否运行、角色与队列配置是否匹配。详细步骤见[生产部署](../deployment/production.md#常见故障排查)。
