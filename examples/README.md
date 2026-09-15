# 示例

本目录中的训练脚本使用可复现的合成数据，仅生成本地模型制品。模型注册、激活、部署和加载由 Datamind CLI 显式执行。训练生成的 `artifacts/` 目录不纳入版本管理。

## 目录结构

```text
examples/
├── README.md
├── scorecard/
│   └── train.py
└── classification/
    ├── decision_tree/train.py
    ├── random_forest/train.py
    ├── logistic_regression/train.py
    ├── xgboost/train.py
    ├── lightgbm/train.py
    └── catboost/train.py
```

## 安装依赖

运行全部示例：

```bash
pip install -e ".[full]"
```

只运行 sklearn 和评分卡示例：

```bash
pip install -e ".[sklearn]"
```

也可以按需安装 `xgboost`、`lightgbm` 或 `catboost` 可选依赖。

## 分类模型

六个分类示例使用同样规模和随机种子的合成二分类数据。每个 `train.py` 都完整包含数据生成、训练/测试集划分、模型训练、评估、制品保存和命令行入口。

Decision Tree、Random Forest、Logistic Regression 和 CatBoost 使用 `benign`、`fraudulent` 字符串类别，演示模型类别标签不限于 `0/1`。Datamind 按模型 `classes_` 的顺序将第二个类别识别为正类。XGBoost 的分类器接口要求从零开始的整数类别；XGBoost 和 LightGBM 示例又保存不携带原始类别映射的原生 Booster 制品，因此这两个示例保留 `0/1` 标签，正类为 `1`。

| 模型 | 训练命令 | 框架 | 模型类型 | 默认制品 |
| --- | --- | --- | --- | --- |
| Decision Tree | `python examples/classification/decision_tree/train.py` | sklearn | decision_tree | `decision_tree/artifacts/decision_tree.pkl` |
| Random Forest | `python examples/classification/random_forest/train.py` | sklearn | random_forest | `random_forest/artifacts/random_forest.pkl` |
| Logistic Regression | `python examples/classification/logistic_regression/train.py` | sklearn | logistic_regression | `logistic_regression/artifacts/logistic_regression.pkl` |
| XGBoost | `python examples/classification/xgboost/train.py` | xgboost | xgboost | `xgboost/artifacts/xgboost.ubj` |
| LightGBM | `python examples/classification/lightgbm/train.py` | lightgbm | lightgbm | `lightgbm/artifacts/lightgbm.txt` |
| CatBoost | `python examples/classification/catboost/train.py` | catboost | catboost | `catboost/artifacts/catboost.cbm` |

所有分类训练入口都支持以下参数：

```bash
python examples/classification/random_forest/train.py \
  --sample-count 5000 \
  --random-seed 42 \
  --output ./random_forest.pkl
```

注册模型时，按照上表选择 `framework` 和 `model-type`：

```bash
datamind model register risk-random-forest \
  --version 1.0.0 \
  --model-path examples/classification/random_forest/artifacts/random_forest.pkl \
  --framework sklearn \
  --model-type random_forest \
  --task-type classification \
  --description "随机森林风险分类模型"
```

sklearn 模型保存为 joblib 制品。XGBoost、LightGBM 和 CatBoost 分别保存为 Datamind 加载器支持的原生 UBJSON、文本和 CBM 制品。

## 信用评分卡

评分卡示例使用包含数值变量、类别变量、缺失值和特殊值的合成信贷数据，演示 WOE 分箱、逻辑回归、跨时间验证、评分转换和模型保存。最终制品是 OptBinning 原生 `Scorecard`。

训练评分卡：

```bash
python examples/scorecard/train.py
```

也可以调整样本数量、随机种子、训练/测试集比例和并行任务数：

```bash
python examples/scorecard/train.py \
  --sample-size 10000 \
  --random-seed 42 \
  --train-size 0.75 \
  --test-size 0.25 \
  --n-jobs -1
```

默认生成 `examples/scorecard/artifacts/scorecard.pkl`。注册模型：

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --description "信用评分模型"
```

训练完成后会输出留出集坏样本率、AUC、Gini、KS、示例客户的违约概率和信用分，以及各变量的分箱摘要。
