# A/B 测试

实验（`Experiment`）将一部分请求分配到不同版本，通过实验分组（`Variant`）比较实际分流、运行情况与预测结果分布。本教程使用 `scorecard-demo` 的 1.0.0 与 1.1.0，完成分流、预测和分析。

## 前置条件

- 已完成[快速上手](../getting-started/quickstart.md)，并记下 `<model_id>` 与 `<champion_deployment_id>`；
- 已按[模型训练示例](../examples/index.md)生成 1.1.0 候选版本模型文件；
- 主部署已启用；候选部署将在步骤 1 中创建，且必须与主部署属于同一模型和环境；
- 当前模型和环境没有其他 `running` 实验；
- 下文所有 `<...>` 均为占位符，执行前必须替换。

## 分配方式

实验的 `traffic_ratio` 控制总体请求的曝光比例，分组 `weight` 控制实验内部的分配。例如曝光 20%，对照组权重 0.75、实验组权重 0.25，约 80% 请求走普通路由、15% 进入对照组、5% 进入实验组。有限样本不保证精确比例，重复主体复用有效分配。详细语义见[实验分流](assignment.md)。

## 1. 准备候选版本

使用不同随机种子生成演示用的候选版本模型文件：

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
datamind runtime list
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

## 5. 查看分析

发起请求后，可在实验详情的「实验分析」中点击「查看全部」，或使用命令行：

```bash
datamind experiment analyze <experiment_id>
```

检查各组决策数、唯一主体数、实际流量比例与执行状态。批量任务尚未结束时，分析会包含 queued 或 running 状态；完成后重新查询可查看最终指标。指标定义与比较边界见[实验分析](analysis.md)。

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

## 完成标准与排查

使用多个主体发起请求后，应能在实验详情中看到 Assignment；重复同一 `subject_key` 应保持同一 Variant。`experiment analyze` 应列出基准组、各组决策数、主体数和运行指标。实验样本较少时，指标差异不代表已经获得统计结论。

启动失败时，依次检查是否存在其他运行实验、是否恰有一个对照组、有效分组权重是否为 1，以及每个分组部署的模型、环境、状态和发布类型。请求没有进入实验时，检查是否提供稳定主体、是否命中曝光比例以及实验生效时间；未曝光是正常结果，不是路由错误。

## 启动约束

- 同一模型、同一环境中，最多运行一个实验。
- 启用分组中恰好有一个对照组，至少有一个实验组。
- 分组绑定同一模型、同一环境的有效非影子部署。
- `hash` 策略下，启用分组的权重之和为 1。
- `manual` 策略下，已配置有效的主体到分组映射。
