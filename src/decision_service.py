import bentoml
from bentoml.io import JSON
from feature_engineering import get_features
from rule_engine import get_rules, apply_rules
from model_service import models
from .db_engine import postgres_engine
import pandas as pd

svc = bentoml.Service("risk_service", runners=list(models.values()))

@svc.api(input=JSON(), output=JSON())
async def decision_api(input_json):
    application_id = input_json["application_id"]
    business_type = input_json["business_type"]
    model_type = input_json.get("model_type", "xgboost")

    # 初筛规则
    rules = get_rules(business_type)
    features_df = get_features([application_id])
    row = features_df.iloc[0].to_dict()
    pass_rule, reason = apply_rules(rules, row)

    # 模型推理
    if not pass_rule:
        final_decision = "reject"
        probability_of_default = None
    else:
        model_runner = models[model_type]
        pred = await model_runner.predict.async_run(features_df)
        probability_of_default = float(pred[0])
        final_decision = "approve" if probability_of_default < 0.5 else "manual_review"

    # 写入本地数据库
    result_df = pd.DataFrame([{
        "application_id": application_id,
        "business_type": business_type,
        "features": str(row),
        "probability_of_default": probability_of_default,
        "final_decision": final_decision
    }])
    result_df.to_sql("decision_results", postgres_engine, if_exists="append", index=False)

    return {
        "application_id": application_id,
        "final_decision": final_decision,
        "probability_of_default": probability_of_default,
        "rule_pass": pass_rule,
        "rule_reason": reason
    }
