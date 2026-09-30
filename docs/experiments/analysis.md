# 实验分析与生命周期

业务结果回流后，可以比较对照组与实验组的审批、转化和违约表现。分析使用已回流的 Outcome，样本量与预测次数、分配主体数分别统计。

## 分析入口与输出

```bash
datamind experiment analyze <experiment_id> --format json
datamind experiment analyze <experiment_id> --baseline-variant-id <variant_id> --format json
```

默认优先选择 Control 作为基准，显式基准必须属于该实验。返回实验信息、基准、分组信息、metrics 与比较结果。基准没有回流样本时不能产生有效比较。未进入实验的结果单独记录，不计入 Variant 样本。

## 指标口径

| 指标 | 计算 |
| --- | --- |
| total_count | 参与该分组评估的 Outcome 行数 |
| approval_rate | approved_count / total_count |
| conversion_rate | converted_count / total_count |
| default_rate | defaulted_count / total_count |
| bad_rate | bad_count / total_count |
| average_amount | 有效金额总和 / amount_count |
| absolute_lift | 分组值 − 基准值 |
| relative_lift | absolute_lift / 基准值；基准为 0 时为 null |

默认坏样本规则为 defaulted=true、label 为 bad（忽略大小写）或 overdue_days > 30，满足任一条件即计为坏样本。严格大于 30，并非大于等于。多个坏样本条件同时成立只计一条。

布尔字段未回流也仍在 total_count 分母中。平均金额只按有效金额条数计算。相同 outcome_id 的更新改变该行当前指标，不增加行数。不同 ID 的多窗口结果会增加样本行，见[Outcome 更新语义](outcomes.md)。

当前实现不输出置信区间、p 值或显著性结论。分析时说明观察窗口、曝光与回流覆盖、标签成熟程度及每组有效样本量。不能根据 Lift 的正负直接声称统计显著，也不能把 Outcome 比率解释为全部在线曝光请求的比例。

## 生命周期

| 操作 | 允许状态与效果 |
| --- | --- |
| start | draft 或 paused → running；检查分组、部署、权重/映射与同环境实验冲突 |
| pause | running → paused；暂停实验选择，正常路由继续工作 |
| stop | running / paused → stopped；不能再次启动 |
| complete | running / paused → completed；结束实验，不自动提升候选或修改路由 |
| archive | draft / running / paused / stopped / completed → archived；终态 |

CLI 操作示例：

```bash
datamind experiment pause <experiment_id>
datamind experiment start <experiment_id>
datamind experiment complete <experiment_id>
datamind experiment analyze <experiment_id> --format json
```

结束后仍可按原始决策回流成熟的 Outcome，并分析已有数据。结束实验不会把 Treatment 设为主版本。发布切换需另行管理 Deployment 和 Routing。

## 配置修改与删除

草稿阶段设置策略、曝光比例、主体字段、时间和分组。Variant 的部署、权重和状态修改受实验状态约束，不应直接改数据库绕过校验。CLI experiment update 在 paused 阶段仅允许 description 和 effective_to。running、stopped、completed、archived 不允许更新。Console/共享服务的可编辑边界以服务校验为准，暂停不恢复成草稿。

删除和恢复是独立管理动作，要求 experiment.delete。运行实验的删除、分组引用和恢复须遵守关联约束。先结束流量，再处理分组与部署。完整合法状态见[状态与权限](../reference/states-permissions.md)，全部参数见[实验 CLI](../cli/experiment.md)和[分组 CLI](../cli/variant.md)。
