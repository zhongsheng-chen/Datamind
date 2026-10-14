# A/B 测试

A/B 测试将参与实验的主体分配到对照组和实验组，比较不同版本的表现。实验（`Experiment`）通过实验分组（`Variant`）关联部署，并保存主体的分配记录（`Assignment`）。

## 与金丝雀发布的区别

实验和金丝雀发布都可以将请求分配到不同版本，但关注的目标和调整方式不同：

| 对比 | 实验（A/B 测试） | 金丝雀发布 |
|------|-----------------|------------|
| 目的 | 比较对照组与实验组的表现 | 逐步上线候选版本，降低发布风险 |
| 分配记录 | 保存分配记录，同一主体复用有效分配 | 不保存分配记录，通过哈希和路由区间选择部署 |
| 调整方式 | 调整曝光比例或分组权重时，应创建新实验，以保持分组稳定 | 验证后逐步提高候选路由的流量比例 |

如需逐步上线候选版本，请参阅[金丝雀发布](../deployment/canary.md)。

## 前置条件

开始实验前，请完成以下准备：

- 按[模型训练示例](../examples/index.md#评分卡示例)准备主版本和候选版本，再参照[快速上手](../getting-started/quickstart.md)分别完成部署。
- 确认主版本和候选版本均能正常预测。
- 保留主版本的普通路由和默认部署，候选部署仅通过实验接收请求，无需创建候选路由。
- 确认同一模型在同一环境中没有其他运行中实验。
- 确认当前账户具备 `model.read`、`model.write`、`deployment.read`、`deployment.write`、`experiment.read`、`experiment.write`、`runtime.read`、`prediction.invoke` 和 `request.read` [权限](../reference/states-permissions.md#权限全集)。

## 创建实验

为 `scorecard-demo` 创建哈希分配实验，将曝光比例设为 20%：

```bash
datamind experiment create \
  --model-id <model_id> \
  --name scorecard-demo-comparison \
  --strategy hash \
  --traffic-ratio 0.2 \
  --bucket-key borrower_id
```

其中，`<model_id>` 为模型的 ID，可通过以下命令查询：

```bash
datamind model list
```

命令中的参数说明：

- `--strategy`：分配策略，`hash` 表示哈希分配。若要为指定主体设置实验分组，请参阅[手动分配](assignment.md#手动分配)。
- `--traffic-ratio`：实验曝光比例，`0.2` 表示按 20% 的比例选择主体参与实验。
- `--bucket-key`：主体字段，未提供非空 `subject_key` 时，读取请求载荷中 `features` 对象的 `borrower_id` 字段。

如需详细了解实验如何选择主体和分组，请参阅[实验分配](assignment.md)。

> **提示**
>
> 新建实验默认为草稿状态（`draft`），启动后才参与预测请求的分配。

## 创建实验分组

为主版本创建对照组，为候选版本创建实验组，权重分别设为 75% 和 25%：

```bash
datamind experiment variant add <experiment_id> \
  --name control \
  --deployment-id <champion_deployment_id> \
  --weight 0.75 \
  --control

datamind experiment variant add <experiment_id> \
  --name treatment \
  --deployment-id <challenger_deployment_id> \
  --weight 0.25
```

其中，`<experiment_id>` 为实验的 ID，可通过以下命令查询：

```bash
datamind experiment list --model-id <model_id>
```

两个部署 ID 分别表示：

- `<champion_deployment_id>`：主版本 `1.0.0` 的部署 ID。
- `<challenger_deployment_id>`：候选版本 `1.1.0` 的部署 ID。

部署 ID 可通过以下命令查询：

```bash
datamind deployment list
```

`--control` 将分组设为对照组；未指定时为实验组。新增分组默认处于启用状态。

## 启动实验

启动前，请确认：

- 同一模型在同一环境中没有其他运行中实验。
- 实验必须且只能包含一个启用的对照组，并至少包含一个启用的实验组。
- 实验分组只能绑定同一模型在同一环境中的可用部署，且部署的发布类型不能为 `shadow`。
- 哈希策略下，启用分组的权重之和为 1。

启动实验：

```bash
datamind experiment start <experiment_id>
```

启动成功后，实验进入运行状态（`running`），仅在生效期内参与请求分配。

> **注意**
>
> 未参与实验的请求，以及实验暂停、停止或完成后的请求，由普通路由和默认部署处理。若没有匹配的普通路由，也没有可用的默认部署，请求将返回无可用部署错误。实验对照组不会自动成为默认部署。

## 验证实验结果

参照[在线预测](../guides/online-prediction.md)或[批量预测](../guides/batch-prediction.md)发起请求，再通过[管理控制台](../guides/console.md#api-调用与执行记录)查看请求与执行记录。

按以下步骤核对：

1. 使用请求 ID（`request_id`）查询关联的执行记录。批量预测需等待批次完成后，按每条实例的请求 ID 分别查询。
2. 核对主预测（`primary`）执行记录的部署、版本和状态，确认请求由实验分组绑定的版本处理，且执行成功。
3. 检查两个版本的预测结果，确认符合预期；重复请求同一主体，确认复用已有分配，并使用不同主体观察实验分组和普通路由的分配情况。

> **注意**
>
> 发起请求时，请勿指定 `deployment_id`，否则会跳过实验分配。未参与实验的请求继续由普通路由和默认部署处理，不会产生实验分配记录。
>
> 请求未提供 `subject_key` 或其值为空时，系统读取 `features` 对象中由 `bucket_key` 指定的顶层字段值作为主体标识。`--bucket-key` 仅指定字段名，字段值需由请求提供。

## 分析实验结果

使用以下命令分析实验结果：

```bash
datamind experiment analyze <experiment_id>
```

分析结果展示各组的决策数、主体数、执行状态和预测指标。批量任务完成后，可重新运行该命令查看完整结果。各指标的含义和统计范围，请参阅[实验分析](analysis.md)。

## 完成或停止实验

正常结束实验：

```bash
datamind experiment complete <experiment_id>
```

需要中止实验：

```bash
datamind experiment stop <experiment_id>
```

完成或停止后，实验不再参与新请求的分配。暂停的实验可重新启动，已完成或停止的实验不能重新启动。结束实验不会自动切换模型版本。如需发布候选版本，请参阅[全量发布](../deployment/full.md#版本切换)。暂停、恢复等操作请参阅[实验分析](analysis.md#生命周期)。

## 异常处理

- **实验启动失败**：检查是否存在其他运行中实验，以及对照组数量、分组权重和绑定部署是否满足[启动条件](#启动实验)。
- **请求未参与实验**：检查主体标识、实验状态和生效时间。未命中曝光比例的主体不参与实验，属于正常分配结果。
- **已分配主体未由实验部署处理**：检查对应分组是否仍为 `active`，以及绑定部署是否启用、是否处于生效时间内。不可用的实验目标会回退到普通路由和默认部署，详见[分配记录与分组稳定性](assignment.md#分配记录与分组稳定性)。
- **预测执行失败**：检查执行记录中的错误、部署运行状态、模型文件和框架依赖。

## 使用注意事项

本教程使用合成数据训练模型，预测结果差异不能直接证明实际业务效果。实验分析仅比较分流、运行情况和预测结果分布，不提供统计显著性结论。
