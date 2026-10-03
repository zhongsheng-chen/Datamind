# 模型训练

源码仓库的 `examples/` 提供可复现的训练脚本。请克隆仓库后从项目根目录运行，PyPI 安装包不包含这些文件。脚本生成本地制品，注册和发布由调用方执行。

## 评分卡示例

安装 `.[sklearn]`，训练两个版本的制品。两个文件都注册为 `scorecard-demo` 的版本，用于金丝雀或 A/B 教程：

```bash
python -m pip install -e '.[sklearn]'
python examples/scorecard/train.py --random-seed 42 --n-jobs 1 \
  --output examples/scorecard/artifacts/scorecard_demo.pkl
python examples/scorecard/train.py --random-seed 7 --n-jobs 1 \
  --output examples/scorecard/artifacts/scorecard_demo_v2.pkl
```

合成信贷数据包含数值、类别、缺失值和特殊值。脚本训练 `optbinning.Scorecard`，以逻辑回归估计违约概率并转换为评分。使用[快速上手](../getting-started/quickstart.md)发布首个版本，候选版本用于[A/B 教程](../experiments/index.md)。

## 分类示例

核心指南使用 `classification-demo` 和 CatBoost 原生制品，其注册与输入见[分类与评分](../guides/models.md)。其他框架可按下表选择，安装对应 extra 后运行脚本：

| 框架 | 脚本目录（examples/classification/ 下） | 模型类型 |
| --- | --- | --- |
| sklearn | logistic_regression/ | logistic_regression |
| sklearn | decision_tree/ | decision_tree |
| sklearn | random_forest/ | random_forest |
| sklearn | credit_risk/ | random_forest |
| xgboost | xgboost/ | xgboost |
| lightgbm | lightgbm/ | lightgbm |
| catboost | catboost/ | catboost |

```bash
python examples/classification/catboost/train.py --help
```

credit_risk 使用合成信贷特征和 0/1 违约标签。其他分类脚本使用合成二分类数据，具体列名和标签以脚本为准。选择新脚本后检查它的输入特征与保存格式，按[兼容性参考](../models/compatibility.md)注册。

## 从示例到实际模型

合成数据用于学习训练、保存和发布流程。接入自己的模型时，确认制品保留了有序特征信息，并用实际输入检查加载与预测。任务名称或文件名不会改变训练标签的含义。
