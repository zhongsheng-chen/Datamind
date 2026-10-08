# 模型管理

将训练好的模型文件注册为模型版本，再根据发布需要激活、部署或更新版本。资源关系见[模型与版本](../concepts/resources.md)，文件格式与框架要求见[模型兼容性](compatibility.md)。

## 前置条件

完成[安装](../getting-started/installation.md)和[配置与初始化](../getting-started/configuration.md)，准备可加载的模型文件，并安装对应框架依赖。使用评分卡示例时，按[模型训练示例](../examples/index.md)生成所需文件。

以下命令均从项目根目录执行。

启用认证时，注册和激活需要 `model.write` 权限，查询需要 `model.read` 权限。完整参数见[模型命令参考](../cli/model.md)。

## 注册模型

首次注册创建模型与版本。以下示例使用已经训练好的评分卡文件：

```bash
datamind model register scorecard-demo \
  --display-name "评分卡示例模型" \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

成功结果中的 `action` 为 `created`。保存 `model_id` 和 `version_id`，再查询注册后的状态：

```bash
datamind model show scorecard-demo --version 1.0.0
```

新模型和版本的状态均为 `inactive`。注册保存文件与元数据，后续通过激活和部署完成发布。

## 注册新版本

需要更新模型或比较不同版本时，为同一模型注册新版本。先按[评分卡示例](../examples/index.md#评分卡示例)训练候选模型，生成 `scorecard_demo_v2.pkl`，再注册为 `1.1.0` 版本：

```bash
datamind model register scorecard-demo \
  --version 1.1.0 \
  --version-description "候选评分卡版本" \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

新版本沿用原模型的 `model_id`，获得独立的 `version_id`，初始状态为 `inactive`。框架、模型类型和任务类型必须与原模型一致；更改这些属性时使用新的模型名称。

`--description` 用于模型描述，注册新版本时不能改写已有描述。版本说明使用 `--version-description`。

## 替换发布前的文件

尚未发布的版本需要修正文件时，可以保持版本号并使用 `--force`。版本必须处于 `inactive`、未被逻辑删除，且当前没有该版本的未删除部署。

以下命令生成修正文件；使用自己的模型时，替换为实际文件路径：

```bash
python examples/scorecard/train.py --random-seed 11 --n-jobs 1 \
  --output examples/scorecard/artifacts/scorecard_demo_v2_revised.pkl

datamind model register scorecard-demo \
  --version 1.1.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo_v2_revised.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --force
```

内容发生变化时，结果为 `action=revised`，`artifact_revision` 增加，版本指向新文件并保持 `inactive`。重复提交相同内容返回 `action=unchanged`，修订号保持不变，即使指定了 `--force`。

系统仅检查当前未删除的部署记录。已发布模型的内容更新应使用新业务版本，以保留历史发布和预测结果的对应关系。

## 激活版本

确认文件和注册信息后，激活需要发布的版本：

```bash
datamind model activate scorecard-demo --version 1.0.0
datamind model show scorecard-demo --version 1.0.0
```

发布候选版本时，将版本号替换为 `1.1.0`。激活后模型和目标版本状态为 `active`，随后按[全量发布](../deployment/full.md)或[金丝雀发布](../deployment/canary.md)创建部署。

## 处理注册失败

| 情况                     | 处理方式                                                                |
|--------------------------|-------------------------------------------------------------------------|
| 文件不存在或加载失败     | 核对路径、框架、格式与已安装依赖                                        |
| 版本已存在，文件内容不同 | 注册新版本，或在符合发布前替换条件时使用 `--force`                      |
| 版本状态不允许替换       | 核对版本是否已激活或发布；已发布内容使用新版本                          |
| 当前存在部署记录         | 注册新版本，保留现有发布历史                                            |
| 模型描述不一致           | 省略 `--description` 或保留原描述，版本信息写入 `--version-description` |
| 版本已删除               | 按恢复流程处理，或注册新的业务版本                                      |

## 停用、删除与恢复

停用使用 `deactivate`，之后可再次 `activate`。弃用使用 `deprecate`，弃用后仅可归档。版本操作通过 `--version` 或 `--version-id` 指定目标；省略版本时，操作范围包含模型及其关联版本。

逻辑删除使用 `delete`，保留数据库记录与模型文件；`restore` 恢复删除标记。`purge` 永久清理已逻辑删除资源的文件，清理后无法恢复。

下线时先结束实验并移除路由，再停用部署并等待卸载，随后删除部署，最后处理版本和模型。各操作的允许状态与权限见[状态与权限](../reference/states-permissions.md)。
