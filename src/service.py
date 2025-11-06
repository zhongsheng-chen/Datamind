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
"""

import bentoml
import random
import uuid
import json
import pytz
import pandas as pd
import xgboost as xgb
from datetime import datetime, timedelta
from sqlalchemy import text

from src.model_factory import ModelFactory
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


def write_request(serial_number, endpoint, workflow_name, business_name, model_name, request_data, result_data, status, start_time, end_time, response_time, error_message=None):
    try:
        sql = text("""
            INSERT INTO requests 
                (request_id, serial_number, endpoint, workflow_name, business_name, model_name, request_data, result_data, status, start_time, end_time, response_time, error_message, created_at)
            VALUES 
                (:request_id, :serial_number, :endpoint, :workflow_name, :business_name, :model_name, :request_data, :result_data, :status, :start_time, :end_time, :response_time, :error_message, :created_at)
        """)

        with postgres_engine.begin() as conn:
            conn.execute(sql, {
                "request_id": str(uuid.uuid4()),
                "serial_number": serial_number,
                "endpoint": endpoint,
                "workflow_name": workflow_name,
                "business_name": business_name,
                "model_name": model_name,
                "request_data": json.dumps(request_data, ensure_ascii=False),
                "result_data": json.dumps(result_data, ensure_ascii=False),
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
                "response_time": response_time,
                "error_message": error_message,
                "created_at": datetime.now(beijing_tz)
            })
    except Exception:
        logger.exception(f"写入数据库失败")


# -------------------------
# BentoML Service
# -------------------------
@bentoml.service(
    resources={"cpu": "8", "memory": "16G"},
    traffic={
        "timeout": 5,
        "max_concurrency": 20,
        "retry": 1,
        "retry_interval": 1
    }
)
class Datamind:
    def __init__(self) -> None:
        """初始化，调用 ModelFactory 加载所有模型"""
        self.models = {}
        self._load_all_models()

    def _load_all_models(self):
        """调用 ModelFactory 加载所有模型"""
        try:
            ModelFactory.load_all_models()  # 让 ModelFactory 负责加载所有模型
            self.models = ModelFactory._model_cache  # 获取 ModelFactory 中的模型缓存
            logger.info(f"已加载所有模型: {list(self.models.keys())}")
        except Exception as e:
            logger.exception(f"加载所有模型失败: {e}")

    def _select_model(self, workflow_name, env="prod", debug_logger=False):
        """根据 workflow 中 AB Test 权重和环境选择模型"""
        workflow_conf = config.workflows.get(workflow_name)
        if not workflow_conf:
            return None, f"workflow 未配置: {workflow_name}。请检查config/config.yaml"

        model_items = workflow_conf.get("models", [])
        if not model_items:
            return None, f"workflow {workflow_name} 的'models'节点未配置。请检查config/config.yaml"

        # 过滤掉没有 ab_test 或 weight 的模型
        valid_models = [
            m for m in model_items
            if m.get("ab_test") and "weight" in m["ab_test"]
        ]
        if not valid_models:
            return None, f"workflow {workflow_name} 没有有效的 AB 测试模型"

        # 根据当前环境过滤模型
        env_models = [
            m for m in valid_models
            if m["ab_test"].get("environment", "prod") == env
        ]
        if not env_models:
            logger.warning(f"[AB 测试] workflow=[{workflow_name}], env=[{env}] 没有可用模型")
            return None, f"workflow=[{workflow_name}] 在env=[{env}] 没有可用模型"

        # 按权重随机选择模型（权重确保为非负数）
        weights = [max(0, float(m["ab_test"]["weight"])) for m in env_models]
        selected_model_item = random.choices(env_models, weights=weights, k=1)[0]

        model_name = selected_model_item["model_name"]
        model = self.models.get(model_name)
        if not model:
            return None, f"模型 {model_name} 未加载"

        try:
            logger.info(
                f"[AB 测试] workflow={workflow_name}, env={env}, "
                f"candidates={[m['model_name'] for m in env_models]}, "
                f"weights={weights}, selected={model_name}"
            )
        except Exception as e:
            if debug_logger:
                logger.exception(f"[AB 测试] 日志记录失败: {e}")
            # 生产环境 debug_logger=False 时完全忽略

        return model, model_name

    def _infer_label_and_proba(self, model, df: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD):
        """
        预测类别及其概率。
        如果是二分类，返回 0 类或 1 类的概率。根据 threshold 来决定标签。
        如果是多分类， 返回最大概率的类别及其概率
        """
        # 如果模型有 predict_proba（sklearn, CatBoostClassifier）
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(df)

            if proba.shape[1] == 2:
                # 二分类问题：返回 0 类或 1 类的概率
                probability_0 = float(proba[0, 0])  # 0 类的概率
                probability_1 = float(proba[0, 1])  # 1 类的概率
                label = 1 if probability_1 >= threshold else 0
                probability = probability_1 if label == 1 else probability_0
            else:
                # 多分类问题：返回最大概率的类别及其概率
                probability = max(proba[0])  # 返回最大概率
                label = proba[0].tolist().index(probability)  # 找到概率最大的类别
        else:
            # XGBoost Booster
            if isinstance(model, xgb.Booster):
                dmatrix = xgb.DMatrix(df)
                proba = model.predict(dmatrix)
                probability = float(proba[0])
                label = 1 if probability >= threshold else 0
            else:  # LightGBM Booster
                proba = model.predict(df)
                probability = float(proba[0])
                label = 1 if probability >= threshold else 0

        return label, probability

    def _check_features(self, input_features, model):
        """检查输入特征是否与训练时使用的特征匹配"""
        missing_features = set(model.feature_names_in_) - set(input_features.columns)
        if missing_features:
            raise ValueError(f"特征缺失 {', '.join(missing_features)}")
        return True

    def _get_business_name(self, workflow_name: str, request: dict) -> str:
        """优先取 config 中 workflow 的 business_name，如果不存在则取 request 中的 business_name"""
        try:
            business_name = config.get_business_workflow(workflow_name).business_name
            if not business_name:
                business_name = request.get("business_name", "")
        except KeyError:
            business_name = request.get("business_name", "")
        return business_name

    def _prepare_features(self, features: dict) -> pd.DataFrame:
        """将请求中的 features 转为 DataFrame"""
        return pd.DataFrame([features])

    async def _update_request_status(self, request_id, status, result_data=None,
                                     end_time=None, response_time=None, error_msg=None):
        """
        更新请求状态，同时安全处理 None 值，避免写入数据库失败。
        """
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

            # 处理 None 值
            result_data_json = json.dumps(result_data, ensure_ascii=False) if result_data is not None else None
            end_time_val = end_time if end_time is not None else None
            response_time_val = response_time if isinstance(response_time, timedelta) else None
            error_msg_val = str(error_msg) if error_msg is not None else None

            with postgres_engine.begin() as conn:
                conn.execute(sql_update, {
                    "request_id": request_id,
                    "status": status,
                    "result_data": result_data_json,
                    "end_time": end_time_val,
                    "response_time": response_time_val,
                    "error_msg": error_msg_val,
                })
        except Exception as e:
            logger.exception(f"更新请求状态失败 request_id={request_id}: error={e}")

    async def _return_failed(self, request_id, error_msg, serial_number=None):
        """统一失败处理"""
        response_data = {
            "request_id": request_id,
            "status": "failed",
            "results": None,
            "metrics": None,
            "error_msg": error_msg
        }
        await self._update_request_status(
            request_id,
            status="failed",
            result_data=response_data,
            end_time=datetime.now(beijing_tz),
            response_time=None,
            error_msg=error_msg
        )
        if serial_number:
            logger.error(f"serial_number=[{serial_number}] {error_msg}")
        return response_data

    async def _handle_request(self, request: dict, endpoint: str, return_type: str = "label_and_proba"):
        workflow_name = request.get("workflow", "")
        features = request.get("features", {})
        threshold = request.get("threshold", DEFAULT_THRESHOLD)
        serial_number = request.get("serial_number", str(uuid.uuid4()))
        business_name = self._get_business_name(workflow_name, request)
        start_time = datetime.now(beijing_tz)
        request_id = str(uuid.uuid4())

        # 写入 running 状态略（和之前一样）

        elapsed = lambda: datetime.now(beijing_tz) - start_time

        # 校验 workflow
        if not workflow_name or not features:
            return await self._return_failed(request_id, "必须提供 workflow 和 features", serial_number)

        # -------- AB Test：只选一个模型 --------
        model, model_name_or_err = self._select_model(workflow_name)
        if not model:
            return await self._return_failed(request_id, model_name_or_err, serial_number)

        X = self._prepare_features(features)

        # 特征检查
        try:
            self._check_features(X, model)
        except ValueError as e:
            return await self._return_failed(request_id, str(e), serial_number)

        # 执行预测
        try:
            label, probability = self._infer_label_and_proba(model, X, threshold)
            elapsed_time = elapsed()

            result = {"model": model_name_or_err, "task_type": endpoint}
            if return_type in ["label", "label_and_proba"]:
                result["label"] = label
            if return_type in ["proba", "label_and_proba"]:
                result["probability"] = probability

            response_data = {
                "request_id": request_id,
                "serial_number": serial_number,
                "workflow": workflow_name,
                "endpoint": endpoint,
                "status": "completed",
                "results": [result],
                "metrics": {"response_time_ms": elapsed_time.total_seconds() * 1000},
                "error_msg": None
            }

            await self._update_request_status(
                request_id,
                status="completed",
                result_data=response_data,
                end_time=datetime.now(beijing_tz),
                response_time=elapsed_time
            )

            if elapsed_time.total_seconds() > 2.0:
                logger.warning(
                    f"serial_number=[{serial_number}] {workflow_name} -> {model_name_or_err} 慢请求: {elapsed_time.total_seconds():.4f}s")

            return response_data

        except Exception as e:
            return await self._return_failed(request_id, f"模型 {model_name_or_err} 执行失败: {str(e)}", serial_number)

    @bentoml.api
    async def predict(self, request: dict):
        return await self._handle_request(request, endpoint="predict", return_type="label_and_proba")

    @bentoml.api
    async def predict_label(self, request: dict):
        return await self._handle_request(request, endpoint="predict_label", return_type="label")

    @bentoml.api
    async def predict_proba(self, request: dict):
        return await self._handle_request(request, endpoint="predict_proba", return_type="proba")

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
        })

        proba_resp = await service.predict_proba({
            "workflow": workflow_name,
            "features": payload,
            "serial_number": serial_number
        })

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
