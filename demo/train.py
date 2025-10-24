#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
train.py

训练一个演示模型. 支持 Decision Tree, Random Forest, XGBoost, LightGBM, Linear Regression.
通过 model_type 指定模型算法.
"""

import os
import joblib
import pickle
import logging
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
from src.db_engine import oracle_engine
from src.utils import get_model_info


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
# 参数
# ------------------------------
BUSINESS_NAME = "demo_loan_catboost" # 可选 demo_loan_lr|demo_loan_dt|demo_loan_rf|demo_loan_lightgbm|demo_loan_xgboost|demo_loan_catboost

# ------------------------------
# 模型选择函数
# ------------------------------
def get_model(model_type):
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
# 通用模型保存函数
# ------------------------------
def save_model(pipeline, model_path, model_type):
    """
    保存模型：
    - XGBoost、LightGBM、CatBoost 使用原生保存方法
    - 其他 sklearn 模型使用 joblib 或 pickle，根据文件后缀自动选择
    """
    ext = os.path.splitext(model_path)[1].lower()
    model = getattr(pipeline, "named_steps", {}).get("model", pipeline)  # 兼容 pipeline 或直接模型对象

    if model_type == "xgboost":
        model.save_model(model_path)
        logger.info(f"[XGBoost] 模型已保存：{model_path}")

    elif model_type == "lightgbm":
        # LightGBM pipeline 时获取 booster_
        booster = getattr(model, "booster_", model)
        booster.save_model(model_path)
        logger.info(f"[LightGBM] 模型已保存：{model_path}")

    elif model_type == "catboost":
        model.save_model(model_path)
        logger.info(f"[CatBoost] 模型已保存：{model_path}")

    else:
        # 其他 sklearn 模型
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
# 主程序
# ------------------------------
def main():
    model_info = get_model_info(BUSINESS_NAME)
    model_type = model_info["model_type"]
    model_path = model_info["model_path"]
    model_name = model_info["model_name"]
    features = model_info["features"]

    # --------------------------
    # 从数据库读取数据
    # --------------------------
    loan_applications = pd.read_sql("SELECT * FROM loan_application WHERE ROWNUM <= 10000", oracle_engine)
    tax_records = pd.read_sql("SELECT * FROM tax_transaction WHERE ROWNUM <= 10000", oracle_engine)

    # --------------------------
    # 构造目标变量 (示例用随机数模拟)
    # --------------------------
    np.random.seed(42)
    loan_applications["default_flag"] = np.random.choice([0, 1], size=len(loan_applications), p=[0.8, 0.2])

    # --------------------------
    # 生成纳税特征
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
    # 划分训练集和测试集
    # --------------------------
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

    # --------------------------
    # Pipeline：标准化 + 模型
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
    logger.info(f"=== {BUSINESS_NAME}-{model_name} 模型评估 ===")
    logger.info(f"Accuracy: {accuracy_score(y_test, y_pred):.4f}")
    logger.info(f"ROC AUC: {roc_auc_score(y_test, y_prob):.4f}")
    logger.info(f"\n{classification_report(y_test, y_pred)}")

    # --------------------------
    # 保存模型（支持 joblib/pickle）
    # --------------------------
    save_model(pipeline, model_path, model_type)


if __name__ == "__main__":
    main()
