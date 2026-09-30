# A/B 测试

以 `application-scorecard` 的 1.0.0 与 1.1.0 为例，将一部分请求分配到两个评分卡版本，回流业务结果后比较表现。先完成[首次模型部署](../getting-started/quickstart.md)，确认主部署已启用，并记下模型与部署 ID。

## 启动前约束

- 同一模型与环境 同时只能有一个 运行中的实验。
- 必须且只能有一个启用的 对照组，至少有一个启用的 实验组。
- 启用分组 必须绑定 active Deployment，且属于同一模型与环境。
- 分组仅可使用非影子部署。
- hash 策略下启用分组 的权重之和必须为 1。
- manual 策略需要有效的主体到 Variant 映射。

## 1. 准备候选版本

使用不同随机种子生成演示候选制品：

```bash
python examples/scorecard/train.py \
  --random-seed 7 \
  --output examples/scorecard/artifacts/application_scorecard_candidate.pkl

datamind model register application-scorecard \
  --version 1.1.0 \
  --model-path examples/scorecard/artifacts/application_scorecard_candidate.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring

datamind model activate application-scorecard --version 1.1.0
datamind deployment create application-scorecard --version 1.1.0 --rollout canary --role challenger
```

复制候选 Deployment ID，替换 `<challenger_deployment_id>`：

```bash
datamind deployment enable <challenger_deployment_id>
```

候选部署可以仅通过 Experiment 参与分配。本次控制台演示还为它配置了 20% 的普通副路由，主部署使用 80% 的普通主路由。具体切换步骤见[流量管理](../routing/index.md)。未进入实验的请求继续按普通路由分配。候选数据为合成示例，不用于证明新版本效果更好。

## 2. 创建 Experiment

将 `<model_id>` 替换为申请评分模型的 Model ID：

```bash
datamind experiment create \
  --model-id <model_id> \
  --name application-scorecard-comparison \
  --strategy hash \
  --traffic-ratio 0.5 \
  --bucket-key borrower_id
```

复制输出的 Experiment ID，后续用 `<experiment_id>` 表示。

## 3. 创建 Control 与 Treatment

```bash
datamind experiment variant add <experiment_id> \
  --name control \
  --deployment-id <champion_deployment_id> \
  --weight 0.5 \
  --control

datamind experiment variant add <experiment_id> \
  --name treatment \
  --deployment-id <challenger_deployment_id> \
  --weight 0.5
```

`<champion_deployment_id>` 是 1.0.0 主部署。CLI 新增分组默认 active。`traffic_ratio=0.5` 表示约 50% 总流量进入实验，两个 Variant 的 `weight=0.5` 表示实验内部各占约 50%，即各约占总流量的 25%。

## 4. 启动并发起请求

```bash
datamind experiment start <experiment_id>
```

使用[快速上手中的预测请求](../getting-started/quickstart.md)，为每个借款人提供稳定的 `subject_key` 和 `subject_type=borrower`。hash 分配时，显式 `subject_key` 优先。没有显式主体时，才尝试从请求载荷解析 `bucket_key`。不能仅配置 `bucket_key` 就假定客户端已经提供主体。

在线与批量预测都可参与实验。重复主体用于验证分配稳定性。不同主体用于观察两组分配及普通路由回退。避免显式提供 `deployment_id`，否则会进入指定部署路径。

## 5. Outcome 回流与分析

保存预测响应的 `request_id`，按照[Outcome 回流](outcomes.md)提交后验结果：

```bash
datamind outcome submit borrower-001 \
  --request-id <request_id> \
  --outcome-id out-borrower-001-t30 \
  --approved \
  --converted \
  --not-defaulted \
  --overdue-days 0 \
  --amount 10000 \
  --label T+30 \
  --context '{"observation_window_days":30}'

datamind experiment analyze <experiment_id> --format json
```

未进入实验的请求仍可记录 Outcome，但不能将其当作实验 Variant 的样本。回流标识、观察窗口和更新边界见[Outcome](outcomes.md)，指标解释见[分析](analysis.md)。

## 6. 完成或停止

正常结束使用：

```bash
datamind experiment complete <experiment_id>
```

需要中止时使用：

```bash
datamind experiment stop <experiment_id>
```

暂停、恢复及结束后的操作见[实验分析与生命周期](analysis.md)。

## 演示结果

手册中的首轮 64 个借款人请求，22 个命中对照组、17 个命中实验组、25 个使用普通路由，随后回流模拟 T+30 结果并完成分析。完整调用规模与界面见[Console 手册](../guides/console.md)。

这些合成样本用于演示分流、记录和分析流程，模型的业务效果需要用真实、成熟的结果评估。
