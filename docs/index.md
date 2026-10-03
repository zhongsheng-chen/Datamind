# Datamind

Datamind 是一个 Python 模型服务管理平台。它将训练好的模型发布为可调用的服务，让模型版本、发布流量、预测执行和操作记录在同一处管理。

## 模型服务

训练得到模型文件后，注册制品并激活版本，创建部署，再通过路由接入请求。预测服务负责加载与执行，控制台用于观察运行状态、调用结果和审计记录。

```text
训练 → 注册 → 部署 → 路由 → 预测 → 观测
```

模型（`Model`）保存名称与任务类型，版本（`Version`）指向制品（`Artifact`）。部署（`Deployment`）将版本发布到指定环境，路由（`Routing`）选择请求目标，运行实例（`Runtime`）记录节点的实际执行状态。

这条链路帮助团队保留版本历史、逐步发布候选模型，并追踪每次预测使用的版本。分类任务返回类别与概率，评分任务还提供信用分与特征评分，业务系统可以据此处理自身决策流程。

## 快速入门

先[安装 Datamind](getting-started/installation.md)，再跟随[快速上手](getting-started/quickstart.md)完成评分卡示例的注册、发布和调用。已有容器环境时，可从 [Docker 部署](deployment/docker.md)开始。

安装包名为 `pydatamind`，Python 导入名和命令行入口均为 `datamind`。

## 常用功能

- 发布候选版本：[金丝雀发布](deployment/canary.md)逐步接入流量，[影子预测](deployment/shadow.md)旁路验证新模型。
- 比较业务表现：[A/B 测试](experiments/index.md)分配请求，回流结果后分析差异。
- 处理多条输入：[批量预测](guides/batch-prediction.md)提交异步任务并查询结果。
- 管理与观测：[管理控制台](guides/console.md)查看模型、部署、调用与审计。

理解资源关系时阅读[核心概念](concepts/resources.md)，查询命令或字段时使用 [参考手册](cli/index.md)。
