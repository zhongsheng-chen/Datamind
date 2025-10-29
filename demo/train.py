#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
train.py

训练一个演示模型。
支持 Decision Tree, Random Forest, XGBoost, LightGBM, CatBoost, Logistic Regression。
通过 config.yaml 的模型定义自动加载模型配置与特征信息。。
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report
import joblib
import pickle

from src.config_parser import config
from src.db_engine import oracle_engine

# ------------------------------
# 日志配置
# ------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ------------------------------
# 获取模型信息
# ------------------------------
def get_model_info(model_name: str, model_group: Optional[str] = None) -> Dict[str, Any]:
    """
    根据模型名称返回详细信息，包括路径、类型、版本、uuid、framework、features
    """
    model_config = config.get("models", {})
    search_groups = [model_group] if model_group else model_config.keys()

    for group in search_groups:
        group_models: List[Dict[str, Any]] = model_config.get(group, [])
        for model in group_models:
            if model.get("model_name") == model_name:
                model_path = Path(model.get("model_path", ""))
                project_root = Path(__file__).resolve().parent

                # 如果不是绝对路径，则拼接项目根目录
                if not model_path.is_absolute():
                    model_path = project_root / model_path
                model_path = model_path.resolve().as_posix()

                # 自动创建目录
                Path(model_path).parent.mkdir(parents=True, exist_ok=True)

                # 解析特征
                features = model.get("features", [])
                if isinstance(features, str):
                    features = config.get_features(features)

                logger.info(f"加载模型配置: {model_name} ({model.get('model_type')})")
                logger.info(f"模型路径: {model_path}")
                logger.info(f"特征: {features}")

                return {
                    "model_group": group,
                    "model_name": model.get("model_name"),
                    "model_type": model.get("model_type"),
                    "model_path": model_path,
                    "version": model.get("version"),
                    "uuid": model.get("uuid"),
                    "framework": model.get("framework"),
                    "features": features,
                }

    logger.error(f"未在配置文件中找到模型: {model_name}")
    raise ValueError(f"未找到模型: {model_name}")


# ------------------------------
# 根据模型类型获取模型对象
# ------------------------------
def get_model(model_type: str):
    if model_type == "logistic_regression":
        return LogisticRegression(solver="lbfgs", max_iter=1000, random_state=42)
    elif model_type == "decision_tree":
        return DecisionTreeClassifier(
            max_depth=50,
            criterion='gini',
            splitter='best',
            min_samples_split=2,
            min_samples_leaf=1,
            max_features='log2',
            random_state=42
        )
    elif model_type == "random_forest":
        return RandomForestClassifier(
            n_estimators=100,
            max_depth=20,
            min_samples_split=2,
            min_samples_leaf=1,
            max_features='log2',
            n_jobs=-1,
            random_state=42
        )
    elif model_type == "xgboost":
        return xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            use_label_encoder=False,
            eval_metric="logloss",
            random_state=42
        )
    elif model_type == "lightgbm":
        return lgb.LGBMClassifier(n_estimators=100, max_depth=5, random_state=42)
    elif model_type == "catboost":
        return CatBoostClassifier(
            iterations=100,
            depth=5,
            learning_rate=0.1,
            loss_function='Logloss',
            verbose=False,
            random_state=42
        )
    else:
        raise ValueError(f"未知模型类型: {model_type}")


# ------------------------------
# 保存模型
# ------------------------------
def save_model(pipeline, model_path, model_type):
    """
    保存模型
    """
    model_dir = Path(model_path).parent
    model_dir.mkdir(parents=True, exist_ok=True)  # 自动创建目录

    ext = Path(model_path).suffix.lower()
    model = getattr(pipeline, "named_steps", {}).get("model", pipeline)

    if model_type == "xgboost":
        model.save_model(model_path)
        logger.info(f"[XGBoost] 模型已保存：{model_path}")
    elif model_type == "lightgbm":
        booster = getattr(model, "booster_", model)
        booster.save_model(model_path)
        logger.info(f"[LightGBM] 模型已保存：{model_path}")
    elif model_type == "catboost":
        model.save_model(model_path)
        logger.info(f"[CatBoost] 模型已保存：{model_path}")
    else:
        if ext == ".joblib":
            joblib.dump(pipeline, model_path)
            logger.info(f"[Joblib] 模型已保存：{model_path}")
        elif ext in [".pkl", ".pickle"]:
            with open(model_path, "wb") as f:
                pickle.dump(pipeline, f)
            logger.info(f"[Pickle] 模型已保存：{model_path}")
        else:
            raise ValueError(f"不支持的模型文件格式: {ext}")


# ------------------------------
# 参数: MODEL_NAME，模型名称, 选项如下：
#                  demo_loan_scorecard_lr_20250930
#                  demo_loan_scorecard_dt_20250930
#                  demo_loan_scorecard_rf_20250930
#                  demo_loan_scorecard_lgbm_20250930
#                  demo_loan_scorecard_xgb_20250930
#                  demo_loan_scorecard_cat_20250930
#                  demo_loan_fraud_detection_cat_20250930
# ------------------------------
MODEL_NAME = "demo_loan_fraud_detection_cat_20250930"

def main():
    # 获取模型信息
    model_info = get_model_info(MODEL_NAME)
    model_type = model_info["model_type"]
    model_path = model_info["model_path"]
    model_name = model_info["model_name"]
    features = model_info["features"]

    # --------------------------
    # 从数据库读取数据（示例）
    # --------------------------
    loan_applications = pd.read_sql("SELECT * FROM loan_application WHERE ROWNUM <= 10000", oracle_engine)
    tax_records = pd.read_sql("SELECT * FROM tax_transaction WHERE ROWNUM <= 10000", oracle_engine)

    # --------------------------
    # 构造目标变量（示例随机）
    # --------------------------
    np.random.seed(42)
    loan_applications["default_flag"] = np.random.choice([0, 1], size=len(loan_applications), p=[0.8, 0.2])

    # --------------------------
    # 纳税特征
    # --------------------------
    tax_features = (
        tax_records.groupby("customer_id")
        .agg(
            total_tax_records=("tax_amount", "count"),
            total_tax_amount=("tax_amount", "sum"),
            avg_tax_amount=("tax_amount", "mean"),
            max_tax_amount=("tax_amount", "max"),
            min_tax_amount=("tax_amount", "min"),
            tax_amount_std=("tax_amount", "std"),
        )
        .reset_index()
        .fillna(0)
    )

    # --------------------------
    # 合并特征
    # --------------------------
    data = loan_applications.merge(tax_features, on="customer_id", how="left").fillna(0)
    data["loan_to_income_ratio"] = data["loan_amount"] / data["income"]
    data["existing_loans_ratio"] = data["existing_loans"] / (data["existing_loans"].max() + 1)

    X = data[features]
    y = data["default_flag"]

    # --------------------------
    # 划分训练集
    # --------------------------
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

    # --------------------------
    # Pipeline
    # --------------------------
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", get_model(model_type)),
    ])
    pipeline.fit(X_train, y_train)

    # --------------------------
    # 模型评估
    # --------------------------
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1]
    logger.info(f"=== {MODEL_NAME} 模型评估 ===")
    logger.info(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    logger.info(f"ROC AUC: {roc_auc_score(y_test, y_prob):.4f}")
    logger.info(f"\n{classification_report(y_test, y_pred)}")

    # --------------------------
    # 保存模型
    # --------------------------
    save_model(pipeline, model_path, model_type)


if __name__ == "__main__":
    main()
