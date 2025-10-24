import bentoml
from bentoml.io import JSON

# 假设 MLflow 注册模型
xgb_model = bentoml.mlflow.import_model(name="xgboost_credit_model", uri="models:/xgboost_credit_model/Production")
dtree_model = bentoml.mlflow.import_model(name="dtree_credit_model", uri="models:/dtree_credit_model/Production")
nn_model = bentoml.mlflow.import_model(name="nn_credit_model", uri="models:/nn_credit_model/Production")
lr_model = bentoml.mlflow.import_model(name="lr_credit_model", uri="models:/lr_credit_model/Production")

models = {
    "xgboost": xgb_model.to_runner(),
    "dtree": dtree_model.to_runner(),
    "nn": nn_model.to_runner(),
    "lr": lr_model.to_runner()
}
