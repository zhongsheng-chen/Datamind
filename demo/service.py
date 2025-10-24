import bentoml
import pandas as pd
from src.utils import get_model_info

business_name = "personal_loan"
model_info = get_model_info(business_name)
model_name = model_info["model_name"]
model_version = model_info["model_version"]

# 加载模型
model_ref = bentoml.sklearn.get(f"{model_name}:{model_version}")
model_runner = model_ref.to_runner()

svc = bentoml.Service("personal_loan_scorecard_service", runners=[model_runner])

# 定义 API: /predict_label, 仅返回预测的类别
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict_label(application: dict):
    """
    输入: JSON 格式特征
    输出: 预测类别
    """
    df = pd.DataFrame([application])
    label = await model_runner.predict.async_run(df)
    return {"label": int(label[0])}

# 定义 API: /predict_probability, 仅返回预测的类别概率
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict_probability(application: dict):
    """
    输入: JSON 格式特征
    输出: 违约概率
    """
    df = pd.DataFrame([application])
    prob = await model_runner.predict_proba.async_run(df)
    return {"probability": float(prob[0, 1])}

# 定义 API: /predict, 仅返回预测的类别及其概率
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict(application: dict):
    """
    输入: JSON 格式特征
    输出: 预测标签和违约概率
    """
    df = pd.DataFrame([application])
    label = await model_runner.predict.async_run(df)
    prob = await model_runner.predict_proba.async_run(df)

    return {
        "label": int(label[0]),
        "probability": float(prob[0, 1])
    }
