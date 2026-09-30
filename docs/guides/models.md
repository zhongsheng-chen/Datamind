# 评分卡与分类模型

本页以申请评分模型为主，使用欺诈风险模型对照分类任务的输入与响应，并补充行为评分、催收评分、多头借贷风险和违约概率模型。

## 演示模型

| 模型标识 | 显示名称 | 任务 | 框架 | 制品 |
| --- | --- | --- | --- | --- |
| `application-scorecard` | 申请评分模型 | scoring | sklearn / optbinning | `application_scorecard.pkl` |
| `behavior-scorecard` | 行为评分模型 | scoring | sklearn / optbinning | `behavior_scorecard.pkl` |
| `collection-scorecard` | 催收评分模型 | scoring | sklearn / optbinning | `collection_scorecard.pkl` |
| `fraud-risk` | 欺诈风险模型 | classification | CatBoost | `fraud_risk.cbm` |
| `multi-borrowing-risk` | 多头借贷风险模型 | classification | XGBoost | `multi_borrowing_risk.ubj` |
| `default-probability` | 违约概率模型 | classification | sklearn / RandomForest | `default_probability.pkl` |

这些业务名称用于展示不同模型的管理和服务交付。三个评分模型复用评分卡训练示例，以不同随机种子生成独立制品；分类模型使用对应框架的合成数据示例。它们并非针对这些业务目标训练的正式模型。特别是多头借贷风险示例复用交易分类数据，催收评分也不预测真实回收率。训练命令见[银行场景示例](../examples/index.md)。

## 申请评分模型

首次注册、激活、部署、路由和 HTTP 认证见[快速上手](../getting-started/quickstart.md)。三个评分模型共享以下八个输入特征：

```json
{
  "request": {
    "model_name": "application-scorecard",
    "subject_key": "borrower-001",
    "subject_type": "borrower",
    "features": {
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.3,
      "credit_utilization_ratio": 0.4,
      "delinquency_count": 0,
      "credit_history_years": 8,
      "employment_type": "salaried",
      "residence_status": "mortgage"
    }
  }
}
```

调用 `/predict` 时按快速上手设置地址与认证请求头。调用行为评分或催收评分时，分别将 `model_name` 替换为 `behavior-scorecard` 或 `collection-scorecard`。

响应包含违约概率 `probability`、总评分 `score`、默认评分阈值 `threshold=600`，以及各特征的 `bin`、`woe` 和 `points`。申请评分 1.0.0 本次示例返回 `score=533.7227645335712`、`probability=0.142860562600954`。

`decision=reject` 表示模型服务按评分阈值返回的判断。行为和催收演示同样沿用评分卡的刻度与返回结构；业务名称不会改变训练标签或阈值含义。重训或命中候选版本后，具体评分可能不同。

## 欺诈风险模型

安装 CatBoost extra，并使用原生 CBM 制品注册分类模型：

```bash
python -m pip install -e ".[sklearn,catboost]"
python examples/classification/catboost/train.py \
  --output examples/classification/catboost/artifacts/fraud_risk.cbm

datamind model register fraud-risk \
  --display-name "欺诈风险模型" \
  --version 1.0.0 \
  --model-path examples/classification/catboost/artifacts/fraud_risk.cbm \
  --framework catboost \
  --model-type catboost \
  --task-type classification

datamind model activate fraud-risk --version 1.0.0
datamind deployment create fraud-risk --version 1.0.0 --rollout full
```

复制部署 ID 后启用并配置主路由：

```bash
datamind deployment enable <fraud_deployment_id>
datamind route create <fraud_deployment_id> \
  --name fraud-risk-main --traffic-ratio 1 --enabled
```

请求使用五个交易特征。训练脚本通过 `make_classification` 生成连续数值；示例数值不代表真实金额、小时或距离的单位：

```json
{
  "request": {
    "model_name": "fraud-risk",
    "subject_key": "transaction-001",
    "subject_type": "transaction",
    "features": {
      "transaction_amount": 0.8,
      "account_age_days": -0.2,
      "transaction_hour": 0.1,
      "distance_from_home": 1.2,
      "recent_transaction_count": 0.5
    }
  }
}
```

响应包含 `probability`、`prediction`、`label` 和默认概率阈值 `threshold=0.5`。CatBoost 示例的类别标签为 `benign` 与 `fraudulent`，分类结果没有信用评分或分箱明细。

## 补充模型

完成[制品训练](../examples/index.md)后，可注册其余四个模型：

```bash
datamind model register behavior-scorecard --display-name "行为评分模型" \
  --version 1.0.0 --model-path examples/scorecard/artifacts/behavior_scorecard.pkl \
  --framework sklearn --model-type logistic_regression --task-type scoring

datamind model register collection-scorecard --display-name "催收评分模型" \
  --version 1.0.0 --model-path examples/scorecard/artifacts/collection_scorecard.pkl \
  --framework sklearn --model-type logistic_regression --task-type scoring

datamind model register multi-borrowing-risk --display-name "多头借贷风险模型" \
  --version 1.0.0 --model-path examples/classification/xgboost/artifacts/multi_borrowing_risk.ubj \
  --framework xgboost --model-type xgboost --task-type classification

datamind model register default-probability --display-name "违约概率模型" \
  --version 1.0.0 --model-path examples/classification/credit_risk/artifacts/default_probability.pkl \
  --framework sklearn --model-type random_forest --task-type classification
```

分别执行 `datamind model activate <模型标识> --version 1.0.0`、`datamind deployment create <模型标识> --version 1.0.0 --rollout full`，再启用输出的部署 ID 并创建比例为 1 的主路由。步骤与欺诈风险模型相同。

多头借贷风险模型的 XGBoost 示例使用上述五个交易特征，标签为 0/1；违约概率模型使用 `age`、`annual_income`、`debt_to_income_ratio`、`credit_utilization_ratio` 和 `delinquency_count` 五个信贷特征，标签 0 表示未违约、1 表示违约。请求必须匹配自身 Schema。

## 结果验证

六个模型均已实际完成在线与异步批量预测。申请评分模型还参与副路由、实验和影子执行；多头借贷风险模型在调用后被删除，用于查看回收站及保留的历史调用。完整操作与统计见[Console 手册](console.md)，异步请求见[批量预测](batch-prediction.md)。
