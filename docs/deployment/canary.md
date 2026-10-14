# 金丝雀发布

金丝雀发布先将少量预测流量分配给候选版本，其余流量仍由主版本处理。验证通过后，逐步扩大候选版本的流量比例，直至完成版本切换，以降低新版本上线的风险。

## 前置条件

开始发布前，请完成以下准备：

- 按[模型训练示例](../examples/index.md#评分卡示例)准备主版本和候选版本，再参照[快速上手](../getting-started/quickstart.md)分别完成部署。
- 确认主版本和候选版本均能正常预测。
- 确认当前账户具备 `model.write`、`deployment.write`、`routing.read`、`routing.write`、`runtime.read`、`prediction.invoke` 和 `request.read` [权限](../reference/states-permissions.md#权限全集)。

## 创建部署

为 `scorecard-demo` 的主版本 `1.0.0` 和候选版本 `1.1.0` 分别创建金丝雀部署：

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout canary --role champion
datamind deployment create scorecard-demo --version 1.1.0 --rollout canary --role challenger
```

命令中的参数说明：

- `--rollout`：发布方式，`canary` 表示金丝雀发布。
- `--role`：部署角色，主部署使用 `champion`，候选部署使用 `challenger`。

启用部署：

```bash
datamind deployment enable <champion_deployment_id>
datamind deployment enable <challenger_deployment_id>
```

其中，两个部署 ID 别表示：

- `<champion_deployment_id>`：主部署的 ID。
- `<challenger_deployment_id>`：候选部署的 ID。

部署 ID 可通过以下命令查询：

```bash
datamind deployment list
```

检查运行实例的状态：

```bash
datamind runtime list
```

确认两个部署的运行实例均为 `running` 后，将主部署设为默认部署：

```bash
datamind deployment set-default <champion_deployment_id>
```

未被路由分配的流量由默认部署处理，详见[默认部署](../routing/index.md#默认部署)。

## 配置路由

为主部署和候选部署分别创建并启用主路由和候选路由，流量比例分别设为 80% 和 20%：

```bash
datamind route create <champion_deployment_id> \
  --name scorecard-demo-canary-champion \
  --traffic-ratio 0.8 \
  --enabled

datamind route create <challenger_deployment_id> \
  --name scorecard-demo-canary-challenger \
  --traffic-ratio 0.2 \
  --enabled
```

> **注意**
>
> 创建前，请禁用同一模型在同一环境中的已有全量路由，避免流量比例之和超过 100%。

## 验证发布结果

参照[在线预测](../guides/online-prediction.md)或[批量预测](../guides/batch-prediction.md)发起请求，再通过[管理控制台](../guides/console.md#api-调用与执行记录)查看请求与执行记录。

按以下步骤核对：

1. 使用请求 ID（`request_id`）查询关联的执行记录。批量预测需等待批次完成后，按每条实例的请求 ID 分别查询。
2. 核对主预测（`primary`）执行记录的部署、版本和状态，确认由主版本或候选版本处理，且执行成功。
3. 检查主版本与候选版本的预测结果，确认符合预期，并观察两个版本的流量分配情况。

> **注意**
>
> 验证路由是否生效时，请勿指定 `deployment_id`，并先暂停或结束相关实验，避免请求由显式指定的部署或实验分组处理。
>
> 分流以主体为单位，请使用不同的 `subject_key` 验证。路由配置不变时，同一主体的分配保持不变。详见[流量分配](../routing/index.md)。

## 调整流量比例

将候选路由的流量比例从 20% 提高到 50%，先降低主路由的比例，再提高候选路由的比例：

```bash
datamind route update <champion_routing_id> --traffic-ratio 0.5
datamind route update <challenger_routing_id> --traffic-ratio 0.5
```

其中，`<champion_routing_id>` 和 `<challenger_routing_id>` 分别为主路由和候选路由的 ID，可通过以下命令查询：

```bash
datamind route list --name scorecard-demo-canary-champion
datamind route list --name scorecard-demo-canary-challenger
```

每次调整后，请验证分流情况和预测结果，再决定是否继续提高候选路由的流量比例。

> **注意**
>
> 已启用路由的流量比例之和不能超过 100%。调整时，应先降低主路由的比例，再提高候选路由的比例。调整期间，未分配的流量由默认部署处理。
>
> 调整比例会改变路由区间，同一主体可能被分配到其他部署。

## 版本切换

候选版本验证通过后，将候选路由的流量比例提高到 100%：

```bash
datamind route update <champion_routing_id> --traffic-ratio 0
datamind route update <challenger_routing_id> --traffic-ratio 1
```

此时，全部普通路由流量由候选部署处理，但默认部署仍为主部署。

随后，按以下步骤完成版本切换：

1. 为候选版本创建新的全量部署并启用。
2. 等待新部署的运行实例状态为 `running`，指定其 `deployment_id` 发起预测，验证预测结果。
3. 为新部署创建流量比例为 100% 的路由，暂不启用。
4. 将新部署设为默认部署，禁用两条金丝雀路由，再启用新路由。
5. 确认版本切换生效后，停用原主部署和候选部署，并等待模型卸载完成。

保留旧版本及其模型文件，以便回滚。

## 回滚

金丝雀发布期间，将流量恢复到主版本：

```bash
datamind route disable <challenger_routing_id>
datamind route update <champion_routing_id> --traffic-ratio 1
```

验证请求已恢复使用主版本后，再停用候选部署。

若已完成版本切换，按以下步骤恢复原主版本：

1. 重新启用原主部署，等待运行实例状态为 `running`，指定其 `deployment_id` 发起预测，验证预测结果。
2. 将原主路由的流量比例设为 100%，暂不启用，并保持候选路由禁用。
3. 将原主部署设为默认部署，禁用新路由，再启用原主路由。
4. 验证请求已恢复使用原主版本后，停用新部署，并等待模型卸载完成。

## 异常处理

- **流量比例更新被拒绝**：检查同一模型在同一环境中的普通路由，先降低已启用路由的流量比例或禁用路由，再提高其他路由的比例。
- **候选版本预测失败**：禁用候选路由，将流量恢复到主版本，并检查候选部署的运行实例、模型文件和框架依赖。

## 使用注意事项

运行中的实验优先于普通路由，因此验证金丝雀分流前，请先暂停或结束相关实验。发起预测请求时，请勿指定 `deployment_id`，以确保请求按普通路由分流。

如需记录主体分组并比较各组表现，请参阅[实验流程](../experiments/index.md)。影子预测独立执行，不参与普通路由的流量分配，请参阅[影子发布](shadow.md)。
