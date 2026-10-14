# 请求字段

本文介绍预测服务请求对象的字段及约束。HTTP 路径、认证、响应与错误处理见[预测 API](runtime-api.md)，调用示例见[在线预测](../guides/online-prediction.md)和[批量预测](../guides/batch-prediction.md)。

## 约定

- 请求对象仅接受已声明的字段。
- 可选字段省略时使用默认值。
- 字符串字段会去除首尾空白，请求载荷中 `features` 对象的字符串值除外。

${models}