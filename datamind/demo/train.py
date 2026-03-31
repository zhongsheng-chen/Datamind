# datamind/demo/train.py

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score
import tempfile
import os
from typing import Optional, Tuple, Dict, Any, List

from datamind.core.ml.model import get_model_registry
from datamind.core.domain.enums import TaskType, ModelType, Framework
from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs
from datamind.core.logging.debug import debug_print
from datamind.core.logging import log_manager
from datamind.core.db.database import db_manager
from datamind.config import get_settings

install_bootstrap_logger()

settings = get_settings()
try:
    log_manager.initialize(settings.logging)
    debug_print("train", "日志管理器初始化成功")
except Exception as e:
    debug_print("train", f"日志管理器初始化失败: {e}")

model_registry = get_model_registry()

try:
    debug_print("train", "初始化数据库连接...")
    db_manager.initialize()
    debug_print("train", "数据库连接初始化成功")
except Exception as e:
    debug_print("train", f"数据库连接初始化失败: {e}")


def generate_data(n_samples: int = 10000,
                  random_state: int = 42,
                  target_rate: float = 0.15) -> Tuple[pd.DataFrame, np.ndarray]:
    """生成示例信贷数据"""
    np.random.seed(random_state)

    age = np.random.normal(35, 10, n_samples).clip(18, 80)
    income = np.random.normal(50000, 20000, n_samples).clip(0, 200000)
    debt_ratio = np.random.beta(2, 5, n_samples) * 0.6
    credit_history = np.random.normal(700, 50, n_samples).clip(300, 850)
    employment_years = np.random.exponential(5, n_samples).clip(0, 40)
    loan_amount = np.random.normal(50000, 30000, n_samples).clip(1000, 200000)

    X = pd.DataFrame({
        'age': age,
        'income': income,
        'debt_ratio': debt_ratio,
        'credit_history': credit_history,
        'employment_years': employment_years,
        'loan_amount': loan_amount
    })

    age_norm = (age - 35) / 10
    income_norm = (income - 50000) / 20000
    debt_ratio_norm = debt_ratio * 2
    credit_history_norm = (credit_history - 700) / 50
    employment_years_norm = employment_years / 10
    loan_amount_norm = loan_amount / 50000

    risk_score = (
        -0.1 * age_norm
        - 0.2 * income_norm
        + 1.5 * debt_ratio_norm
        - 0.3 * credit_history_norm
        - 0.15 * employment_years_norm
        + 0.1 * loan_amount_norm
        + np.random.normal(0, 0.5, n_samples)
    )

    prob = 1 / (1 + np.exp(-risk_score))
    threshold = np.percentile(prob, (1 - target_rate) * 100)
    y = (prob > threshold).astype(int)

    print(f"   风险分数范围: min={risk_score.min():.4f}, max={risk_score.max():.4f}, mean={risk_score.mean():.4f}")
    print(f"   违约概率范围: min={prob.min():.4f}, max={prob.max():.4f}, mean={prob.mean():.4f}")
    print(f"   实际违约率: {y.mean():.2%}")

    return X, y


def train_pipeline(X_train: pd.DataFrame, y_train: np.ndarray, model_type: str,
                   n_estimators: int = 100, max_depth: int = 5) -> Pipeline:
    """
    训练 Pipeline 模型

    参数:
        X_train: 训练特征
        y_train: 训练标签
        model_type: 模型类型 ('random_forest', 'logistic_regression')
        n_estimators: 随机森林参数
        max_depth: 随机森林参数

    返回:
        训练好的 Pipeline
    """
    if model_type == 'random_forest':
        classifier = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth, random_state=42, n_jobs=-1
        )
    else:
        classifier = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', classifier)
    ])

    pipeline.fit(X_train, y_train)
    return pipeline


def evaluate_pipeline(pipeline: Pipeline, X_test: pd.DataFrame, y_test: np.ndarray,
                      feature_names: List[str]) -> Dict[str, Any]:
    """
    评估 Pipeline 性能

    参数:
        pipeline: 训练好的 Pipeline
        X_test: 测试特征
        y_test: 测试标签
        feature_names: 特征名称列表

    返回:
        评估结果字典
    """
    y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
    y_pred = pipeline.predict(X_test)

    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)

    classifier = pipeline.named_steps['classifier']
    if hasattr(classifier, 'coef_'):
        importance = np.abs(classifier.coef_[0])
    elif hasattr(classifier, 'feature_importances_'):
        importance = classifier.feature_importances_
    else:
        importance = np.ones(len(feature_names))

    feature_importance = {col: float(imp) for col, imp in zip(feature_names, importance)}

    print(f"   AUC: {auc:.4f}")
    print(f"   准确率: {accuracy:.4f}")
    print(f"   预测概率范围: min={y_pred_proba.min():.4f}, max={y_pred_proba.max():.4f}, mean={y_pred_proba.mean():.4f}")

    print("\n   特征重要性:")
    for col, imp in sorted(feature_importance.items(), key=lambda x: -x[1]):
        print(f"     {col}: {imp:.4f}")

    return {
        'auc': auc,
        'accuracy': accuracy,
        'feature_importance': feature_importance,
        'y_pred_proba': y_pred_proba
    }


def register_pipeline(pipeline: Pipeline, model_name: str, model_version: str,
                      feature_names: List[str], eval_result: Dict[str, Any],
                      model_params: Dict[str, Any],
                      activate: bool = True, set_production: bool = True) -> str:
    """
    注册 Pipeline 到模型注册中心

    参数:
        pipeline: 训练好的 Pipeline
        model_name: 模型名称
        model_version: 模型版本
        feature_names: 特征名称列表
        eval_result: 评估结果
        model_params: 模型参数
        activate: 是否激活
        set_production: 是否设为生产

    返回:
        模型ID
    """
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
        joblib.dump(pipeline, tmp.name)
        model_path = tmp.name

    try:
        model_type = 'random_forest' if isinstance(pipeline.named_steps['classifier'], RandomForestClassifier) else 'logistic_regression'
        model_type_enum = ModelType.RANDOM_FOREST.value if model_type == 'random_forest' else ModelType.LOGISTIC_REGRESSION.value

        model_id = model_registry.register_model(
            model_name=model_name,
            model_version=model_version,
            task_type=TaskType.SCORING.value,
            model_type=model_type_enum,
            framework=Framework.SKLEARN.value,
            input_features=feature_names,
            output_schema={"score": "float", "probability": "float", "feature_scores": "dict"},
            created_by="demo",
            model_file=open(model_path, 'rb'),
            description=f"示例{model_type}评分卡模型，AUC={eval_result['auc']:.4f}",
            model_params=model_params,
            scorecard_params={
                "base_score": 600, "pdo": 50, "min_score": 300,
                "max_score": 900, "direction": "lower_better", "base_odds": 1.0
            }
        )
        print(f"   模型注册成功，ID: {model_id}")

        if activate:
            model_registry.activate_model(model_id=model_id, operator="demo", reason="示例模型激活")
            print(f"   模型已激活")

        if set_production:
            model_registry.promote_to_production(model_id=model_id, operator="demo", reason="示例模型设为生产")
            print(f"   已设置为生产模型")

        return model_id

    finally:
        if os.path.exists(model_path):
            os.unlink(model_path)


def train_model(model_type: str = 'logistic_regression',
                n_estimators: int = 100,
                max_depth: int = 5,
                save_to_registry: bool = True,
                activate: bool = True,
                set_production: bool = True,
                output_path: Optional[str] = None) -> dict:
    """
    训练示例评分卡模型

    参数:
        model_type: 模型类型 ('random_forest', 'logistic_regression')
        n_estimators: 随机森林的树数量
        max_depth: 树的最大深度
        save_to_registry: 是否保存到模型注册中心
        activate: 是否激活模型
        set_production: 是否设置为生产模型
        output_path: 输出路径（如果不保存到注册中心）

    返回:
        训练结果字典
    """
    print("\n" + "=" * 60)
    print("开始训练示例评分卡模型")
    print("=" * 60)

    print("\n1. 生成示例数据...")
    X, y = generate_data(n_samples=10000, target_rate=0.15)
    print(f"   特征维度: {X.shape}")
    print(f"   特征列表: {list(X.columns)}")
    print(f"   正样本比例: {y.mean():.2%}")

    if y.sum() < 2:
        print(f"   警告: 正样本数量太少，重新生成数据...")
        X, y = generate_data(n_samples=10000, target_rate=0.15)

    print("\n2. 划分训练集和测试集...")
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError:
        print(f"   分层抽样失败，使用普通抽样")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
    print(f"   训练集: {len(X_train)} 样本")
    print(f"   测试集: {len(X_test)} 样本")

    print("\n3. 训练模型...")
    pipeline = train_pipeline(X_train, y_train, model_type, n_estimators, max_depth)
    print("   模型训练完成")

    print("\n4. 评估模型...")
    eval_result = evaluate_pipeline(pipeline, X_test, y_test, list(X.columns))

    print("\n5. 保存模型...")
    model_name = f"demo_{model_type}"
    model_version = "1.0.0"

    if save_to_registry:
        model_params = {
            "n_estimators": n_estimators if model_type == 'random_forest' else None,
            "max_depth": max_depth if model_type == 'random_forest' else None,
            "feature_importance": eval_result['feature_importance']
        }
        model_id = register_pipeline(
            pipeline, model_name, model_version, list(X.columns),
            eval_result, model_params, activate, set_production
        )
        result = {
            'success': True,
            'model_id': model_id,
            'model_name': model_name,
            'model_version': model_version,
            'model_type': model_type,
            'auc': eval_result['auc'],
            'accuracy': eval_result['accuracy'],
            'feature_importance': eval_result['feature_importance'],
            'message': f'模型 {model_name} v{model_version} 训练并注册成功'
        }
    else:
        if output_path is None:
            output_path = f"./{model_name}_{model_version}.pkl"
        joblib.dump(pipeline, output_path)
        print(f"   模型已保存到: {output_path}")
        result = {
            'success': True,
            'model_path': output_path,
            'model_name': model_name,
            'model_version': model_version,
            'model_type': model_type,
            'auc': eval_result['auc'],
            'accuracy': eval_result['accuracy'],
            'feature_importance': eval_result['feature_importance'],
            'message': f'模型已保存到 {output_path}'
        }

    print("\n" + "=" * 60)
    print("训练完成!")
    print("=" * 60)

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="训练示例评分卡模型")
    parser.add_argument(
        "--type", choices=["random_forest", "logistic_regression"],
        default="logistic_regression", help="模型类型"
    )
    parser.add_argument(
        "--no-registry", action="store_true", help="不保存到注册中心，保存到本地文件"
    )
    parser.add_argument(
        "--output", help="输出路径（配合 --no-registry 使用）"
    )

    args = parser.parse_args()

    result = train_model(
        model_type=args.type,
        save_to_registry=not args.no_registry,
        output_path=args.output
    )

    flush_bootstrap_logs()

    if result['success']:
        print(f"\n{result['message']}")
    else:
        print(f"\n{result['message']}")