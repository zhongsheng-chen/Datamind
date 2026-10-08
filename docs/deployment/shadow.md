# 影子发布

影子发布使用 `rollout_type=shadow`，角色自动为 `shadow`。候选部署使用主请求的输入执行影子预测，客户端仍获得主部署的预测结果。

## 准备候选版本与任务 Worker

先完成[快速上手](../getting-started/quickstart.md)，再按[模型训练示例](../examples/index.md#评分卡示例)生成候选模型文件，按[金丝雀教程的准备步骤](canary.md#准备主版本和候选版本)注册并激活 `scorecard-demo` 的 `1.1.0` 版本，无需创建金丝雀部署或实验。

配置 Redis Broker，并启动消费 `shadow` 队列的[任务 Worker](processes.md)。默认 `all` 角色同时消费 `batch` 和 `shadow` 队列。

## 创建与启用

```bash
datamind deployment create scorecard-demo --version 1.1.0 --rollout shadow
```

复制部署（`Deployment`） ID，替换 `<shadow_deployment_id>`：

```bash
datamind deployment enable <shadow_deployment_id>
datamind route create <shadow_deployment_id> \
  --name scorecard-demo-shadow --traffic-ratio 1 --enabled
```

本例影子比例为 1，使符合路由条件的请求都产生影子执行。影子比例不消耗主路由流量预算。

## 验证执行

发起[在线](../guides/online-prediction.md)或[批量](../guides/batch-prediction.md)预测。在 Console“执行记录”区分 `primary` 与 `shadow`，核对部署、版本和成功状态。主预测与影子预测各有独立执行记录。

按请求查看主结果与影子结果的示例见[管理控制台](../guides/console.md)。

## 比较与故障处理

按 `request_id` 对齐 `primary` 与 `shadow` 执行，比较概率、评分、决策及耗时，确认两个版本使用相同输入 Schema。影子失败或超时保留独立执行状态，不覆盖主预测结果。排查执行记录、任务 Worker、模型文件加载与 Broker 日志。Celery 对可重试失败按队列的 `max_retries` 与 `retry_backoff_seconds` 配置重试。不存在用于任意影子执行的公开重试接口。

影子部署不能绑定实验分组，也不能作为显式主预测目标。预测服务的 `DATAMIND_RUNTIME_SHADOW_ENABLED` 和 `DATAMIND_RUNTIME_SHADOW_TIMEOUT` 见[环境变量](../reference/environment-variables.md)。需要停止影子预测时，禁用影子路由。下线部署前确认队列中已有任务和运行状态。历史执行仍可查询。
