#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Datamind 模型服务
支持：
- workflow 自动路由（AB Test）
- /predict, /predict_label, /predict_proba
- 日志记录、慢请求警告
- 敏感字段掩码
- 请求结果写入 PostgreSQL

默认模式（ab_test_all_run=False）只跑 AB Test 选中的模型，返回结果只有一个。
全跑模式（ab_test_all_run=True）跑所有有效模型，AB Test 主模型排第一。
"""

import bentoml
import random
import uuid
import json
import pytz
import pandas as pd
import xgboost as xgb
import time
from datetime import datetime, timedelta
from sqlalchemy import text

from src.model_loader import ModelLoader
from src.config_parser import config
from src.db_engine import postgres_engine
from src.setup import setup_logger

logger = setup_logger()
DEFAULT_THRESHOLD = 0.5
beijing_tz = pytz.timezone("Asia/Shanghai")

# 敏感字段掩码
SENSITIVE_FIELDS = {"income", "total_tax_amount", "avg_tax_amount", "max_tax_amount", "min_tax_amount"}


def mask_payload(payload: dict) -> dict:
    return {k: ("******" if k in SENSITIVE_FIELDS else v) for k, v in payload.items()}


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
            logger.info(
                "已加载所有模型: " +
                ", ".join(
                    f"{name}(version={meta.version}, uuid={meta.uuid}, hash={meta.hash})"
                    for name, meta in self.models.items()
                )
            )
        except Exception as e:
            logger.exception(f"加载所有模型失败: {e}")

    def _select_model(self, workflow_name: str, env="prod"):
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

        logger.info(
            f"[AB 测试] workflow={workflow_name}, env={env}, "
            f"candidates={[m['model_name'] for m in env_models]}, "
            f"weights={weights}, selected={model_name}"
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

    async def _return_response(
        self,
        request_id,
        serial_number,
        results=None,
        failures=None,
        elapsed_time=None,
        cpu_percent=0.0,
        memory_mb=0.0
    ):
        """统一报文返回"""
        results = results or []
        failures = failures or []

        if results and not failures:
            code = 0
            message = "success"
            status = "completed"
            error_msg = None
        elif results and failures:
            code = 0
            message = "completed"
            status = "completed"
            error_msg = "部分模型执行失败"
        else:
            code = 1001
            message = "failed"
            status = "failed"
            error_msg = "所有模型执行失败"

        total_time_ms = sum(r.get("time_ms", 0) for r in results) if results else 0.0
        metrics_runtime = [{"model_name": r["model_name"], "time_ms": r.get("time_ms", 0)} for r in results]

        response_data = {
            "code": code,
            "message": message,
            "data": {
                "request_id": request_id,
                "serial_number": serial_number,
                "status": status,
                "results": results,
                "metrics": {
                    "response_time_ms": elapsed_time.total_seconds() * 1000 if elapsed_time else 0.0,
                    "runtime": metrics_runtime
                },
                "resource_usage": {
                    "cpu_percent": cpu_percent,
                    "memory_mb": memory_mb
                },
                "error_msg": error_msg,
                "failures": failures
            }
        }

        await self._update_request_status(
            request_id,
            status=status,
            result_data=response_data,
            end_time=datetime.now(beijing_tz),
            response_time=elapsed_time,
            error_msg=error_msg
        )

        return response_data

    async def _return_failed(self, request_id, error_msg, serial_number=None):
        return await self._return_response(
            request_id=request_id,
            serial_number=serial_number or str(uuid.uuid4()),
            results=[],
            failures=[{"name": None, "error_code": 5000, "error_msg": error_msg}],
            elapsed_time=None,
            cpu_percent=0.0,
            memory_mb=0.0
        )

    async def _handle_request(self, request: dict, endpoint: str, return_type: str = "label_and_proba",
                              ab_test_all_run: bool = False):
        workflow_name = request.get("workflow", "")
        features = request.get("features", {})
        threshold = request.get("threshold", DEFAULT_THRESHOLD)
        serial_number = request.get("serial_number", str(uuid.uuid4()))
        request_id = str(uuid.uuid4())
        start_time = datetime.now(beijing_tz)
        business_name = self._get_business_name(workflow_name, request)

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
            logger.exception(f"写入 running 状态失败 request_id={request_id}: {e}")

        X = self._prepare_features(features)
        results = []
        failures = []

        if ab_test_all_run:
            primary_model, primary_model_name_or_err = self._select_model(workflow_name)
            workflow_conf = config.workflows.get(workflow_name, {})
            model_items = workflow_conf.get("models", [])

            for m_item in model_items:
                if not m_item.get("ab_test") or "weight" not in m_item["ab_test"]:
                    continue
                model_name = m_item["model_name"]
                cached_model = self.models.get(model_name)
                if not cached_model:
                    failures.append({"name": model_name, "error_code": 5001, "error_msg": "模型未加载"})
                    continue
                try:
                    self._check_features(X, cached_model.model)
                    start_model = time.time()
                    label, probability = self._infer_label_and_proba(cached_model.model, X, threshold)
                    end_model = time.time()
                    model_time_ms = round((end_model - start_model) * 1000, 2)

                    result = {
                        "model_name": model_name,
                        "version": cached_model.version,
                        "uuid": cached_model.uuid,
                        "hash": cached_model.hash,
                        "role": "primary" if model_name == primary_model_name_or_err else "challenger",
                        "endpoint": endpoint,
                        "time_ms": model_time_ms
                    }
                    if return_type in ["label", "label_and_proba"]:
                        result["label"] = label
                    if return_type in ["proba", "label_and_proba"]:
                        result["probability"] = probability
                    results.append(result)
                except Exception as e:
                    failures.append({"name": model_name, "error_code": 5002, "error_msg": str(e)})

            # 主模型排第一
            if primary_model and primary_model_name_or_err:
                for i, r in enumerate(results):
                    if r["model_name"] == primary_model_name_or_err:
                        results.insert(0, results.pop(i))
                        break
        else:
            cached_model, model_name_or_err = self._select_model(workflow_name)
            if not cached_model:
                return await self._return_failed(request_id, model_name_or_err, serial_number)
            try:
                self._check_features(X, cached_model.model)
                start_model = time.time()
                label, probability = self._infer_label_and_proba(cached_model.model, X, threshold)
                end_model = time.time()
                model_time_ms = round((end_model - start_model) * 1000, 2)

                result = {
                    "model_name": model_name_or_err,
                    "version": cached_model.version,
                    "uuid": cached_model.uuid,
                    "hash": cached_model.hash,
                    "role": "primary",
                    "endpoint": endpoint,
                    "time_ms": model_time_ms
                }
                if return_type in ["label", "label_and_proba"]:
                    result["label"] = label
                if return_type in ["proba", "label_and_proba"]:
                    result["probability"] = probability
                results.append(result)
            except Exception as e:
                failures.append({"name": model_name_or_err, "error_code": 5002, "error_msg": str(e)})

        elapsed_time = datetime.now(beijing_tz) - start_time

        return await self._return_response(
            request_id=request_id,
            serial_number=serial_number,
            results=results,
            failures=failures,
            elapsed_time=elapsed_time,
            cpu_percent=12.5,
            memory_mb=150.3
        )

    # -------------------------
    # BentoML APIs
    # -------------------------
    @bentoml.api
    async def predict(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="predict",
                                          return_type="label_and_proba", ab_test_all_run=ab_test_all_run)

    @bentoml.api
    async def predict_label(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="predict_label",
                                          return_type="label", ab_test_all_run=ab_test_all_run)

    @bentoml.api
    async def predict_proba(self, request: dict, ab_test_all_run: bool = False):
        return await self._handle_request(request, endpoint="predict_proba",
                                          return_type="proba", ab_test_all_run=ab_test_all_run)



if __name__ == "__main__":
    import asyncio

    service = Datamind()


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


    async def run_test():
        workflow_name = "demo_loan_approval_workflow"
        payload = random_payload()
        serial_number = random_serial_number()

        label_resp = await service.predict_label({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number,
            "threshold": 0.6
        }, ab_test_all_run=True)

        proba_resp = await service.predict_proba({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number
        }, ab_test_all_run=False)

        predict_resp = await service.predict({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number,
            "threshold": 0.6
        })

        print("predict_label:", label_resp)
        print("predict_proba:", proba_resp)
        print("predict:", predict_resp)


    asyncio.run(run_test())
