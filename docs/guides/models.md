# 分类与评分

注册模型时，通过 `task_type` 指定任务语义。评分任务使用评分卡，分类任务使用二分类模型，两者的输入取决于训练特征，输出结构也不同。

| 任务 | 典型对象 | 结果 |
| --- | --- | --- |
| `scoring` | `optbinning.Scorecard` | 概率、信用分、特征评分与阈值决策 |
| `classification` | sklearn / XGBoost / LightGBM / CatBoost 分类模型 | 类别、概率与阈值判断 |

## 使用评分卡

评分卡示例使用合成信贷特征，标签表示违约结果。跟随[快速上手](../getting-started/quickstart.md)注册 `scorecard-demo`，使用如下特征调用 `/predict`：

```json
{
  "request": {
    "model_name": "scorecard-demo",
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

响应中的 `probability` 表示违约概率，`score` 表示总评分，特征结果包含 `bin`、`woe` 和 `points`。`decision` 按评分阈值生成，默认阈值为 600。它表达模型判断，实际审批由业务系统处理。

## 使用分类模型

以 CatBoost 示例为例，训练并注册一个独立模型：

```bash
python -m pip install -e '.[catboost]'
python examples/classification/catboost/train.py \
  --output examples/classification/catboost/artifacts/classification_demo.cbm

datamind model register classification-demo \
  --display-name "分类示例模型" \
  --version 1.0.0 \
  --model-path examples/classification/catboost/artifacts/classification_demo.cbm \
  --framework catboost --model-type catboost --task-type classification
```

随后按[全量发布](../deployment/full.md)激活版本、创建部署并启用路由，将命令中的模型名替换为 `classification-demo`，路由名使用 `classification-demo-main`。

该脚本使用 `make_classification` 生成连续数值，并将两类标记为 `benign` / `fraudulent`。字段名称用于演示输入结构，数值没有真实交易金额、小时或距离的业务单位。

```json
{
  "request": {
    "model_name": "classification-demo",
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

分类响应包含 `probability`、`prediction`、`label` 和 `threshold`，默认概率阈值为 0.5。它不包含评分卡的分箱与特征分。训练入口见[模型训练](../examples/index.md)，支持的对象与格式见[模型兼容性](../models/compatibility.md)。
