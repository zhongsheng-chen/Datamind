# datamind/demo/train_sample_model.py
"""训练示例评分卡模型

用于演示和测试模型部署功能。
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score, accuracy_score
import joblib

from datamind.core.ml.model_registry import model_registry
from datamind.core.domain.enums import TaskType, ModelType, Framework, ModelStatus
from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs
from datamind.core.logging.debug import debug_print
from datamind.core.db.database import db_manager
from datamind.config import get_settings

install_bootstrap_logger()

# 初始化数据库连接
try:
    debug_print("train_sample_model", "初始化数据库连接...")
    db_manager.initialize()
    debug_print("train_sample_model", "数据库连接初始化成功")
except Exception as e:
    debug_print("train_sample_model", f"数据库连接初始化失败: {e}")


def generate_sample_data(n_samples=10000, random_state=42):
    """
    生成示例信贷数据

    Args:
        n_samples: 样本数量
        random_state: 随机种子

    Returns:
        X: 特征DataFrame
        y: 标签Series
    """
    np.random.seed(random_state)

    # 生成特征
    age = np.random.normal(35, 10, n_samples).clip(18, 80)
    income = np.random.normal(50000, 20000, n_samples).clip(0, 200000)
    debt_ratio = np.random.beta(2, 5, n_samples) * 0.6
    credit_history = np.random.normal(700, 50, n_samples).clip(300, 850)
    employment_years = np.random.exponential(5, n_samples).clip(0, 40)
    loan_amount = np.random.normal(50000, 30000, n_samples).clip(1000, 200000)

    # 构建DataFrame
    X = pd.DataFrame({
        'age': age,
        'income': income,
        'debt_ratio': debt_ratio,
        'credit_history': credit_history,
        'employment_years': employment_years,
        'loan_amount': loan_amount
    })

    # 生成标签（违约概率）- 调整参数使正样本比例约为 15-20%
    log_odds = (
        -2.0
        + 0.05 * (age - 35) / 10
        - 0.00003 * (income - 50000) / 10000
        + 3.0 * debt_ratio
        - 0.02 * (credit_history - 700) / 50
        - 0.1 * employment_years
        + 0.00002 * loan_amount / 10000
        + np.random.normal(0, 0.8, n_samples)
    )

    prob = 1 / (1 + np.exp(-log_odds))
    y = (prob > 0.5).astype(int)

    print(f"   违约概率分布: min={prob.min():.4f}, max={prob.max():.4f}, mean={prob.mean():.4f}")

    return X, y


def train_sample_model(
        model_type='random_forest',
        n_estimators=100,
        max_depth=5,
        save_to_registry=True,
        activate=True,
        set_production=True,
        output_path=None
):
    """
    训练示例评分卡模型

    Args:
        model_type: 模型类型 ('random_forest', 'logistic_regression')
        n_estimators: 随机森林的树数量
        max_depth: 树的最大深度
        save_to_registry: 是否保存到模型注册中心
        activate: 是否激活模型
        set_production: 是否设置为生产模型
        output_path: 输出路径（如果不保存到注册中心）

    Returns:
        dict: 训练结果信息
    """
    print("\n" + "=" * 60)
    print("开始训练示例评分卡模型")
    print("=" * 60)

    # 1. 生成数据
    print("\n1. 生成示例数据...")
    X, y = generate_sample_data(n_samples=10000)
    print(f"   特征维度: {X.shape}")
    print(f"   特征列表: {list(X.columns)}")
    print(f"   正样本比例: {y.mean():.2%}")

    # 检查正样本数量是否足够
    n_pos = y.sum()
    if n_pos < 2:
        print(f"   警告: 正样本数量太少 ({n_pos})，重新生成数据...")
        X, y = generate_sample_data(n_samples=10000)
        print(f"   正样本比例: {y.mean():.2%}")

    # 2. 划分数据集
    print("\n2. 划分训练集和测试集...")
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError as e:
        print(f"   分层抽样失败: {e}，使用普通抽样")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
    print(f"   训练集: {len(X_train)} 样本")
    print(f"   测试集: {len(X_test)} 样本")
    print(f"   训练集正样本比例: {y_train.mean():.2%}")
    print(f"   测试集正样本比例: {y_test.mean():.2%}")

    # 3. 特征标准化
    print("\n3. 特征标准化...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # 4. 训练模型
    print(f"\n4. 训练模型 ({model_type})...")

    if model_type == 'random_forest':
        model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42,
            n_jobs=-1
        )
    elif model_type == 'logistic_regression':
        model = LogisticRegression(
            max_iter=1000,
            random_state=42,
            n_jobs=-1
        )
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")

    model.fit(X_train_scaled, y_train)
    print("   模型训练完成")

    # 5. 评估模型
    print("\n5. 评估模型...")
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = model.predict(X_test_scaled)

    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"   AUC: {auc:.4f}")
    print(f"   准确率: {accuracy:.4f}")

    # 6. 特征重要性
    if hasattr(model, 'feature_importances_'):
        importance = model.feature_importances_
    elif hasattr(model, 'coef_'):
        importance = np.abs(model.coef_[0])
    else:
        importance = np.ones(len(X.columns))

    feature_importance = {
        col: float(imp) for col, imp in zip(X.columns, importance)
    }

    print("\n   特征重要性:")
    for col, imp in sorted(feature_importance.items(), key=lambda x: -x[1]):
        print(f"     {col}: {imp:.4f}")

    # 7. 保存模型
    print("\n6. 保存模型...")

    model_name = f"demo_{model_type}"
    model_version = "1.0.0"
    model_path = None

    try:
        # 保存模型文件到临时目录
        with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
            joblib.dump(model, tmp.name)
            model_path = tmp.name

        if save_to_registry:
            # 注册模型
            model_id = model_registry.register_model(
                model_name=model_name,
                model_version=model_version,
                task_type=TaskType.SCORING.value,
                model_type=ModelType.RANDOM_FOREST.value if model_type == 'random_forest' else ModelType.LOGISTIC_REGRESSION.value,
                framework=Framework.SKLEARN.value,
                input_features=list(X.columns),
                output_schema={
                    "score": "float",
                    "probability": "float",
                    "feature_scores": "dict"
                },
                created_by="demo",
                model_file=open(model_path, 'rb'),
                description=f"示例{model_type}评分卡模型，AUC={auc:.4f}",
                model_params={
                    "n_estimators": n_estimators if model_type == 'random_forest' else None,
                    "max_depth": max_depth if model_type == 'random_forest' else None,
                    "scaler": {
                        "mean": scaler.mean_.tolist(),
                        "scale": scaler.scale_.tolist()
                    }
                },
                scorecard_params={
                    "base_score": 600,
                    "pdo": 50,
                    "min_score": 300,
                    "max_score": 900,
                    "direction": "higher_better"
                }
            )
            print(f"   模型注册成功，ID: {model_id}")

            # 激活模型
            if activate:
                model_registry.activate_model(
                    model_id=model_id,
                    operator="demo",
                    reason="示例模型激活"
                )
                print(f"   模型已激活")

            # 设置为生产模型
            if set_production:
                model_registry.promote_to_production(
                    model_id=model_id,
                    operator="demo",
                    reason="示例模型设为生产"
                )
                print(f"   已设置为生产模型")

            result = {
                'success': True,
                'model_id': model_id,
                'model_name': model_name,
                'model_version': model_version,
                'model_type': model_type,
                'auc': auc,
                'accuracy': accuracy,
                'feature_importance': feature_importance,
                'message': f'模型 {model_name} v{model_version} 训练并注册成功'
            }
        else:
            # 保存到本地文件
            if output_path is None:
                output_path = f"./{model_name}_{model_version}.pkl"

            joblib.dump((model, scaler, list(X.columns)), output_path)
            print(f"   模型已保存到: {output_path}")

            result = {
                'success': True,
                'model_path': output_path,
                'model_name': model_name,
                'model_version': model_version,
                'model_type': model_type,
                'auc': auc,
                'accuracy': accuracy,
                'feature_importance': feature_importance,
                'message': f'模型已保存到 {output_path}'
            }

        print("\n" + "=" * 60)
        print("训练完成!")
        print("=" * 60)

        return result

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e),
            'message': f'训练失败: {e}'
        }
    finally:
        # 清理临时文件
        if model_path and os.path.exists(model_path):
            os.unlink(model_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="训练示例评分卡模型")
    parser.add_argument(
        "--type",
        choices=["random_forest", "logistic_regression"],
        default="random_forest",
        help="模型类型"
    )
    parser.add_argument(
        "--no-registry",
        action="store_true",
        help="不保存到注册中心，保存到本地文件"
    )
    parser.add_argument(
        "--output",
        help="输出路径（配合 --no-registry 使用）"
    )

    args = parser.parse_args()

    result = train_sample_model(
        model_type=args.type,
        save_to_registry=not args.no_registry,
        output_path=args.output
    )

    flush_bootstrap_logs()

    if result['success']:
        print(f"\n✓ {result['message']}")
    else:
        print(f"\n✗ {result['message']}")