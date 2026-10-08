# 模型训练示例

本页介绍如何使用 `examples/` 中的脚本训练并保存评分卡和分类模型。

- **[评分卡示例](#评分卡示例)**：你将学会训练评分卡模型，按照快速上手教程完成部署与评分预测，获取信用评分及违约概率。此外，你还将学会通过金丝雀发布和 A/B 测试比较不同版本。
- **[分类示例](#分类示例)**：你将学会训练分类模型，按照快速上手教程完成部署与分类预测，获取预测类别及其概率。

## 准备

按[安装](../getting-started/installation.md#从源码安装)中的步骤克隆源码仓库。

## 评分卡示例

评分卡示例使用合成信贷数据，包含数值特征、类别特征、缺失值和特殊值。训练脚本使用 `optbinning.Scorecard` 构建评分卡，通过逻辑回归估计违约概率并生成信用评分。

安装所需依赖：

```bash
python -m pip install -e '.[sklearn]'
```

进入评分卡示例目录：

```bash
cd examples/scorecard
```

训练评分卡模型：

```bash
python train.py --random-seed 42 --n-jobs 1 --output artifacts/scorecard_demo.pkl
```

如需比较两个版本，使用不同随机种子训练候选模型：

```bash
python train.py --random-seed 7 --n-jobs 1 --output artifacts/scorecard_demo_v2.pkl
```

训练完成后，模型文件将保存到 `artifacts/` 目录下。通过[管理控制台](../guides/console.md#模型管理)上传文件，注册为 `scorecard-demo` 的以下版本：

| 模型文件                | 版本    | 描述     |
|-------------------------|---------|----------|
| `scorecard_demo.pkl`    | `1.0.0` | 主版本   |
| `scorecard_demo_v2.pkl` | `1.1.0` | 候选版本 |

完成模型注册后，可按照[快速上手](../getting-started/quickstart.md)中的步骤部署模型并验证评分结果，再通过[金丝雀发布](../deployment/canary.md)或 [A/B 测试](../experiments/index.md)比较两个版本。

## 分类示例

分类示例使用 CatBoost 在合成数据上训练二分类模型，类别标签为 `benign` 和 `fraudulent`。训练完成后，模型以 CatBoost 原生格式保存。

安装所需依赖：

```bash
python -m pip install -e '.[catboost]'
```

进入 CatBoost 示例目录：

```bash
cd examples/classification/catboost
```

训练分类模型：

```bash
python train.py --output artifacts/classification_demo.cbm
```

训练完成后，模型文件将保存到 `artifacts/` 目录下。通过[管理控制台](../guides/console.md#模型管理)上传文件，注册为 `classification-demo` 的 `1.0.0` 版本。

预测输入见[评分与分类](../guides/scoring-and-classification.md)。

### 其他分类模型

仓库还提供以下分类示例。安装对应框架的[可选依赖](../getting-started/installation.md)，再运行相应目录下的 `train.py`：

| 框架     | 脚本目录（位于 `examples/classification/`） | 模型类型              |
|----------|---------------------------------------------|-----------------------|
| sklearn  | `logistic_regression/`                      | `logistic_regression` |
| sklearn  | `decision_tree/`                            | `decision_tree`       |
| sklearn  | `random_forest/`                            | `random_forest`       |
| sklearn  | `credit_risk/`                              | `random_forest`       |
| xgboost  | `xgboost/`                                  | `xgboost`             |
| lightgbm | `lightgbm/`                                 | `lightgbm`            |
| catboost | `catboost/`                                 | `catboost`            |

从项目根目录进入示例目录，使用 `--help` 查看脚本支持的参数，例如：

```bash
cd examples/classification/credit_risk
python train.py --help
```

`credit_risk` 使用合成信贷特征和 0/1 违约标签，其他脚本使用通用合成二分类数据。输入字段和标签定义以各脚本为准，模型文件格式与注册要求见[模型兼容性](../models/compatibility.md)。

## 从示例到实际模型

接入自己的模型时，确认保存并重新加载后仍保留特征名称及顺序，模型框架与文件格式符合注册要求，再使用实际输入验证预测结果。

示例中的业务字段和标签用于演示，不代表真实业务数据或模型效果。预测结果的业务含义应以训练标签为准。
