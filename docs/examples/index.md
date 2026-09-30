# 示例

训练脚本位于源码仓库的 `examples/`，请克隆仓库后从项目根目录运行。生成的制品可按[快速上手](../getting-started/quickstart.md)注册并发布。

## 银行场景示例

安装评分卡与分类模型所需依赖：

```bash
python -m pip install -e ".[sklearn,catboost,xgboost]"
```

三个评分模型使用同一评分卡示例，以不同随机种子训练。申请评分另准备 1.1.0 候选版本：

```bash
python examples/scorecard/train.py --random-seed 42 --n-jobs 1 \
  --output examples/scorecard/artifacts/application_scorecard.pkl
python examples/scorecard/train.py --random-seed 7 --n-jobs 1 \
  --output examples/scorecard/artifacts/application_scorecard_candidate.pkl
python examples/scorecard/train.py --random-seed 19 --n-jobs 1 \
  --output examples/scorecard/artifacts/behavior_scorecard.pkl
python examples/scorecard/train.py --random-seed 31 --n-jobs 1 \
  --output examples/scorecard/artifacts/collection_scorecard.pkl
```

三个分类模型分别使用 CatBoost、XGBoost 和随机森林示例：

```bash
python examples/classification/catboost/train.py \
  --output examples/classification/catboost/artifacts/fraud_risk.cbm
python examples/classification/xgboost/train.py \
  --output examples/classification/xgboost/artifacts/multi_borrowing_risk.ubj
python examples/classification/credit_risk/train.py \
  --output examples/classification/credit_risk/artifacts/default_probability.pkl
```

业务显示名称用于演示资源管理，训练数据与标签仍以各脚本为准。模型清单、注册参数和输入区别见[评分卡与分类模型](../guides/models.md)。

## 其他训练入口

| 任务 | 框架 | 脚本 |
| --- | --- | --- |
| 分类 | sklearn | `examples/classification/logistic_regression/train.py` |
| 分类 | sklearn | `examples/classification/decision_tree/train.py` |
| 分类 | sklearn | `examples/classification/random_forest/train.py` |
| 分类 | lightgbm | `examples/classification/lightgbm/train.py` |

这些脚本使用各自的特征和制品格式，不能仅替换文件名就混用输入。安装对应框架 extra，具体兼容边界见[模型兼容性](../models/compatibility.md)。

## 选择下一步

- 首次服务交付：[快速上手](../getting-started/quickstart.md)。
- 模型注册与任务区别：[使用指南](../guides/models.md)。
- 主、副、影子路由：[流量管理](../routing/index.md)。
- 版本比较：[A/B 测试](../experiments/index.md)。
- 实际操作和删除后的概览：[Console 手册](../guides/console.md)。
