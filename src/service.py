import json
import random
import bentoml
from bentoml.io import JSON
from datetime import datetime
from sqlalchemy import text
from src.config_parser import config
from src.db_engine import postgres_engine
from setup import setup_logger

logger = setup_logger()
svc = bentoml.Service("datamind")

# ======================================
# 加载模型 runners
# ======================================

MODEL_RUNNERS = {}

def load_all_models():
    """加载配置或 models 目录下所有模型（支持指定版本）"""
    for category, model_list in config.models.items():
        for m in model_list:
            model_name = m["model_name"]
            version = m.get("version", "latest")
            framework = m["framework"].lower()

            tag = f"{model_name}:{version}"
            try:
                if framework == "sklearn":
                    runner = bentoml.sklearn.get(tag).to_runner()
                elif framework == "xgboost":
                    runner = bentoml.xgboost.get(tag).to_runner()
                elif framework == "lightgbm":
                    runner = bentoml.lgbm.get(tag).to_runner()
                elif framework == "catboost":
                    runner = bentoml.catboost.get(tag).to_runner()
                else:
                    logger.warning(f"未知框架: {framework}，跳过模型 {model_name}")
                    continue

                MODEL_RUNNERS[tag] = runner
                svc.add_runner(runner)
                logger.info(f"[加载成功] 模型 {tag} ({framework})")

            except Exception as e:
                logger.exception(f"加载模型 {tag} 失败: {e}")

load_all_models()

# ======================================
# 数据库存储函数
# ======================================

def write_to_db(customer_id: str, workflow: str, req: dict, result: dict):
    """保存请求与结果"""
    try:

        sql = text("""
            INSERT INTO loan_requests (customer_id, workflow, request_data, result_data, created_at)
            VALUES (:cid, :workflow, :req, :res, :time)
        """)
        with postgres_engine.begin() as conn:
            conn.execute(sql, {
                "cid": customer_id,
                "workflow": workflow,
                "req": json.dumps(req, ensure_ascii=False),
                "res": json.dumps(result, ensure_ascii=False),
                "time": datetime.utcnow()
            })
    except Exception as e:
        logger.exception("写入数据库失败")


# ======================================
# 各阶段封装
# ======================================

async def rule_check(customer_id: str, features: list) -> dict:
    """规则引擎"""
    logger.info(f"[{customer_id}] 执行规则检查")
    passed = True  # 可替换为规则表达式引擎
    return {"step": "rule_check", "passed": passed}


async def fraud_check(customer_id: str, features: list, models: list) -> list:
    """欺诈检测"""
    results = []
    for model_name in models:
        runner = MODEL_RUNNERS.get(model_name)
        if not runner:
            logger.warning(f"未找到欺诈模型 {model_name}")
            continue
        score = await runner.async_run([features])
        results.append({
            "step": "fraud_check",
            "model": model_name,
            "score": float(score[0])
        })
    return results


async def model_scoring(customer_id: str, features: list, ab_models: list) -> dict:
    """模型评分 (A/B测试支持)"""
    chosen_model = random.choices(
        population=[m["model_name"] for m in ab_models],
        weights=[m["ab_test"].get("weight", 1.0) for m in ab_models],
        k=1
    )[0]
    runner = MODEL_RUNNERS.get(chosen_model)
    if not runner:
        return {"error": f"模型 {chosen_model} 未加载"}
    score = await runner.async_run([features])
    return {"step": "model_scoring", "model": chosen_model, "score": float(score[0])}


# ======================================
# 统一工作流执行函数
# ======================================

async def execute_workflow(req: dict) -> dict:
    customer_id = req["customer_id"]
    workflow_name = req["workflow"]
    features = req["features"]

    wf = config.workflows.get(workflow_name)
    if not wf:
        return {"error": f"未找到工作流 {workflow_name}"}

    result = {
        "customer_id": customer_id,
        "workflow": workflow_name,
        "steps": [],
        "timestamp": datetime.utcnow().isoformat()
    }

    for step in wf.get("workflow_steps", []):
        if not step.get("enabled", True):
            logger.info(f"[{workflow_name}] 跳过步骤 {step['step_name']}")
            continue

        step_name = step["step_name"]
        try:
            if step_name == "rule_check":
                step_result = await rule_check(customer_id, features)
                result["steps"].append(step_result)
                if not step_result["passed"]:
                    break

            elif step_name == "fraud_check":
                fraud_results = await fraud_check(customer_id, features, step.get("models", []))
                result["steps"].extend(fraud_results)

            elif step_name == "model_scoring":
                step_result = await model_scoring(customer_id, features, wf.get("models", []))
                result["steps"].append(step_result)

        except Exception as e:
            logger.exception(f"步骤 {step_name} 执行出错: {e}")
            result["steps"].append({"step": step_name, "error": str(e)})

    return result


# ======================================
# BentoML API 接口
# ======================================

@svc.api(input=JSON(), output=JSON())
async def predict_label(application: dict):
    """
    返回模型预测标签 (分类任务)
    """
    model_name = application.get("model_name")
    features = application.get("features")

    runner = MODEL_RUNNERS.get(model_name)
    if not runner:
        return {"error": f"模型 {model_name} 未加载"}

    preds = await runner.async_run([features])
    label = int(preds[0] > 0.5)  # 简单阈值分类，可根据实际修改
    return {"model": model_name, "label": label}


@svc.api(input=JSON(), output=JSON())
async def predict_proba(application: dict):
    """
    返回预测概率 (如信用评分或违约概率)
    """
    model_name = application.get("model_name")
    features = application.get("features")

    runner = MODEL_RUNNERS.get(model_name)
    if not runner:
        return {"error": f"模型 {model_name} 未加载"}

    proba = await runner.async_run([features])
    return {"model": model_name, "probability": float(proba[0])}


@svc.api(input=JSON(), output=JSON())
async def predict(application: dict):
    """
    贷款申请完整流程：规则检查 → 欺诈检测 → 模型评分
    """
    if not all(k in application for k in ("workflow", "customer_id", "features")):
        return {"error": "缺少必要字段：workflow / customer_id / features"}

    result = await execute_workflow(application)
    write_to_db(application["customer_id"], application["workflow"], application, result)
    return result
