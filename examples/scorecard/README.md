# 信用评分模型示例

本示例使用可复现的合成信贷数据训练评分卡模型，用于演示真实的
WOE 分箱、逻辑回归、模型验证、评分转换和模型注册。

最终制品是一个 OptBinning 原生 `Scorecard`：

```text
原始数值/类别特征
  → OptBinning BinningProcess（最优分箱和 WOE 转换）
  → OptBinning Scorecard（内含 LogisticRegression、概率和分值）
  → joblib scorecard.pkl
```

训练数据同时包含申请日期、数值变量、类别变量和缺失值。1 表示
违约，0 表示正常；申请日期不作为模型特征，而是用于跨时间切分。
最早 75% 样本用于训练，最新 25% 样本用于验证，分箱只在训练集
拟合，避免随机切分和数据泄漏导致效果虚高。

## 目录内容

- `train.py`：生成演示数据、训练、验证并保存原生 Scorecard。
- `scoring_config.json`：评分参数配置。
- `route_rules.json`：路由规则示例。
- `artifacts/`：训练生成的模型制品，不纳入版本管理。

## 训练模型

```bash
pip install -e ".[sklearn]"
python examples/scorecard/train.py
```

默认生成：

```text
examples/scorecard/artifacts/scorecard.pkl
```

也可以指定输出路径：

```bash
python examples/scorecard/train.py --output ./scorecard.pkl
```

还可以调整样本数量和随机种子：

```bash
python examples/scorecard/train.py \
  --sample-size 10000 \
  --random-seed 42 \
  --train-size 0.75 \
  --test-size 0.25 \
  --n-jobs -1
```

训练完成后会输出：

- 留出集坏样本率、AUC、Gini 和 KS；
- 示例客户的违约概率和信用分；
- 每个变量的类型、求解状态、箱数、IV 和质量分；
- 已回读验证的 `scorecard.pkl` 文件路径。

模型将 `annual_income` 和 `credit_history_years` 的缺失值作为独立
信息处理；`employment_type` 和 `residence_status` 使用类别分箱。
线上加载该 `.pkl` 时必须安装与训练环境兼容的 `optbinning` 和
`scikit-learn`。

## 注册模型

```bash
datamind model register scorecard \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring \
  --description "信用评分模型" \
  --version-description "信用评分模型 v1.0.0"
```

训练与注册相互独立：训练脚本只生成本地制品，模型注册由 CLI 显式执行。
