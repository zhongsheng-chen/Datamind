# 批量预测

批量预测由 Runtime 接收请求、通过 Broker 发布任务，再由 batch Worker 执行。提交成功后仍需查询批次结果。

## 准备

部署[申请评分模型](models.md)，配置 Redis Broker，并启动[任务 Worker](../deployment/processes.md)。Runtime 与 Worker 应共享数据库、存储和环境配置。

## 提交

使用已获取的 HTTP 访问令牌：

```bash
curl -sS http://127.0.0.1:8700/predict/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "request": {
      "model_name": "application-scorecard",
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

响应包含 `batch_id`、`status=queued` 和 `submitted_count`，此时不能判断预测已经全部成功。

## 查询结果

复制 `batch_id`，替换以下占位符：

```bash
curl -sS http://127.0.0.1:8700/predict/batch/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"request":{"batch_id":"<batch_id>"}}'
```

成功完成时状态为 `succeeded`，响应包含完成数、成功数、失败数和 `result.predictions`。也可进入 Console“批量任务”，查看批次和任务执行记录。

每条实例传入[评分卡的八个特征](models.md)。欺诈风险分类示例使用 `model_name=fraud-risk`，传入五个交易特征，不能复用评分卡的信贷输入。

## 较大批次

`instances` 支持多条输入。保留同一模型对应的特征 Schema，为每条实例生成不同的 `subject_key`，即可提交 50、100 或 200 条实例。每次提交得到独立 `batch_id`，应逐批查询完成数、失败数与预测结果，不要将 HTTP 提交成功当作执行完成。

例如生成 200 条申请评分实例，再提交生成的 JSON 文件：

```bash
python - <<'PYTHON'
import json
from pathlib import Path

batch_size = 200  # 可改为 50 或 100
features = {
    "age": 35,
    "annual_income": 120000,
    "debt_to_income_ratio": 0.3,
    "credit_utilization_ratio": 0.4,
    "delinquency_count": 0,
    "credit_history_years": 8,
    "employment_type": "salaried",
    "residence_status": "mortgage",
}
request = {
    "model_name": "application-scorecard",
    "instances": [
        {"features": features, "subject_key": f"borrower-batch-{i:03}",
         "subject_type": "borrower"}
        for i in range(batch_size)
    ],
}
Path("batch-request.json").write_text(json.dumps({"request": request}))
PYTHON

curl -sS http://127.0.0.1:8700/predict/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  --data-binary @batch-request.json
```

提交后仍按上文用返回的 `batch_id` 查询。重复实验时请按实际借款人或演示轮次设置主体标识，避免把不同对象误用为同一主体。

## 实验与影子任务

每条实例的主体信息参与路由或实验分流。配置影子路由后，还会产生独立的影子执行记录。主批次结果与影子记录分别核对。

本次六个模型各完成两条基础批量实例，申请评分另完成十二条实验批量实例。还为每个模型分别提交 50、100、200 条实例，共十八个较大批次、2,100 条实例；最终状态与统计见[Console 手册](console.md)。

## 取消与重试

两个接口均使用 POST、Bearer 认证和 `{"request":{"batch_id":"<batch_id>"}}`，要求 prediction.invoke。

| 当前状态 | cancel | retry |
| --- | --- | --- |
| queued / retrying | 直接转 cancelled | 不允许手动重试 |
| running | 转 cancelling，由执行器协作停止 | 不允许 |
| cancelling / cancelled | 重复取消保持当前状态 | 仅 cancelled 可重试 |
| partially_succeeded / failed | 不允许取消 | 可重新排队 |
| succeeded | 不允许 | 不允许 |

取消不是强杀已经开始的模型计算，必须继续查询到 cancelled。已成功实例保留；手动重试创建新的任务和 Attempt，只重试未成功实例，batch_id 保持不变，成功计数作为已有进度保留。attempt_count 用于追踪尝试次数。自动队列重试使用 retrying 状态，与客户端手动 retry 是不同过程。

查询 result 时逐条检查实例结果和错误。partially_succeeded 表示部分实例失败，需要定位特征、部署或运行错误；failed 也可能是投递失败。遇到 TaskDispatchError 检查 Redis、队列名和 Worker 角色后再重试。状态错误返回 HTTP 409，不存在的批次返回 404；成功提交和重试返回 202。完整字段见[Runtime API](../reference/runtime-api.md)。
