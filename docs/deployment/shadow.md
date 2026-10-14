# 影子发布

影子发布将全部或部分预测请求复制给候选版本，异步执行影子预测，用于比较主版本与候选版本的预测结果。预测请求仍返回主预测结果，影子预测结果仅记录供比较和分析，不作为请求响应返回。

## 前置条件

开始发布前，请完成以下准备：

- 按[模型训练示例](../examples/index.md#评分卡示例)准备主版本和候选版本，再参照[快速上手](../getting-started/quickstart.md)分别完成部署。
- 确认主版本和候选版本均能正常预测。
- 参照[本地部署](local.md)配置 Redis Broker，并启动任务 Worker。
- 确认当前账户具备 `model.write`、`deployment.write`、`routing.read`、`routing.write`、`runtime.read`、`prediction.invoke` 和 `request.read` [权限](../reference/states-permissions.md#权限全集)。

## 创建部署

为 `scorecard-demo` 的候选版本 `1.1.0` 创建影子部署：

```bash
datamind deployment create scorecard-demo --version 1.1.0 --rollout shadow
```

命令中的参数说明：

- `--rollout`：发布方式，`shadow` 表示影子发布。部署角色自动设为 `shadow`。

启用部署：

```bash
datamind deployment enable <deployment_id>
```

其中，`<deployment_id>` 为部署的 ID，可通过以下命令查询：

```bash
datamind deployment list
```

检查运行实例的状态：

```bash
datamind runtime list
```

确认影子部署的运行实例状态为 `running` 后，再配置影子路由。

## 配置路由

为影子部署创建影子路由，将流量比例设为 100%，并启用：

```bash
datamind route create <deployment_id> \
  --name scorecard-demo-shadow \
  --traffic-ratio 1 \
  --enabled
```

影子路由独立采样，不参与普通路由的流量分配。

## 验证发布结果

参照[在线预测](../guides/online-prediction.md)或[批量预测](../guides/batch-prediction.md)发起请求，再通过[管理控制台](../guides/console.md#api-调用与执行记录)查看请求与执行记录。

按以下步骤核对：

1. 使用请求 ID（`request_id`）查询关联的执行记录。批量预测需等待批次完成后，按每条实例的请求 ID 分别查询。
2. 核对主预测（`primary`）与影子预测（`shadow`）执行记录的部署、版本和状态，确认分别由主版本和候选版本处理，且执行成功。
3. 检查主版本与候选版本的预测结果，确认符合预期，并比较概率、评分、决策和执行耗时。

> **注意**
>
> 影子预测异步执行。主请求返回或批次完成时，影子执行可能仍处于 `queued` 或 `running` 状态，等待执行成功后再比较结果。影子预测失败或超时不会覆盖主预测结果。

## 停止与下线

禁用影子路由，停止为后续请求创建影子执行：

```bash
datamind route disable <routing_id>
```

其中，`<routing_id>` 为影子路由的 ID，可通过以下命令查询：

```bash
datamind route list --name scorecard-demo-shadow
```

禁用路由不会取消已入队或正在运行的影子任务。下线时，按以下顺序操作：

1. 等待已有影子任务完成。
2. 删除影子路由，再停用影子部署。
3. 等待运行实例完成模型卸载后，删除部署。

历史执行记录仍可查询。删除操作须满足关联限制，详见[状态与权限](../reference/states-permissions.md)。

## 异常处理

- **没有影子执行记录**：检查影子部署和路由是否已启用、是否处于生效时间内，以及请求是否满足路由条件。确认 `DATAMIND_RUNTIME_SHADOW_ENABLED` 为 `true`，且主预测成功。
- **影子执行一直等待**：检查任务 Worker 是否在线、是否消费影子队列，以及与预测服务的 Broker 和队列配置是否一致。
- **影子任务投递失败**：执行记录中的 `ShadowQueueRejected` 表示任务未成功进入队列。检查 Broker 和预测服务日志；此类失败不会进入 Worker 的执行重试流程。
- **影子预测失败或超时**：检查执行记录中的错误、模型文件、框架依赖和任务 Worker 日志。Worker 执行异常会按[任务队列配置](../reference/environment-variables.md#任务队列)中的 `max_retries` 和 `retry_backoff_seconds` 重试；重试期间，执行记录会恢复为 `queued`。系统未提供手动重试影子预测的公开接口。

## 使用注意事项

影子部署不能绑定实验分组，也不能作为显式主预测目标或默认部署。候选版本通过影子路由参与预测，请求仍返回主预测结果。

在线请求由预测服务解析影子路由，批量实例由任务 Worker 解析。两类进程应使用一致的[运行时配置](../reference/environment-variables.md#运行管理)：

- `DATAMIND_RUNTIME_SHADOW_ENABLED`：控制是否解析影子路由。
- `DATAMIND_RUNTIME_SHADOW_TIMEOUT`：控制单次影子预测的超时时间。

候选版本验证通过后，可参照[全量发布](full.md#版本切换)或[金丝雀发布](canary.md)将其用于主预测。
