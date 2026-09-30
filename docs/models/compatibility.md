# 兼容性与制品

注册前确认模型框架、算法标识与制品格式匹配，并安装对应框架依赖。

## 框架、算法与格式

| 框架 | 模型类型标识 | 注册文件后缀 |
| --- | --- | --- |
| sklearn | `logistic_regression`、`decision_tree`、`random_forest` | `.pkl`、`.pickle`、`.joblib` |
| xgboost | `xgboost` | `.json`、`.ubj`、`.model` |
| lightgbm | `lightgbm` | `.txt`、`.model` |
| catboost | `catboost` | `.cbm` |

注册时先检查文件后缀，再加载制品并提取模型信息。文件内容需要与声明的框架和任务匹配。

## 分类与评分

分类支持上述框架，当前推理语义为二分类。sklearn 与 CatBoost 的类别按模型 classes_ 顺序解释，第二个类别为正类。XGBoost/LightGBM 原生 Booster 示例使用 0/1，正类为 1。业务含义应与训练标签对应，不能仅凭模型名称推断正类是好客户或坏客户。评分任务使用 sklearn 框架下的 `optbinning.Scorecard`，以 `LogisticRegression` 为估计器，注册时使用 `--model-type logistic_regression --task-type scoring`。

评分卡输出包括违约概率、总评分与特征分，操作入口见[分类模型与评分卡指南](../guides/models.md)。

## 输入信息与依赖

注册服务提取有序特征名称、数量和来源。sklearn 优先使用 feature_names_in_，XGBoost 还读取 Booster 特征名，LightGBM 读取 feature_name，CatBoost 读取 feature_names_。评分卡从分箱过程提取输入字段。训练时使用带列名的数据，并确认保存再加载后仍保留名称。

```python
# sklearn / optbinning
import joblib
joblib.dump(model, "application_scorecard.pkl")
# XGBoost
model.save_model("multi_borrowing_risk.ubj")
# LightGBM 原生 Booster
booster.save_model("classification_model.txt")
# CatBoost
model.save_model("fraud_risk.cbm")
```

各片段使用已经训练好的对应对象，完整脚本见[示例索引](../examples/index.md)。`.pkl` 等文件实际由 joblib 加载，不要仅改扩展名伪装格式。加载会校验真实模型类型。没有可用特征名时 Schema 可能无法提取，不能据此推断请求任意字段或列顺序均可用，应重新训练/保存并检查注册后的 Schema。

## 依赖与兼容验证

当前依赖下限为 scikit-learn 1.6、XGBoost 2.0、LightGBM 4.0、CatBoost 1.2。optbinning 为 >=1.0,<2.0，准确约束来自 pyproject.toml。这些是安装声明，不是任意历史模型跨版本可加载的保证。训练和服务使用可兼容的依赖版本，并用对应框架测试、序列化往返与真实预测验证。

sklearn 分类支持 LogisticRegression、DecisionTreeClassifier、RandomForestClassifier。评分使用 optbinning.Scorecard 与 LogisticRegression 估计器。原生 Booster 与 sklearn wrapper 的加载行为因框架不同，应按仓库同框架示例选择对象及格式。

常见失败包括不支持的后缀、模型对象与声明算法不匹配、评分任务使用普通分类器、缺少可选依赖、特征名称缺失或请求列不匹配。先核对训练脚本、注册 Schema 和服务依赖，再检查 Runtime 加载错误。制品修订规则见[模型与版本](index.md)。
