#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
service.py

BentoML 模型服务定义文件。
支持分类模型的预测标签、预测概率等 API。
"""

import bentoml
import pandas as pd
from pathlib import Path
from src.config_parser import config  # ✅ 使用新的配置系统

# =========================
# 模型加载
# =========================

MODEL_NAME = "demo_loan_scorecard_cat_20250930"  # ✅ 指定模型名称
model_info = config.get_model(MODEL_NAME)

if not model_info:
    raise ValueError(f"未找到模型配置: {MODEL_NAME}")

model_name = model_info["model_name"]
model_version = model_info.get("version", "latest")
model_type = model_info.get("model_type", "sklearn")
model_path = Path(model_info.get("model_path", "")).as_posix()

print(f"[INFO] 加载模型配置: {model_name} ({model_type})")
print(f"[INFO] 模型路径: {model_path}")

# ✅ 从 BentoML 加载模型
model_ref = bentoml.models.get(f"{model_name}:{model_version}")
model_runner = model_ref.to_runner()

# =========================
# BentoML 服务定义
# =========================

svc = bentoml.Service(f"{model_name}_service", runners=[model_runner])

# ✅ /predict_label: 返回类别
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict_label(application: dict):
    df = pd.DataFrame([application])
    label = await model_runner.predict.async_run(df)
    return {"label": int(label[0])}

# ✅ /predict_proba: 返回违约概率
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict_proba(application: dict):
    df = pd.DataFrame([application])
    proba = await model_runner.predict_proba.async_run(df)
    return {"probability": float(proba[0, 1])}

# ✅ /predict: 同时返回类别与概率
@svc.api(input=bentoml.io.JSON(), output=bentoml.io.JSON())
async def predict(application: dict):
    df = pd.DataFrame([application])
    label = await model_runner.predict.async_run(df)
    proba = await model_runner.predict_proba.async_run(df)
    return {
        "label": int(label[0]),
        "probability": float(proba[0, 1])
    }
