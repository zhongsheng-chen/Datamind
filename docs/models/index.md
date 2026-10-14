# 模型管理

将训练好的模型文件注册为模型版本，激活后即可创建部署。关于模型与版本的关系，请参阅[模型与版本](../concepts/resources.md)。关于模型文件和依赖要求，请参阅[模型兼容性](compatibility.md)。

## 前置条件

开始操作前，请完成以下准备：

- 完成[安装](../getting-started/installation.md)和[配置与初始化](../getting-started/configuration.md)。
- 按[模型训练示例](../examples/index.md#评分卡示例)准备模型文件。
- 确认当前账户具备 `model.write`、`model.read` 和 `model.delete` [权限](../reference/states-permissions.md#权限全集)。

## 注册模型

首次使用模型时，可注册模型及其首个版本：

```bash
datamind model register scorecard-demo \
  --display-name "评分卡示例模型" \
  --version 1.0.0 \
  --version-description "首个评分卡版本" \
  --model-path examples/scorecard/artifacts/scorecard_demo_v1.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

注册完成后，查看模型与版本信息：

```bash
datamind model show scorecard-demo --version 1.0.0
```

新注册的模型和版本均处于未激活（`inactive`）状态。激活版本后，即可创建部署。

## 注册新版本

需要迭代模型或对比版本效果时，可为同一模型注册新版本：

```bash
datamind model register scorecard-demo \
  --version 1.1.0 \
  --version-description "候选评分卡版本" \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

注册完成后，查看新版本信息：

```bash
datamind model show scorecard-demo --version 1.1.0
```

新版本处于未激活（`inactive`）状态。激活版本后，即可创建部署。

> **注意**
>
> 同一模型的所有版本须使用相同的框架、模型类型和任务类型。如需更改，请注册新模型。
>
> 版本说明通过 `--version-description` 设置。`--description` 仅用于首次注册时设置模型描述，不会在注册新版本时更新。

## 强制注册版本

需要修正已有版本的模型文件时，可使用 `--force` 强制注册，保留原版本号。先重新训练模型，生成新的模型文件：

```bash
python examples/scorecard/train.py \
  --random-seed 17 \
  --n-jobs 1 \
  --output examples/scorecard/artifacts/scorecard_demo_v2_revised.pkl
```

然后，使用新文件强制注册已有版本：

```bash
datamind model register scorecard-demo \
  --version 1.1.0 \
  --version-description "修订后的候选评分卡版本" \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2_revised.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --force
```

文件更新后，修订号（`artifact_revision`）递增，版本仍为未激活（`inactive`）状态。文件内容未变化时，修订号不变。

> **注意**
>
> 强制注册要求版本处于未激活（`inactive`）状态、未被删除，且没有关联部署。已发布版本如需更新模型文件，请[注册新版本](#注册新版本)，确保历史预测结果可追溯到原模型文件。

## 激活版本

准备使用某个版本时，可将其激活，再创建部署：

```bash
datamind model activate scorecard-demo --version 1.0.0
```

查看激活后的状态：

```bash
datamind model show scorecard-demo --version 1.0.0
```

版本激活后，可参照[全量发布](../deployment/full.md)、[金丝雀发布](../deployment/canary.md)或[影子发布](../deployment/shadow.md)创建部署。

## 停用版本

暂时不再使用某个版本时，可将其停用，需要时再次激活：

```bash
datamind model deactivate scorecard-demo --version 1.0.0
```

停用前，请先停用该版本的所有已启用部署。停用后，版本状态为 `inactive`。

## 弃用版本

确定不再使用某个版本时，可将其标记为弃用：

```bash
datamind model deprecate scorecard-demo --version 1.0.0
```

弃用前，请先停用该版本的所有已启用部署。弃用后，版本状态为 `deprecated`，无法再次激活，但仍可归档。

## 删除版本

删除不再使用的版本：

```bash
datamind model delete scorecard-demo --version 1.0.0
```

版本删除后，版本信息和模型文件仍会保留，可恢复使用。删除前，请先结束相关实验并移除路由，停用关联部署，待模型卸载完成后，先删除部署，再删除版本。

## 恢复版本

恢复已逻辑删除的版本：

```bash
datamind model restore scorecard-demo --version 1.0.0
```

若所属模型也已删除，请省略 `--version` 参数，恢复模型及随其删除的版本：

```bash
datamind model restore scorecard-demo
```

恢复后，版本处于未激活（`inactive`）状态。模型文件一旦开始永久清理，版本便无法恢复。

## 永久清理

永久清理已逻辑删除版本的模型文件：

```bash
datamind model purge scorecard-demo --version 1.0.0
```

> **注意**
>
> 执行前，请先停用关联部署，并等待运行实例完成卸载。清理后无法恢复版本，请确认模型文件不再需要后执行。

## 选择注册方式

- [注册新版本](#注册新版本)：使用新版本号，保留已有版本及其模型文件，用于模型迭代和效果对比。

- [强制注册版本](#强制注册版本)：保留版本号，替换模型文件并递增修订号，用于修正已有版本的模型文件。

## 常见问题

- **文件不存在或加载失败**：检查文件路径、模型框架、文件格式及依赖，具体要求见[模型兼容性](compatibility.md)。
- **版本已存在，文件内容不同**：[注册新版本](#注册新版本)，或确认满足条件后[强制注册版本](#强制注册版本)。
- **版本状态不允许强制注册**：确认版本处于未激活（`inactive`）状态；已发布版本请[注册新版本](#注册新版本)。
- **版本仍有未删除的关联部署**：已停用的部署会阻止强制注册，建议[注册新版本](#注册新版本)，保留已有部署及预测记录。
- **注册新版本时提示模型描述不一致**：注册新版本不能修改已有模型的描述，请省略 `--description`；新版本的说明通过 `--version-description` 设置。
- **版本已删除**：请先[恢复版本](#恢复版本)，再执行注册操作。若需替换模型文件，请参阅[强制注册版本](#强制注册版本)。
