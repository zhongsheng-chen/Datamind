#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
service.py

分类模型服务示例
"""

import bentoml
import xgboost as xgb
import pandas as pd
import uuid
from time import time

from src.model_loader import ModelFactory
from src.logger import create_logger

logger = create_logger()

MODEL_NAME = "demo_loan_scorecard_lr_20250930"
DEFAULT_THRESHOLD = 0.5

# 敏感字段，需要在日志中掩码
SENSITIVE_FIELDS = {"income", "total_tax_amount", "avg_tax_amount", "max_tax_amount", "min_tax_amount"}

def mask_payload(payload: dict) -> dict:
    """对敏感字段进行掩码"""
    return {k: ("******" if k in SENSITIVE_FIELDS else v) for k, v in payload.items()}

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
        self.model = ModelFactory.load_model(MODEL_NAME)

    def _infer_label_and_proba(self, df: pd.DataFrame, threshold: float = DEFAULT_THRESHOLD):
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(df)
            label = (proba[:, 1] >= threshold).astype(int)
            probability = proba[0, 1]
        else:
            if isinstance(self.model, xgb.Booster):
                dmatrix = xgb.DMatrix(df)
                proba = self.model.predict(dmatrix)
            else:  # LightGBM Booster
                proba = self.model.predict(df)
            label = (proba >= threshold).astype(int)
            probability = proba[0]
        return int(label[0]), float(probability)

    @bentoml.api
    async def predict(self, request: dict) -> dict:
        request_id = str(uuid.uuid4())
        start_time = time()
        payload = request.get("payload")
        if not payload:
            logger.error(f"request_id=[{request_id}] Missing 'payload' in request")
            return {"error": "Missing 'payload' in request"}

        threshold = request.get("threshold", DEFAULT_THRESHOLD)
        df = pd.DataFrame([payload])

        try:
            label, probability = self._infer_label_and_proba(df, threshold)
            elapsed = time() - start_time
            masked = mask_payload(payload)
            logger.info(
                f"request_id=[{request_id}] predict: threshold={threshold}, "
                f"label={label}, probability={probability:.4f}, elapsed={elapsed:.4f}s, "
                f"payload={masked}"
            )
            if elapsed > 2.0:
                logger.warning(f"request_id=[{request_id}] slow request: elapsed={elapsed:.4f}s")
            return {"label": label, "probability": probability}
        except Exception as e:
            logger.exception(f"[{request_id}] predict failed: {e}")
            return {"error": str(e)}

    @bentoml.api
    async def predict_label(self, request: dict) -> dict:
        request_id = str(uuid.uuid4())
        start_time = time()
        payload = request.get("payload")
        if not payload:
            logger.error(f"request_id=[{request_id}] Missing 'payload' in request")
            return {"error": "Missing 'payload' in request"}

        threshold = request.get("threshold", DEFAULT_THRESHOLD)
        df = pd.DataFrame([payload])

        try:
            label, _ = self._infer_label_and_proba(df, threshold)
            elapsed = time() - start_time
            masked = mask_payload(payload)
            logger.info(
                f"request_id=[{request_id}] predict_label: threshold={threshold}, label={label}, "
                f"elapsed={elapsed:.4f}s, payload={masked}"
            )
            if elapsed > 2.0:
                logger.warning(f"[{request_id}] slow request: elapsed={elapsed:.4f}s")
            return {"label": label}
        except Exception as e:
            logger.exception(f"[{request_id}] predict_label failed: {e}")
            return {"error": str(e)}

    @bentoml.api
    async def predict_proba(self, request: dict) -> dict:
        request_id = str(uuid.uuid4())
        start_time = time()
        payload = request.get("payload")
        if not payload:
            logger.error(f"request_id=[{request_id}] Missing 'payload' in request")
            return {"error": "Missing 'payload' in request"}

        df = pd.DataFrame([payload])
        try:
            _, probability = self._infer_label_and_proba(df)
            elapsed = time() - start_time
            masked = mask_payload(payload)
            logger.info(
                f"request_id=[{request_id}] predict_proba: probability={probability:.4f}, "
                f"elapsed={elapsed:.4f}s, payload={masked}"
            )
            if elapsed > 2.0:
                logger.warning(f"[{request_id}] slow request: elapsed={elapsed:.4f}s")
            return {"probability": probability}
        except Exception as e:
            logger.exception(f"request_id=[{request_id}] predict_proba failed: {e}")
            return {"error": str(e)}


# =========================
# 🔹 本地调试入口
# =========================
if __name__ == "__main__":
    import asyncio

    payload = {
        "age": 35,
        "income": 12000,
        "debt_ratio": 0.3,
        "loan_amount": 5000,
        "existing_loans": 1,
        "total_tax_records": 5,
        "total_tax_amount": 2500,
        "avg_tax_amount": 500,
        "max_tax_amount": 800,
        "min_tax_amount": 200,
        "tax_amount_std": 150,
        "loan_to_income_ratio": 0.42,
        "existing_loans_ratio": 0.1,
    }

    service = Datamind()

    async def run_test():
        label = await service.predict_label({"payload": payload, "threshold": 0.6})
        proba = await service.predict_proba({"payload": payload})
        both = await service.predict({"payload": payload, "threshold": 0.6})
        print("predict_label:", label)
        print("predict_proba:", proba)
        print("predict:", both)

    asyncio.run(run_test())
