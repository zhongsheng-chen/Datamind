#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Datamind 模型服务
支持：
- workflow 自动路由（AB Test）
- /predict, /predict_label, /predict_proba, /predict_score
- 日志记录、慢请求警告
- 敏感字段掩码
- 请求结果写入 PostgreSQL
"""

import bentoml
import random
import uuid
import json
import pytz
import pandas as pd
import xgboost as xgb
import psutil
from datetime import datetime, timedelta
from sqlalchemy import text
from collections import OrderedDict

from src.model_loader import ModelLoader
from src.config_parser import config
from src.db_engine import postgres_engine
from src.logger import get_logger
from src.scoring import ScoreTransformer as ST

logger = get_logger()
beijing_tz = pytz.timezone("Asia/Shanghai")

DEFAULT_THRESHOLD = 0.5
DEFAULT_BASE_SCORE = 600
DEFAULT_PDO = 50
_EPS = 1e-6
SENSITIVE_FIELDS = {"income", "total_tax_amount", "avg_tax_amount", "max_tax_amount", "min_tax_amount"}

# -------------------------
# 工具函数
# -------------------------
def mask_payload(payload: dict) -> dict:
    return {k: ("******" if k in SENSITIVE_FIELDS else v) for k, v in payload.items()}

def summarize_results(results: list) -> str:
    """
    将模型结果提炼为简洁字符串
    支持 label/probability/score 信息
    输出示例:
      "modelA role=primary status=success label=1 probability=0.87; modelB role=challenger status=failed"
    """
    lines = []
    for r in results:
        parts = [
            r.get("model_name", ""),
            f"role={r.get('role', '')}",
            f"status={r.get('status', '')}"
        ]
        if "label" in r:
            parts.append(f"label={r['label']}")
        if "probability" in r:
            parts.append(f"probability={r['probability']:.4f}")
        if "score" in r:
            parts.append(f"score={r['score']}")
        lines.append(" ".join(parts))
    return "; ".join(lines)

def summarize_features(features: dict, n=3) -> str:
    """
    返回前 n 个 key:value 的特征，敏感字段已掩码，并显示未展示特征数量
    """
    masked = mask_payload(features)
    items = list(masked.items())
    displayed_items = items[:n]
    omitted_count = max(0, len(items) - n)
    summary = ", ".join(f"{k}={v}" for k, v in displayed_items)
    if omitted_count > 0:
        summary += f", ...(+{omitted_count} more)"
    return summary

# -------------------------
# 日志函数
# -------------------------
def log_info(request_id, msg, **kwargs):
    logger.info(f"[request_id={request_id}] {msg} | {json.dumps(kwargs, ensure_ascii=False)}")

def log_warning(request_id, msg, **kwargs):
    logger.warning(f"[request_id={request_id}] {msg} | {json.dumps(kwargs, ensure_ascii=False)}")

def log_error(request_id, msg, **kwargs):
    logger.error(f"[request_id={request_id}] {msg} | {json.dumps(kwargs, ensure_ascii=False)}")


@bentoml.service(
    resources={"cpu": "8", "memory": "16G"},
    traffic={"timeout": 5, "max_concurrency": 20, "retry": 1, "retry_interval": 1}
)
class Datamind:
    def __init__(self) -> None:
        """初始化，加载所有模型"""
        self.models = {}
        self._load_all_models()

    def _load_all_models(self):
        """调用 ModelLoader 加载所有模型"""
        try:
            ModelLoader.load_all_models()
            self.models = ModelLoader._model_cache
            if not self.models:
                logger.error("所有模型加载失败，模型缓存为空")
            else:
                logger.debug(
                    "已加载模型: " +
                    ", ".join(
                        f"{name}(version={meta.version}, uuid={meta.uuid}, hash={meta.hash})"
                        for name, meta in self.models.items()
                    )
                )
        except Exception as e:
            logger.exception(f"加载模型失败: {e}")
            self.models = {}

    def _select_model(self, workflow_name: str, env="prod", request_id=None):
        """根据 AB Test 权重选择主模型"""
        workflow_conf = config.workflows.get(workflow_name)
        if not workflow_conf:
            return None, f"workflow 未配置: {workflow_name}"

        model_items = workflow_conf.get("models", [])
        valid_models = [m for m in model_items if m.get("ab_test") and "weight" in m["ab_test"]]
        env_models = [m for m in valid_models if m["ab_test"].get("environment", "prod") == env]

        if not env_models:
            return None, f"workflow=[{workflow_name}] 在env=[{env}] 没有可用模型"

        weights = [max(0, float(m["ab_test"]["weight"])) for m in env_models]
        selected_item = random.choices(env_models, weights=weights, k=1)[0]

        model_name = selected_item["model_name"]
        cached_model = self.models.get(model_name)
        if not cached_model:
            return None, f"模型 {model_name} 未加载"

        log_info(
            request_id,
            "AB 测试",
            candidates=[m['model_name'] for m in env_models],
            selected=model_name
        )

        return cached_model, model_name

    def _infer_label_and_proba(self, model_obj, df: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD):
        """预测类别及概率"""
        if hasattr(model_obj, "predict_proba"):
            proba = model_obj.predict_proba(df)
            if proba.shape[1] == 2:
                p0, p1 = float(proba[0, 0]), float(proba[0, 1])
                label = 1 if p1 >= threshold else 0
                probability = p1 if label == 1 else p0
            else:
                probability = max(proba[0])
                label = proba[0].tolist().index(probability)
        else:
            if isinstance(model_obj, xgb.Booster):
                dmatrix = xgb.DMatrix(df)
                proba = model_obj.predict(dmatrix)
                probability = float(proba[0])
                label = 1 if probability >= threshold else 0
            else:
                proba = model_obj.predict(df)
                probability = float(proba[0])
                label = 1 if probability >= threshold else 0
        return label, probability

    def _check_features(self, df: pd.DataFrame, model_obj):
        missing = set(model_obj.feature_names_in_) - set(df.columns)
        if missing:
            raise ValueError(f"特征缺失: {', '.join(missing)}")
        return True

    def _prepare_features(self, features: dict) -> pd.DataFrame:
        return pd.DataFrame([features])

    def _get_business_name(self, workflow_name: str, request: dict) -> str:
        try:
            business_name = config.get_business_workflow(workflow_name).business_name
            if not business_name:
                business_name = request.get("business_name", "")
        except KeyError:
            business_name = request.get("business_name", "")
        return business_name

    async def _update_request_status(self, request_id, status, result_data=None,
                                     end_time=None, response_time=None, error_msg=None):
        try:
            sql_update = text("""
                UPDATE requests
                SET status        = :status,
                    result_data   = :result_data,
                    end_time      = :end_time,
                    response_time = :response_time,
                    error_msg     = :error_msg
                WHERE request_id = :request_id
            """)
            result_json = json.dumps(result_data, ensure_ascii=False) if result_data else None
            response_time_ms = response_time.total_seconds() * 1000 if isinstance(response_time, timedelta) else None
            with postgres_engine.begin() as conn:
                conn.execute(sql_update, {
                    "request_id": request_id,
                    "status": status,
                    "result_data": result_json,
                    "end_time": end_time,
                    "response_time": response_time_ms,
                    "error_msg": str(error_msg) if error_msg else None,
                })
        except Exception as e:
            logger.exception(f"更新请求状态失败 request_id={request_id}: {e}")

    def make_response(self, results=None, failures=None, request_id=None, serial_number=None,
                      workflow_name="", endpoint="", runtime=None, elapsed_time=None,
                      cpu_percent=0.0, memory_mb=0.0):
        """
        根据失败类型统一返回错误码
        """
        if results:
            code = 0
            message = "SUCCESS"
            status = "completed"
            error_msg = None
        elif failures:
            first_error = failures[0].get("error", "")
            if "workflow 未配置" in first_error:
                code = 1002
                message = "WORKFLOW_NOT_FOUND"
            elif "未加载" in first_error:
                code = 1003
                message = "MODEL_NOT_LOADED"
            elif "特征缺失" in first_error:
                code = 1004
                message = "FEATURE_MISSING"
            elif "predict" in first_error.lower() or "异常" in first_error:
                code = 1005
                message = "MODEL_PREDICT_ERROR"
            elif "非法" in first_error.lower():
                code = 1006
                message = "INVALID_REQUEST"
            elif "超时" in first_error.lower():
                code = 1007
                message = "TIMEOUT"
            elif "资源" in first_error.lower():
                code = 1008
                message = "RESOURCE_LIMIT"
            else:
                code = 1001
                message = "ALL_MODELS_FAILED"
            status = "failed"
            error_msg = first_error
        else:
            code = 1000
            message = "UNKNOWN_ERROR"
            status = "failed"
            error_msg = "未知错误"

        return OrderedDict([
            ("code", code),
            ("message", message),
            ("data", OrderedDict([
                ("request_id", request_id),
                ("serial_number", serial_number),
                ("workflow", workflow_name),
                ("endpoint", endpoint),
                ("status", status),
                ("results", results or []),
                ("metrics", OrderedDict([
                    ("response_time_ms", elapsed_time.total_seconds() * 1000 if elapsed_time else None),
                    ("runtime", runtime or [])
                ])),
                ("resource_usage", OrderedDict([
                    ("cpu_percent", cpu_percent),
                    ("memory_mb", memory_mb)
                ])),
                ("error_msg", error_msg),
                ("failures", failures or [])
            ]))
        ])

    async def _handle_request(self, request: dict, endpoint: str, return_type: str = "label_and_proba",
                              ab_test_all_run: bool = False):
        workflow_name = request.get("workflow", "")
        features = request.get("features", {})
        threshold = request.get("threshold", DEFAULT_THRESHOLD)
        serial_number = request.get("serial_number", "")
        ab_test_all_run = request.get("ab_test_all_run", ab_test_all_run)
        request_id = str(uuid.uuid4())
        start_time = datetime.now(beijing_tz)
        business_name = self._get_business_name(workflow_name, request)

        log_info(request_id,
                 f"收到请求",
                 features=summarize_features(mask_payload(features), n=3),
                 threshold=threshold,
                 serial_number=serial_number,
                 ab_test_all_run=ab_test_all_run,
                 endpoint=endpoint)

        # 写入 running 状态
        try:
            sql_insert = text("""
                INSERT INTO requests
                (request_id, serial_number, endpoint, workflow_name, business_name, model_name,
                 request_data, status, start_time, created_at)
                VALUES (:request_id, :serial_number, :endpoint, :workflow_name, :business_name,
                        :model_name, :request_data, 'running', :start_time, :created_at)
            """)
            with postgres_engine.begin() as conn:
                conn.execute(sql_insert, {
                    "request_id": request_id,
                    "serial_number": serial_number,
                    "endpoint": endpoint,
                    "workflow_name": workflow_name,
                    "business_name": business_name,
                    "model_name": "",
                    "request_data": json.dumps(request, ensure_ascii=False),
                    "start_time": start_time,
                    "created_at": start_time
                })
        except Exception as e:
            log_error(request_id, "写入 running 状态失败", error=str(e))

        X = self._prepare_features(features)
        results = []
        failures = []
        runtime = []

        try:
            if ab_test_all_run:
                primary_model, primary_model_name_or_err = self._select_model(workflow_name, request_id=request_id)
                workflow_conf = config.workflows.get(workflow_name, {})
                model_items = workflow_conf.get("models", [])

                for m_item in model_items:
                    if not m_item.get("ab_test") or "weight" not in m_item["ab_test"]:
                        continue
                    model_name = m_item["model_name"]
                    cached_model = self.models.get(model_name)
                    if not cached_model:
                        failures.append({
                            "model_name": model_name,
                            "endpoint": endpoint,
                            "error": f"模型 {model_name} 未加载",
                            "status": "failed",
                            "model_timer_start": None,
                            "model_timer_end": None,
                            "model_timer_ms": 0
                        })
                        continue

                    model_timer_start = datetime.now(beijing_tz)
                    try:
                        self._check_features(X, cached_model.model)
                        label, probability = self._infer_label_and_proba(cached_model.model, X, threshold)
                        model_timer_end = datetime.now(beijing_tz)
                        model_timer_ms = (model_timer_end - model_timer_start).total_seconds() * 1000

                        result = {
                            "model_name": model_name,
                            "version": cached_model.version,
                            "uuid": cached_model.uuid,
                            "hash": cached_model.hash,
                            "endpoint": endpoint,
                            "role": "primary" if model_name == primary_model_name_or_err else "challenger",
                            "status": "success",
                            "model_timer_start": model_timer_start.isoformat(),
                            "model_timer_end": model_timer_end.isoformat(),
                            "model_timer_ms": model_timer_ms
                        }
                        if return_type in ["label", "label_and_proba"]:
                            result["label"] = label
                            result["probability"] = probability
                            result["threshold"] = threshold
                        if return_type in ["proba", "label_and_proba"]:
                            result["probability"] = probability
                        if return_type == "score":
                            base_score, pdo, min_score, max_score, direction = ST._extract_params(request)
                            result["score"] = ST.probability_to_score(probability, request)
                            result["scoring_params"] = {
                                "base_score": base_score,
                                "pdo": pdo,
                                "min_score": min_score,
                                "max_score": max_score,
                                "direction": direction,
                                "label": label,
                                "probability": probability,
                                "threshold": threshold,
                            }

                        results.append(result)
                        runtime.append(result.copy())
                    except Exception as e:
                        model_timer_end = datetime.now(beijing_tz)
                        model_timer_ms = (model_timer_end - model_timer_start).total_seconds() * 1000
                        failures.append({
                            "model_name": model_name,
                            "endpoint": endpoint,
                            "error": str(e),
                            "status": "failed",
                            "model_timer_start": model_timer_start.isoformat(),
                            "model_timer_end": model_timer_end.isoformat(),
                            "model_timer_ms": model_timer_ms
                        })
                        runtime.append(failures[-1].copy())
            else:
                cached_model, model_name_or_err = self._select_model(workflow_name, request_id=request_id)
                if not cached_model:
                    failures.append({
                        "model_name": model_name_or_err,
                        "endpoint": endpoint,
                        "error": model_name_or_err,
                        "status": "failed",
                        "model_timer_start": None,
                        "model_timer_end": None,
                        "model_timer_ms": 0
                    })
                else:
                    model_timer_start = datetime.now(beijing_tz)
                    try:
                        self._check_features(X, cached_model.model)
                        label, probability = self._infer_label_and_proba(cached_model.model, X, threshold)
                        model_timer_end = datetime.now(beijing_tz)
                        model_timer_ms = (model_timer_end - model_timer_start).total_seconds() * 1000

                        result = {
                            "model_name": model_name_or_err,
                            "version": cached_model.version,
                            "uuid": cached_model.uuid,
                            "hash": cached_model.hash,
                            "endpoint": endpoint,
                            "role": "primary",
                            "status": "success",
                            "model_timer_start": model_timer_start.isoformat(),
                            "model_timer_end": model_timer_end.isoformat(),
                            "model_timer_ms": model_timer_ms
                        }
                        if return_type in ["label", "label_and_proba"]:
                            result["label"] = label
                            result["probability"] = probability
                            result["threshold"] = threshold
                        if return_type in ["proba", "label_and_proba"]:
                            result["probability"] = probability
                        if return_type == "score":
                            base_score, pdo, min_score, max_score, direction = ST._extract_params(request)
                            result["score"] = ST.probability_to_score(probability, request)
                            result["scoring_params"] = {
                                "base_score": base_score,
                                "pdo": pdo,
                                "min_score": min_score,
                                "max_score": max_score,
                                "direction": direction,
                                "label": label,
                                "probability": probability,
                                "threshold": threshold,
                            }

                        results.append(result)
                        runtime.append(result.copy())
                    except Exception as e:
                        model_timer_end = datetime.now(beijing_tz)
                        model_timer_ms = (model_timer_end - model_timer_start).total_seconds() * 1000
                        failures.append({
                            "model_name": model_name_or_err,
                            "endpoint": endpoint,
                            "error": str(e),
                            "status": "failed",
                            "model_timer_start": model_timer_start.isoformat(),
                            "model_timer_end": model_timer_end.isoformat(),
                            "model_timer_ms": model_timer_ms
                        })
                        runtime.append(failures[-1].copy())
        except Exception as e:
            failures.append({
                "model_name": "",
                "endpoint": endpoint,
                "error": str(e),
                "status": "failed",
                "model_timer_start": None,
                "model_timer_end": None,
                "model_timer_ms": 0
            })

        elapsed_time = datetime.now(beijing_tz) - start_time
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_mb = psutil.Process().memory_info().rss / 1024 / 1024

        response_data = self.make_response(
            results=results,
            failures=failures,
            request_id=request_id,
            serial_number=serial_number,
            workflow_name=workflow_name,
            endpoint=endpoint,
            runtime=runtime,
            elapsed_time=elapsed_time,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb
        )

        await self._update_request_status(
            request_id,
            status=response_data["data"]["status"],
            result_data=response_data,
            end_time=datetime.now(beijing_tz),
            response_time=elapsed_time,
            error_msg=response_data["data"]["error_msg"]
        )

        if elapsed_time.total_seconds() > 2.0:
            log_warning(request_id, f"{workflow_name} 慢请求", elapsed_seconds=elapsed_time.total_seconds())

        log_info(request_id,
                 f"请求完成",
                 status=response_data["data"]["status"],
                 results_summary=summarize_results(response_data["data"].get("results", [])))

        return dict(response_data)

    # -------------------------
    # BentoML APIs
    # -------------------------
    @bentoml.api
    async def predict(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="/predict",
                                          return_type="label_and_proba", ab_test_all_run=ab_test_all_run)

    @bentoml.api
    async def predict_label(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="/predict_label",
                                          return_type="label", ab_test_all_run=ab_test_all_run)

    @bentoml.api
    async def predict_proba(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="/predict_proba",
                                          return_type="proba", ab_test_all_run=ab_test_all_run)

    @bentoml.api
    async def predict_score(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="predict_score",
                                          return_type="score", ab_test_all_run=ab_test_all_run)


if __name__ == "__main__":
    import asyncio

    service = Datamind()

    async def run_test():
        def random_payload():
            return {
                "age": random.randint(18, 65),
                "income": random.randint(3000, 20000),
                "debt_ratio": round(random.uniform(0, 1), 2),
                "loan_amount": random.randint(1000, 10000),
                "existing_loans": random.randint(0, 5),
                "total_tax_records": random.randint(0, 10),
                "total_tax_amount": random.randint(0, 10000),
                "avg_tax_amount": random.randint(0, 3000),
                "max_tax_amount": random.randint(100, 2000),
                "min_tax_amount": random.randint(50, 1000),
                "tax_amount_std": round(random.uniform(0, 500), 2),
                "loan_to_income_ratio": round(random.uniform(0, 1), 2),
                "existing_loans_ratio": round(random.uniform(0, 1), 2),
            }

        def random_serial_number(length=15):
            import string
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

        workflow_name = "demo_loan_approval_workflow"
        payload = random_payload()
        serial_number = random_serial_number()

        label_resp = await service.predict_label({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number,
            "threshold": 0.56
        }, ab_test_all_run=True)

        proba_resp = await service.predict_proba({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number
        }, ab_test_all_run=False)

        score_resp = await service.predict_score({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number
        }, ab_test_all_run=True)

        predict_resp = await service.predict({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number,
            "threshold": 0.65
        })

        print(json.dumps(label_resp, ensure_ascii=False, indent=2))
        print(json.dumps(proba_resp, ensure_ascii=False, indent=2))
        print(json.dumps(score_resp, ensure_ascii=False, indent=2))
        print(json.dumps(predict_resp, ensure_ascii=False, indent=2))

    asyncio.run(run_test())
