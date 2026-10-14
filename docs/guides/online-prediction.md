# 在线预测

在线预测通过 `POST /predict` 调用已部署模型。输入特征须与模型训练时一致，输出结构由分类或评分任务决定。

## 前置条件

发起预测前，请完成以下准备：

- 按[模型训练示例](../examples/index.md)准备模型，激活模型版本并启用部署，确认模型已成功加载。
- 启用认证时，获取访问令牌，并确认当前账户具备 `prediction.invoke` 权限。

首次使用见[快速上手](../getting-started/quickstart.md)，令牌获取方式见[预测 API](../reference/runtime-api.md#认证)。

## 发起请求

以[快速上手](../getting-started/quickstart.md)中的 `scorecard-demo` 为例，将 `<access_token>` 替换为实际访问令牌：

```bash
curl -sS http://127.0.0.1:8700/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "request": {
      "model_name": "scorecard-demo",
      "subject_key": "borrower-001",
      "subject_type": "borrower",
      "features": {
        "age": 45,
        "annual_income": 240000,
        "debt_to_income_ratio": 0.1,
        "credit_utilization_ratio": 0.1,
        "delinquency_count": 0,
        "credit_history_years": 20,
        "employment_type": "salaried",
        "residence_status": "owner"
      }
    }
  }'
```

如需调用分类模型，请参阅[评分与分类](scoring-and-classification.md#使用分类模型)。

> **提示**
>
> 输入特征按名称匹配，请求载荷中 `features` 对象的字段顺序不影响预测结果。

## 选择部署

通过 `deployment_id` 可显式指定部署；未指定时，系统按实验分配、普通路由和默认部署的顺序选择目标。具体规则见[流量分配与决策优先级](../routing/index.md)。

## 处理响应

请求成功后，接口返回的响应示例如下：

```json
{
  "success": true,
  "task_type": "scoring",
  "score": 680.17,
  "probability": 0.013,
  "decision": "approve",
  "threshold": 600.0,
  "request_id": "<request_id>"
}
```

可通过 `request_id` 在管理控制台查看关联的请求、决策和执行记录，完整响应结构见[预测 API](../reference/runtime-api.md)。

## 请求失败

| 情况            | 处理方式                                                               |
|-----------------|------------------------------------------------------------------------|
| 输入校验失败    | 检查字段名称、数据类型是否符合模型要求                                 |
| 没有可用部署    | 检查部署状态、环境及生效时间；未匹配到路由时，确认已设置可用的默认部署 |
| 模型加载失败    | 检查运行实例、框架依赖与文件访问                                       |
| HTTP 401 或 403 | 检查令牌、用户状态及调用权限                                           |
| HTTP 504        | 检查模型耗时与 `DATAMIND_SERVICE_TIMEOUT` 配置                         |

排查时，保留调用时间及响应中的 `error_type` 和 `request_id`。详细步骤见[生产部署](../deployment/production.md#常见故障排查)。

> **提示**
>
> 超时或网络中断不代表预测未执行。接口不支持幂等去重，重试可能产生新的预测记录，请根据业务需要决定是否重试。
