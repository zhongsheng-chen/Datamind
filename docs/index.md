# Datamind

Datamind 将训练好的 Python 模型发布为预测服务，统一管理模型版本、部署、流量与调用记录。支持分类和评分任务，提供 CLI 与管理控制台。

## 从第一个模型开始

[快速上手](getting-started/quickstart.md)以申请评分模型为例，带你完成训练、注册、发布和首次预测。开始前，请先[安装](getting-started/installation.md)并[配置数据库与管理员](getting-started/configuration.md)。

安装包名为 `pydatamind`，Python 导入名和命令行入口均为 `datamind`。

## 发布与评估

| 要做什么 | 阅读内容 |
| --- | --- |
| 管理模型与制品 | [模型与版本](models/index.md)、[兼容性](models/compatibility.md) |
| 发布新版本 | [全量发布](deployment/full.md)、[金丝雀发布](deployment/canary.md)、[影子发布](deployment/shadow.md) |
| 分配请求流量 | [路由](routing/index.md)、[规则与生效时间](routing/rules.md) |
| 比较模型效果 | [A/B 测试](experiments/index.md)、[结果回流](experiments/outcomes.md)、[实验分析](experiments/analysis.md) |
| 接入业务系统 | [在线预测](guides/online-prediction.md)、[批量预测](guides/batch-prediction.md) |
| 使用管理界面 | [Console 操作手册](guides/console.md)、[用户与权限](guides/access-control.md) |

## 部署与开发

[架构](concepts/architecture.md)介绍管理服务与预测服务如何协作。[生产部署](deployment/production.md)说明基础设施、多实例运行和运维步骤，从源码开发则从[开发环境](development/index.md)开始。

查阅命令、配置和接口时，使用 [CLI Reference](cli/index.md)、[配置参考](reference/configuration.md)和 [Runtime API](reference/runtime-api.md)。
