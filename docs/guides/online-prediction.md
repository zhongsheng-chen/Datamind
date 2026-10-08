# 在线预测

通过 `POST /predict` 调用已部署模型。输入特征由训练模型定义，输出结构由分类或评分任务决定。

## 前置条件

目标版本已激活，部署已启用并完成加载。首次发布流程见[快速上手](../getting-started/quickstart.md)，已有服务的版本发布见[全量发布](../deployment/full.md)。

启用认证时，调用方需要 HTTP 访问令牌及 `prediction.invoke` 权限。令牌获取方式见[预测 API](../reference/runtime-api.md)；CLI 登录凭据与 HTTP 访问令牌分别管理。

## 发起请求

以下示例调用快速上手中的 `scorecard-demo`。替换 `<access_token>`，并按实际部署地址调整主机和端口：

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
        "age": 35,
        "annual_income": 120000,
        "debt_to_income_ratio": 0.3,
        "credit_utilization_ratio": 0.4,
        "delinquency_count": 0,
        "credit_history_years": 8,
        "employment_type": "salaried",
        "residence_status": "mortgage"
      }
    }
  }'
```

`model_name` 选择模型，`features` 必须符合该模型的特征要求。使用其他模型时，应同时替换模型名称和输入特征。分类输入示例见[评分与分类](scoring-and-classification.md)。

## 选择部署与主体

默认由平台选择主部署。验证候选版本时，可在 `request` 中增加 `deployment_id`，请求将直接使用该部署，并校验模型、环境、状态与生效时间。

参与实验时，使用稳定的 `subject_key` 标识业务主体，`subject_type` 说明主体类型。同一主体可以复用实验分配，但每次调用仍会产生新的预测记录。主体解析与分配规则见[实验分流](../experiments/assignment.md)。

## 处理响应

检查 HTTP 状态码和响应中的 `success`。成功响应返回 `request_id`，评分任务还返回概率、总评分、阈值决策和特征评分。完整响应结构见[预测 API](../reference/runtime-api.md)。

保存 `request_id`，在管理控制台中关联查看请求、决策、主执行和影子执行。

## 处理失败

| 情况 | 处理方式 |
| --- | --- |
| 输入校验失败 | 核对字段名、值类型与注册后的特征结构 |
| 没有可用部署 | 检查当前环境中的部署状态与生效时间 |
| 模型加载失败 | 检查运行实例、框架依赖与文件访问 |
| HTTP 401 或 403 | 检查令牌、用户状态及调用权限 |
| HTTP 504 | 检查模型耗时与服务的 `timeout` 配置 |

保留响应中的 `error_type`、`request_id` 和调用时间，用于定位日志。在线接口没有请求幂等键；超时或网络中断后，调用方应结合业务语义决定是否重试。运行故障排查见[生产部署](../deployment/production.md)。
