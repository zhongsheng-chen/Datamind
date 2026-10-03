# A/B 测试

实验（`Experiment`）将一部分请求分配到不同版本，通过实验分组（`Variant`）比较回流的业务结果。本教程使用 `scorecard-demo` 的 1.0.0 与 1.1.0，完成分流、结果回流和分析。先完成[快速上手](../getting-started/quickstart.md)，确认主部署已启用，并记下模型与部署 ID。

## 分配方式

实验的 `traffic_ratio` 控制总体请求的曝光比例，分组 `weight` 控制实验内部的分配。例如曝光 20%，对照组权重 0.75、实验组权重 0.25，约 80% 请求走普通路由、15% 进入对照组、5% 进入实验组。有限样本不保证精确比例，重复主体复用有效分配。详细语义见[实验分流](assignment.md)。

## 1. 准备候选版本

使用不同随机种子生成演示候选制品：

```bash
python examples/scorecard/train.py \
  --random-seed 7 \
  --output examples/scorecard/artifacts/scorecard_demo_v2.pkl

datamind model register scorecard-demo \
  --version 1.1.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring

datamind model activate scorecard-demo --version 1.1.0
datamind deployment create scorecard-demo --version 1.1.0 --rollout canary --role challenger
```

复制候选部署 ID，替换 `<challenger_deployment_id>`：

```bash
datamind deployment enable <challenger_deployment_id>
datamind runtime list --format json
```

确认候选部署已实际加载，再继续创建实验。

候选部署可以仅通过实验参与分配。如需让未曝光请求也参与渐进发布，可另行配置普通路由，操作见[金丝雀教程](../deployment/canary.md)。未进入实验的请求继续按普通路由分配。候选数据为合成示例，不用于证明新版本效果更好。

## 2. 创建实验

将 `<model_id>` 替换为评分卡示例的模型 ID：

```bash
datamind experiment create \
  --model-id <model_id> \
  --name scorecard-demo-comparison \
  --strategy hash \
  --traffic-ratio 0.2 \
  --bucket-key borrower_id
```

复制输出的实验 ID，后续用 `<experiment_id>` 表示。

## 3. 创建对照组与实验组

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

`<champion_deployment_id>` 是 1.0.0 主部署。新增分组默认 `active`，上述权重与曝光设置对应前文的 15% / 5% 分配。

## 4. 启动并发起请求

```bash
datamind experiment start <experiment_id>
```

使用[快速上手中的预测请求](../getting-started/quickstart.md)，为每个借款人提供稳定的 `subject_key` 和 `subject_type=borrower`。哈希分配时，显式 `subject_key` 优先。没有显式主体时，才尝试从请求载荷解析 `bucket_key`。不能仅配置 `bucket_key` 就假定客户端已经提供主体。

在线与批量预测都可参与实验。重复主体用于验证分配稳定性。不同主体用于观察两组分配及普通路由回退。避免显式提供 `deployment_id`，否则会进入指定部署路径。

## 5. 业务结果回流与分析

保存预测响应的 `request_id`，按[业务结果回流](outcomes.md)提交后验结果：

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

未进入实验的请求仍可记录业务结果，但不能将其当作实验分组的样本。回流标识、观察窗口和更新边界见[业务结果](outcomes.md)，指标解释见[实验分析](analysis.md)。

## 6. 完成或停止

正常结束使用：

```bash
datamind experiment complete <experiment_id>
```

需要中止时使用：

```bash
datamind experiment stop <experiment_id>
```

暂停、恢复及结束后的操作见[实验分析](analysis.md)。

## 启动约束

- 同一模型、同一环境中，最多运行一个实验。
- 启用分组中恰好有一个对照组，至少有一个实验组。
- 分组绑定同一模型、同一环境的有效非影子部署。
- `hash` 策略下，启用分组的权重之和为 1。
- `manual` 策略下，已配置有效的主体到分组映射。
