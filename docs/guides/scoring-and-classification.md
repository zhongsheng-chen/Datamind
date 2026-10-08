# 评分与分类

本页介绍评分与分类任务的预测输入和结果。注册模型时，通过 `task_type` 指定任务类型；预测输入须与模型的训练特征一致。

| 任务             | 模型                                             | 结果                                   |
|------------------|--------------------------------------------------|----------------------------------------|
| `scoring`        | `optbinning.Scorecard`                           | 违约概率、信用评分、特征评分与阈值决策 |
| `classification` | sklearn / XGBoost / LightGBM / CatBoost 分类模型 | 类别、概率与阈值判断                   |

支持的模型与文件格式见[模型兼容性](../models/compatibility.md)。

## 使用评分卡

### 准备模型

按照[评分卡示例](../examples/index.md#评分卡示例)训练评分卡模型。从项目根目录执行以下命令，注册为 `scorecard-demo` 的 `1.0.0` 版本：

```bash
datamind model register scorecard-demo \
  --display-name "评分卡示例模型" \
  --version 1.0.0 \
  --model-path examples/scorecard/artifacts/scorecard_demo.pkl \
  --framework sklearn \
  --model-type logistic_regression \
  --task-type scoring
```

激活该版本：

```bash
datamind model activate scorecard-demo --version 1.0.0
```

按照[全量发布](../deployment/full.md)中的步骤创建并启用部署、配置路由和启动预测服务。确认运行实例状态为 `running` 后，即可按照[在线预测](online-prediction.md)中的步骤获取访问令牌并发起请求。

### 发起请求

调用 `/predict` 时，使用以下请求体。请求地址与认证方式见[在线预测](online-prediction.md)。

```json
{
  "request": {
    "model_name": "scorecard-demo",
    "subject_key": "borrower-001",
    "subject_type": "borrower",
    "features": {
      "age": 45,
      "annual_income": 240000,
      "debt_to_income_ratio": 0.1,
      "credit_utilization_ratio": 0.1,
      "delinquency_count": 0,
      "credit_history_years": 20,
      "employment_type": "salaried",
      "residence_status": "owner"
    }
  }
}
```

### 查看结果

请求成功后，接口返回响应：

```jsonc
{
  "success": true,
  "task_type": "scoring",
  "score": 680.1729095023757,
  "probability": 0.013002585872582427,
  "decision": "approve",
  "threshold": 600.0,
  "score_intercept": 0.0,
  "features": {
    "age": {
      "value": 45,
      "bin": "[40.00, 50.00)",
      "woe": 0.04071375518752225,
      "points": 66.28438957991956
    }
    // ... 为简洁起见，省略部分字段
  },
  "request_id": "req_374596385a614b3b"
}
```

`score` 表示信用评分，`probability` 表示违约概率。信用评分高于默认阈值 600，因此决策结果为 `approve`。特征结果中的 `bin`、`woe` 和 `points` 分别表示分箱、证据权重和特征评分。更多字段说明见[预测 API](../reference/runtime-api.md)。

## 使用分类模型

### 准备模型

按照[分类示例](../examples/index.md#分类示例)训练 CatBoost 模型。从项目根目录执行以下命令，注册为 `classification-demo` 的 `1.0.0` 版本：

```bash
datamind model register classification-demo \
  --display-name "分类示例模型" \
  --version 1.0.0 \
  --model-path examples/classification/catboost/artifacts/classification_demo.cbm \
  --framework catboost \
  --model-type catboost \
  --task-type classification
```

激活该版本：

```bash
datamind model activate classification-demo --version 1.0.0
```

按照[全量发布](../deployment/full.md)中的步骤创建并启用部署、配置路由和启动预测服务。确认运行实例状态为 `running` 后，即可按照[在线预测](online-prediction.md)中的步骤获取访问令牌并发起请求。

### 发起请求

调用 `/predict` 时，使用以下请求体。请求地址与认证方式见[在线预测](online-prediction.md)。

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

### 查看结果

请求成功后，接口返回响应：

```json
{
  "success": true,
  "task_type": "classification",
  "probability": 0.1418782784066073,
  "prediction": 0,
  "label": "benign",
  "threshold": 0.5,
  "request_id": "req_e99b080584f747e7"
}
```

`prediction` 表示预测类别，`probability` 表示预测概率。概率低于默认阈值 0.5，因此预测类别为 `0`，对应的类别标签为 `benign`。更多字段说明见[预测 API](../reference/runtime-api.md)。
