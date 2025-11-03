#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Datamind 模型服务（BentoML）

支持：
- 自动加载配置中的所有模型（或指定业务流程）
- 三个标准 BentoML API：
    - predict_label: 返回分类标签
    - predict_proba: 返回概率
    - predict: 执行完整贷款工作流（规则→欺诈→评分）
- 一个运维接口：
    - models: 查看模型加载状态
"""

import json
import random
from datetime import datetime

import bentoml
from bentoml.io import JSON
from sqlalchemy import text

from src.config_parser import config
from src.db_engine import postgres_engine
from setup import setup_logger

logger = setup_logger()
svc = bentoml.Service("datamind")

# ============================================================
# 模型加载逻辑
# ============================================================

MODEL_RUNNERS = {}
MODEL_STATUS = {}  # 记录加载状态


def load_models(workflow_name: str | None = None):
    """
    加载配置文件中定义的模型：
    - 若指定 workflow_name，则只加载该流程所需模型
    - 否则加载全部模型
    """
    try:
        if workflow_name:
            wf = config.get_business_workflow(workflow_name)
            models_to_load = wf.get_models()
            logger.info(f"[模型加载] 仅加载工作流 {workflow_name} 的模型")
        else:
            all_model_names = config.list_models(flatten=True)
            models_to_load = [config.get_model(name) for name in all_model_names if config.get_model(name)]
            logger.info("[模型加载] 加载全部配置模型")

        for model_conf in models_to_load:
            model_name = model_conf["model_name"]
            framework = model_conf.get("framework", "").lower()
            version = model_conf.get("version", "latest")
            tag = f"{model_name}:{version}"

            status = {"model": model_name, "framework": framework, "version": version, "loaded": False}

            try:
                # 根据框架加载模型
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
                    MODEL_STATUS[model_name] = status
                    continue

                MODEL_RUNNERS[model_name] = runner
                svc.add_runner(runner)
                status["loaded"] = True
                logger.info(f"[加载成功] 模型 {tag} ({framework})")

            except Exception as e:
                logger.exception(f"[加载失败] 模型 {tag}: {e}")

            MODEL_STATUS[model_name] = status

    except Exception as e:
        logger.exception(f"[模型加载异常] {e}")


# 启动时加载全部模型
load_models()


# ============================================================
# 数据库存储函数
# ============================================================

def write_to_db(serialno: str, workflow: str, request_data: dict, result: dict):
    """保存请求与结果"""
    try:
        sql = text("""
            INSERT INTO loan_requests (serialno, workflow, request_data, result_data, created_at)
            VALUES (:serialno, :workflow, :req, :res, :time)
        """)
        with postgres_engine.begin() as conn:
            conn.execute(sql, {
                "serialno": serialno,
                "workflow": workflow,
                "req": json.dumps(request_data, ensure_ascii=False),
                "res": json.dumps(result, ensure_ascii=False),
                "time": datetime.utcnow()
            })
    except Exception:
        logger.exception(f"[{serialno}] 写入数据库失败")


# ============================================================
# 各阶段封装
# ============================================================

async def rule_check(serialno: str, features: list) -> dict:
    """规则引擎检查"""
    logger.info(f"[{serialno}] 执行规则检查")
    passed = True  # 可扩展为真实规则引擎
    return {"step": "rule_check", "passed": passed}


async def fraud_check(serialno: str, features: list, models: list) -> list:
    """欺诈检测阶段"""
    results = []
    for model_name in models:
        runner = MODEL_RUNNERS.get(model_name)
        if not runner:
            logger.warning(f"[{serialno}] 未找到欺诈模型 {model_name}")
            continue
        try:
            score = await runner.async_run([features])
            results.append({
                "step": "fraud_check",
                "model": model_name,
                "score": float(score[0])
            })
        except Exception as e:
            logger.exception(f"[{serialno}] 欺诈模型 {model_name} 执行异常: {e}")
    return results


async def model_scoring(serialno: str, features: list, ab_models: list) -> dict:
    """模型评分阶段 (支持 A/B 测试)"""
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


# ============================================================
# 工作流执行函数
# ============================================================

async def execute_workflow(request_data: dict) -> dict:
    """执行工作流，包括规则检查、欺诈检测、模型评分"""
    serialno = request_data["serialno"]
    workflow_name = request_data["workflow"]
    features = request_data["features"]

    try:
        wf = config.get_business_workflow(workflow_name)
    except KeyError:
        return {"error": f"未找到工作流 {workflow_name}"}

    result = {
        "serialno": serialno,
        "workflow": workflow_name,
        "steps": [],
        "timestamp": datetime.utcnow().isoformat()
    }

    for step in wf.steps:
        if not step.enabled:
            logger.info(f"[{serialno}] 跳过步骤 {step.name}")
            continue

        try:
            if step.name == "rule_check":
                step_result = await rule_check(serialno, features)
                result["steps"].append(step_result)
                if not step_result["passed"]:
                    break

            elif step.name == "fraud_check":
                fraud_models = step.models or []
                fraud_results = await fraud_check(serialno, features, [m["model_name"] for m in fraud_models])
                result["steps"].extend(fraud_results)

            elif step.name == "model_scoring":
                step_result = await model_scoring(serialno, features, wf.models)
                result["steps"].append(step_result)

        except Exception as e:
            logger.exception(f"[{serialno}] 步骤 {step.name} 执行出错: {e}")
            result["steps"].append({"step": step.name, "error": str(e)})

    return result


# ============================================================
# BentoML API 接口
# ============================================================

@svc.api(input=JSON(), output=JSON())
async def predict_label(request_data: dict):
    """返回分类标签"""
    model_name = request_data.get("model_name")
    features = request_data.get("features")
    serialno = request_data.get("serialno", "unknown")

    runner = MODEL_RUNNERS.get(model_name)
    if not runner:
        return {"error": f"模型 {model_name} 未加载"}

    try:
        preds = await runner.async_run([features])
        label = int(preds[0] > 0.5)
        logger.info(f"[{serialno}] 模型 {model_name} 输出标签 {label}")
        return {"model": model_name, "label": label}
    except Exception as e:
        logger.exception(f"[{serialno}] 模型 {model_name} 预测失败: {e}")
        return {"error": f"模型 {model_name} 执行失败"}


@svc.api(input=JSON(), output=JSON())
async def predict_proba(request_data: dict):
    """返回预测概率"""
    model_name = request_data.get("model_name")
    features = request_data.get("features")
    serialno = request_data.get("serialno", "unknown")

    runner = MODEL_RUNNERS.get(model_name)
    if not runner:
        return {"error": f"模型 {model_name} 未加载"}

    try:
        proba = await runner.async_run([features])
        prob = float(proba[0])
        logger.info(f"[{serialno}] 模型 {model_name} 输出概率 {prob:.4f}")
        return {"model": model_name, "probability": prob}
    except Exception as e:
        logger.exception(f"[{serialno}] 模型 {model_name} 概率预测失败: {e}")
        return {"error": f"模型 {model_name} 执行失败"}


@svc.api(input=JSON(), output=JSON())
async def predict(request_data: dict):
    """执行完整贷款申请流程"""
    required_fields = ("workflow", "serialno", "features")
    if not all(k in request_data for k in required_fields):
        return {"error": "缺少必要字段：workflow / serialno / features"}

    serialno = request_data["serialno"]
    workflow = request_data["workflow"]

    logger.info(f"[{serialno}] 开始执行工作流 {workflow}")
    result = await execute_workflow(request_data)
    write_to_db(serialno, workflow, request_data, result)
    logger.info(f"[{serialno}] 工作流 {workflow} 执行完成")

    return result


# ============================================================
# 模型状态查询接口
# ============================================================

@svc.api(input=JSON(), output=JSON())
async def check_health(_: dict = None):
    """返回当前已加载的模型状态"""
    summary = list(MODEL_STATUS.values())
    return {
        "status": "ok" if all(m["loaded"] for m in summary) else "partial",
        "count": len(summary),
        "models": summary
    }

if __name__ == "__main__":
    req = {"serialno": "A001", "model_name": "demo_lr", "features": [0.5, 0.3, 0.8]}
    print(predict_label.sync_dantic(req))
