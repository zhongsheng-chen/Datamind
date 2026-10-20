# 全量发布

全量发布将全部预测流量一次性切换至新版本。切换完成后，所有预测请求均由新版本处理，并返回新版本的预测结果。全量发布适合首次上线或直接切换模型版本。

## 前置条件

开始发布前，请完成以下准备：

- 参照[快速上手](../getting-started/quickstart.md)训练、注册并激活评分卡示例模型，并启动预测服务。
- 确认当前账户具备 `model.write`、`deployment.read`、`deployment.write`、`routing.write`、`runtime.read`、`prediction.invoke` 和 `request.read` [权限](../reference/states-permissions.md#权限全集)。

## 首次发布

创建全量部署：

```bash
datamind deployment create scorecard-demo --version 1.0.0 --rollout full
```

命令中的参数说明：

- `--rollout`：发布方式，`full` 表示全量发布。部署角色自动设为 `champion`。

启用部署：

```bash
datamind deployment enable <deployment_id>
```

其中，`<deployment_id>` 为部署的 ID，可通过以下命令查询：

```bash
datamind deployment list
```

创建匹配所有请求的路由，将流量比例设为 100%，并启用。全量路由的流量比例必须为 100%：

```bash
datamind route create <deployment_id> \
  --name scorecard-demo-main \
  --traffic-ratio 1 \
  --enabled
```

检查运行实例的状态：

```bash
datamind runtime list
```

确认该部署的运行实例状态为 `running` 后，将其设为默认部署：

```bash
datamind deployment set-default <deployment_id>
```

更多关于默认部署的说明，请参阅[默认部署](../routing/index.md#默认部署)。

## 验证发布结果

参照[在线预测](../guides/online-prediction.md)或[批量预测](../guides/batch-prediction.md)发起请求，再通过[管理控制台](../guides/console.md#调用与执行)查看请求与执行记录。

按以下步骤核对：

1. 使用请求 ID（`request_id`）查询关联的执行记录。批量预测需等待批次完成后，按每条实例的请求 ID 分别查询。
2. 核对主预测（`primary`）执行记录的部署、版本和状态，确认由本次发布的版本处理，且执行成功。
3. 检查本次发布版本的预测结果，确认符合预期。

> **注意**
>
> 验证路由是否生效时，请勿指定 `deployment_id`，并先暂停或结束相关实验，避免请求由显式指定的部署或实验分组处理。

## 版本切换

注册并激活新版本后，按以下步骤完成版本切换：

1. 为新版本创建新的全量部署并启用。
2. 等待新部署的运行实例状态为 `running`，指定其 `deployment_id` 发起预测，验证预测结果。
3. 为新部署创建流量比例为 100% 的路由，暂不启用。
4. 将新部署设为默认部署，禁用旧路由，再启用新路由。
5. 发起未指定 `deployment_id` 的请求，确认版本切换生效后，停用旧部署，并等待模型卸载完成。

保留旧版本及其模型文件，以便回滚。

> **注意**
>
> 启用新部署不会自动切换流量。请先将其设为默认部署，再禁用旧路由、启用新路由，确保切换期间的请求由新部署处理。
>
> 同一模型在同一环境中只能启用一条全量路由，否则总流量比例会超过 100%。

## 回滚

保留旧版本及其模型文件，以便恢复旧版本：

1. 确认旧部署已启用、运行实例状态为 `running`。若已停用，重新启用并等待加载完成。
2. 指定旧部署的 `deployment_id` 发起预测，验证结果。
3. 使用 `datamind deployment set-default <old_deployment_id>` 恢复旧默认部署，再禁用新主路由、启用旧主路由。
4. 发起未指定 `deployment_id` 的请求，确认使用旧版本，再停用新部署。

路由回滚不会改写历史请求或实验结果。

## 下线

1. 禁用并删除关联路由。
2. 停用部署，等待运行实例完成模型卸载后删除部署。
3. 确认版本不再被其他部署使用，再停用或删除版本。

删除前须满足关联限制，详见[状态与权限](../reference/states-permissions.md)。

## 异常处理

- **运行实例未就绪**：检查预测服务是否正常运行，以及模型文件和框架依赖是否可用，待运行实例状态为 `running` 后再切换。
- **新路由启用被拒绝**：检查同一模型在同一环境中已启用路由的流量比例，先禁用旧路由，再启用新路由。
- **切换后仍使用旧版本**：检查旧路由是否已禁用、默认部署是否已切换，以及相关实验是否仍在运行。发起预测请求时，请勿指定旧部署的 `deployment_id`。
- **新版本预测失败**：按[回滚](#回滚)步骤恢复旧版本，并检查新部署的运行状态、模型文件和框架依赖。

## 使用注意事项

运行中的实验优先于普通路由，因此验证路由切换结果前，请先暂停或结束相关实验。发起预测请求时，请勿指定 `deployment_id`，以确保请求按普通路由分流。

如需记录主体分组并比较各组表现，请参阅[实验流程](../experiments/index.md)。影子预测独立执行，不参与普通路由的流量分配，请参阅[影子发布](shadow.md)。
