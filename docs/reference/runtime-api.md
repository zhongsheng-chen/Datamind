# 预测 API

预测服务（`Runtime`）默认监听 `http://127.0.0.1:8700`。认证启用时，受保护接口必须发送 `Authorization: Bearer <access_token>`。请求字段与约束见[请求字段表](runtime-schemas.md)，预测操作见[在线](../guides/online-prediction.md)与[批量指南](../guides/batch-prediction.md)。

## 接口与权限

除探针外，下面的业务接口均使用 POST。BentoML 方法的输入放在外层 `request` 中，认证接口使用直接 JSON 对象。

| 路径 | 输入 | 权限 | 返回内容 |
| --- | --- | --- | --- |
| `/auth/login` | `username`、`password` | 本地账户认证 | `access_token`、`refresh_token`、`token_type`、`expires_in` |
| `/auth/refresh` | `refresh_token` | 有效刷新凭据 | 轮换后的令牌 |
| `/auth/logout` | `refresh_token` | 刷新凭据校验 | 退出与撤销结果 |
| `/predict` | `PredictRequest` | `prediction.invoke` | 主预测结果与 `request_id` |
| `/predict/batch` | `BatchPredictRequest` | `prediction.invoke` | HTTP 202，`batch_id`、`status`、`submitted_count`、`status_url` |
| `/predict/batch/status` | `BatchReferenceRequest` | `prediction.invoke` | 批次状态、计数、结果 |
| `/predict/batch/cancel` | `BatchReferenceRequest` | `prediction.invoke` | 取消后的批次状态 |
| `/predict/batch/retry` | `BatchReferenceRequest` | `prediction.invoke` | HTTP 202，重新排队后的状态 |
| `/feedback/outcomes` | `OutcomeFeedbackRequest` | `outcome.write` | 业务结果（`Outcome`）与是否新建 |
| `/admin/load` | `ControlRequest` | `runtime.manage` | 部署加载控制结果 |
| `/admin/unload` | `ControlRequest` | `runtime.manage` | 部署卸载控制结果 |
| `/admin/reload` | `ControlRequest` | `runtime.manage` | 新一代加载目标 |
| `/admin/status` | DeploymentRequest | runtime.read | control、runtimes、local、local_generation |
| `/admin/services` | 无参数 | runtime.read | 当前服务运行信息 |
| `/health` | 无参数 | 无资源权限 | 进程健康信息 |
| `/ready` | 无参数 | 无资源权限 | 数据库等就绪检查，失败 HTTP 503 |

探针可用 GET 请求。`/ready` 成功不等于所有部署均已加载。模型交付还要检查运行实例记录并执行预测。

## 请求示例

```bash
curl -X POST http://127.0.0.1:8700/admin/status \
  -H 'Authorization: Bearer <access_token>' \
  -H 'Content-Type: application/json' \
  -d '{"request":{"deployment_id":"<deployment_id>"}}'
```

单条预测必须提供非空 `model_name` 和 `features`。`deployment_id` 可指定主目标，但不能指向影子部署。`subject_key` 用于稳定分桶和关联业务结果。批量请求使用 `instances`，每条实例有独立 `features` 和可选主体。

业务结果必须有 `outcome_id`、`subject_key`，且 `decision_id`、`request_id` 至少提供一个。二者同时提供时必须指向同一决策。API 不接受客户端自行指定 `experiment_id` 或 `variant_id`，归属从原始决策读取。

## 响应与追踪

预测响应包含 `success`、`request_id` 及任务结果。分类结果包含预测类别与概率，评分结果包含概率、评分、决策、阈值及特征评分信息，具体示例见[分类与评分](../guides/models.md)。影子结果异步写入执行记录，不替代返回给调用方的主结果。

批次查询包含 `batch_id`、`status`、`total_count`、`completed_count`、`succeeded_count`、`failed_count`、`attempt_count`、`created_at`、`started_at`、`finished_at`。产生后再包含 `result` 或 `error`。部分成功需要检查逐实例结果，不能仅凭 HTTP 200 判断全部成功。终态和取消重试边界见[批量指南](../guides/batch-prediction.md)。

## 错误

| HTTP 状态 | 当前错误或原因 | 处理 |
| --- | --- | --- |
| 400 | RuntimeRouteError、TypeError、ValueError | 检查输入、模型名、规则与部署可用性 |
| 401 / 403 | 认证失败 / 权限不足 | 重新认证或补足对应权限 |
| 404 | ServiceDeploymentNotFoundError、BatchNotFoundError | 检查 ID 与资源是否存在 |
| 409 | ServiceEnvironmentMismatchError、InvalidDeploymentStateError、BatchStateError | 修正环境或遵循状态转换 |
| 503 | TaskDispatchError、就绪失败 | 检查 Broker、数据库和进程 |
| 504 | RequestTimeoutError | 检查模型耗时与服务超时 |
| 500 | 未在映射表中声明的业务异常 | 保留 `request_id`，核对服务日志 |

Pydantic/BentoML 输入校验发生在方法调用前，HTTP 错误与业务 `success=false` 响应应分别处理。错误对象通常含 `success=false`、`error`、`error_type`。客户端应同时检查 HTTP 状态与响应内容。
