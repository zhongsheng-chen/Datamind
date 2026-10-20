# 模型训练示例

本页介绍如何使用 `examples/` 中的脚本训练并保存评分卡和分类模型。

- **[评分卡示例](#评分卡示例)**：训练评分卡模型，获取信用评分和违约概率，并为版本比较准备候选模型。
- **[分类示例](#分类示例)**：训练分类模型，按照[评分与分类](../guides/scoring-and-classification.md#使用分类模型)完成部署与预测，获取预测类别及其概率。

## 准备

按照[从源码安装](../getting-started/installation.md#从源码安装)中的说明克隆仓库，并创建和激活 Python 虚拟环境。以下命令均在项目根目录执行。

## 评分卡示例

评分卡示例使用合成信贷数据，包含数值特征、类别特征、缺失值和特殊值。训练脚本使用 `optbinning.Scorecard` 构建评分卡，通过逻辑回归估计违约概率并生成信用评分。

安装所需依赖：

```bash
python -m pip install -e ".[sklearn]"
```

训练评分卡模型：

```bash
python examples/scorecard/train.py --random-seed 42 --n-jobs 1 --output examples/scorecard/artifacts/scorecard_demo_v1.pkl
```

如需比较两个版本，使用不同随机种子训练候选模型：

```bash
python examples/scorecard/train.py --random-seed 43 --n-jobs 1 --output examples/scorecard/artifacts/scorecard_demo_v2.pkl
```

训练完成后，模型文件将保存到 `examples/scorecard/artifacts/` 目录下。通过[管理控制台](../guides/console.md#模型管理)将两个模型分别注册为 `scorecard-demo` 的主版本和候选版本：

| 模型文件                | 版本    | 描述     |
|-------------------------|---------|----------|
| `scorecard_demo_v1.pkl` | `1.0.0` | 主版本   |
| `scorecard_demo_v2.pkl` | `1.1.0` | 候选版本 |

完成模型注册后，按照[快速上手](../getting-started/quickstart.md)激活并部署主版本，验证评分结果。若已训练并注册候选版本，可通过[金丝雀发布](../deployment/canary.md)或 [A/B 测试](../experiments/index.md)比较两个版本。

## 分类示例

### CatBoost 示例

本示例使用合成交易数据，通过 CatBoost 训练二分类模型，区分正常交易（`benign`）和欺诈交易（`fraudulent`）。训练完成后，模型以 CatBoost 原生格式保存。

安装所需依赖：

```bash
python -m pip install -e ".[catboost]"
```

训练分类模型：

```bash
python examples/classification/catboost/train.py --output examples/classification/catboost/artifacts/classification_demo.cbm
```

训练完成后，模型文件将保存到 `examples/classification/catboost/artifacts/` 目录下。通过[管理控制台](../guides/console.md#模型管理)将模型注册为 `classification-demo` 的 `1.0.0` 版本。

完成模型注册后，按照[评分与分类](../guides/scoring-and-classification.md#使用分类模型)激活并部署模型，验证分类结果。

### 更多分类示例

`examples/classification/` 目录还提供以下训练示例，均使用与 CatBoost 示例相同的合成交易数据：

| 模型     | 框架         | 脚本目录               |
|----------|--------------|------------------------|
| 逻辑回归 | scikit-learn | `logistic_regression/` |
| 决策树   | scikit-learn | `decision_tree/`       |
| 随机森林 | scikit-learn | `random_forest/`       |
| XGBoost  | XGBoost      | `xgboost/`             |
| LightGBM | LightGBM     | `lightgbm/`            |

按照[安装](../getting-started/installation.md)中的说明安装所需的框架依赖，再运行 `train.py` 训练模型。如需查看训练参数，可使用 `--help`，例如：

```bash
python examples/classification/random_forest/train.py --help
```
