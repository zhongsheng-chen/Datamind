# 请求字段

本页是预测服务请求对象的字段参考。HTTP 路径、认证、响应与错误见[预测 API](runtime-api.md)，完整调用流程见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

除认证接口外，HTTP 请求将这里展示的对象放在外层 `request` 字段中，例如 `{"request":{"deployment_id":"<deployment_id>"}}`。`PredictionInstance` 只作为批量请求的嵌套元素。示例中的 `<model_name>`、`<deployment_id>`、`<batch_id>`、`<request_id>`、`<feature_name>` 和 `<value>` 均为占位符，调用前必须替换。

请求只接受下表声明的字段，字符串会去除首尾空白。表中约束由 Pydantic 在进入业务处理前校验；“业务条件”由路由、运行控制在后续阶段校验。可选字段省略时使用表中默认值。

${models}