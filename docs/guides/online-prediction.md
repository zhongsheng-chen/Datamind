# 在线预测

在线预测通过 Runtime 的 `POST /predict` 调用已经部署的模型。

## 请求准备

提供 `model_name` 和非空 `features`。实验场景还需提供稳定的 `subject_key`。可选 `subject_type` 表达主体类型。显式提供 `deployment_id` 会进入指定部署校验路径。

启用认证时，HTTP 请求需要 Bearer 访问令牌。CLI 登录凭据不会自动附加到 curl 或其他客户端。

## 调用与结果

第一个完整请求见[快速上手](../getting-started/quickstart.md)。响应中的 `request_id` 用于追踪请求，并可作为[Outcome 回流](../experiments/outcomes.md)的关联信息。

## 排查路径

先核对认证与权限，再检查模型版本、Deployment、Routing 和 Runtime 状态。错误对象包含 success=false、error 和 error_type，HTTP 状态映射见[Runtime API](../reference/runtime-api.md)。客户端同时检查 HTTP 状态和业务 success，保留 request_id 用于定位。

输入校验失败先修正 features 与注册 Schema。无可用部署先核对环境、状态与生效时间。部署加载失败检查框架依赖和存储。504 表示超时，需要检查模型计算和服务 timeout_seconds。在线接口没有请求幂等键，盲目重试可能新增预测与决策记录。重试应由上游按业务语义和请求追踪设计。

同一个 subject_key 保持实验分组稳定，但不使预测调用幂等。显式 deployment_id 可用于候选版本验证，仍要求模型与部署匹配，并绕过实验和普通路由选择。分类和评分完整特征示例见[模型指南](models.md)。
