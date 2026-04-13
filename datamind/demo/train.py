# datamind/demo/train.py

"""模型训练脚本

提供示例评分卡模型的训练、评估和注册功能，用于演示 Datamind 平台的模型管理能力。

核心功能：
  - generate_data: 生成示例信贷数据用于模型训练
  - woe_transform: 基于分箱配置进行WOE转换
  - train_scorecard: 训练WOE转换后的逻辑回归模型
  - train_pipeline: 训练 sklearn Pipeline 模型（直接使用原始特征）
  - evaluate_model: 评估模型性能
  - register_scorecard: 注册评分卡模型（包含WOE分箱配置）
  - register_pipeline: 注册标准 Pipeline 模型
  - train_model: 统一的训练入口，支持多种训练方式

训练方式：
  - woe: 使用WOE分箱训练（推荐，特征贡献合理）
  - raw: 使用原始特征训练（特征贡献巨大，不推荐）

使用场景：
  - 快速验证：使用示例数据快速验证模型训练流程
  - 模型注册：将训练好的模型注册到模型注册中心
  - 生产部署：将模型设为生产版本，供服务调用

支持的模型类型：
  - logistic_regression: 逻辑回归（评分卡）
  - random_forest: 随机森林（陪跑模型）

使用示例：
    >>> # 使用WOE方式训练逻辑回归模型并注册（推荐）
    >>> result = train_model(model_type="logistic_regression", train_mode="woe")
    >>>
    >>> # 使用原始特征训练随机森林模型
    >>> result = train_model(model_type="random_forest", train_mode="raw")
"""

import joblib
import numpy as np
import pandas as pd
import tempfile
import os
import argparse
import logging
import json
from typing import Optional, Tuple, Dict, Any, List
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, accuracy_score

from datamind.core.model import get_model_registry
from datamind.core.domain.enums import TaskType, ModelType, Framework
from datamind.core.db.database import db_manager
from datamind.config import get_settings
from datamind.demo.binning_config import BINNING_CONFIG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()
model_registry = get_model_registry()


def generate_data(
    n_samples: int = 10000,
    random_state: int = 42,
    target_rate: float = 0.15
) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    生成示例信贷数据

    参数:
        n_samples: 样本数量
        random_state: 随机种子
        target_rate: 目标违约率

    返回:
        (特征DataFrame, 标签数组)
    """
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

    # 生成目标变量（基于风险逻辑）
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

    logger.info("风险分数范围: min=%.4f, max=%.4f, mean=%.4f",
                risk_score.min(), risk_score.max(), risk_score.mean())
    logger.info("违约概率范围: min=%.4f, max=%.4f, mean=%.4f",
                prob.min(), prob.max(), prob.mean())
    logger.info("实际违约率: %.2f%%", y.mean() * 100)

    return X, y


def woe_transform_value(value: float, bins: List) -> float:
    """
    根据分箱配置将单个值转换为WOE值

    参数:
        value: 原始特征值
        bins: Bin对象列表

    返回:
        WOE值
    """
    if value is None:
        # 查找缺失值分箱
        for b in bins:
            if b.is_missing:
                return b.woe
        return 0.0

    for b in bins:
        if b.contains(value):
            return b.woe

    # 如果没有匹配的分箱，返回最后一个分箱的WOE
    return bins[-1].woe if bins else 0.0


def woe_transform_dataframe(
    df: pd.DataFrame,
    binning_config: Dict[str, List]
) -> pd.DataFrame:
    """
    将DataFrame中的所有特征转换为WOE值

    参数:
        df: 原始特征DataFrame
        binning_config: 分箱配置字典

    返回:
        WOE值DataFrame
    """
    df_woe = pd.DataFrame(index=df.index)

    for col in df.columns:
        if col in binning_config:
            bins = binning_config[col]
            df_woe[col] = df[col].apply(lambda x: woe_transform_value(x, bins))
        else:
            # 如果没有分箱配置，保持原值
            logger.warning("特征 %s 没有分箱配置，将保持原值", col)
            df_woe[col] = df[col]

    return df_woe


def train_scorecard(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    binning_config: Dict[str, List],
    feature_names: List[str]
) -> Tuple[LogisticRegression, Dict[str, Any]]:
    """
    使用WOE转换训练逻辑回归评分卡模型

    参数:
        X_train: 训练特征（原始值）
        y_train: 训练标签
        binning_config: 分箱配置
        feature_names: 特征名称列表

    返回:
        (训练好的逻辑回归模型, 模型系数字典)
    """
    logger.info("进行WOE转换...")
    X_train_woe = woe_transform_dataframe(X_train, binning_config)

    logger.info("训练逻辑回归模型...")
    model = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)
    model.fit(X_train_woe[feature_names].values, y_train)

    # 构建系数映射
    coef_map = {}
    for i, col in enumerate(feature_names):
        coef_map[col] = float(model.coef_[0][i])

    logger.info("模型系数:")
    for col, coef in sorted(coef_map.items(), key=lambda x: -abs(x[1])):
        logger.info("  %s: %.6f", col, coef)
    logger.info("截距: %.6f", model.intercept_[0])

    return model, coef_map


def train_pipeline(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    model_type: str,
    n_estimators: int = 100,
    max_depth: int = 5
) -> Pipeline:
    """
    训练 Pipeline 模型（直接使用原始特征）

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
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=42, n_jobs=-1
        )
    else:
        classifier = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)

    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('classifier', classifier)
    ])

    pipeline.fit(X_train, y_train)
    return pipeline


def evaluate_model(
    model,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    feature_names: List[str],
    is_woe_model: bool = False,
    binning_config: Optional[Dict[str, List]] = None
) -> Dict[str, Any]:
    """
    评估模型性能

    参数:
        model: 训练好的模型
        X_test: 测试特征
        y_test: 测试标签
        feature_names: 特征名称列表
        is_woe_model: 是否为WOE模型
        binning_config: 分箱配置（WOE模型需要）

    返回:
        评估结果字典
    """
    if is_woe_model and binning_config:
        X_test_woe = woe_transform_dataframe(X_test, binning_config)
        X_eval = X_test_woe[feature_names].values
        y_pred_proba = model.predict_proba(X_eval)[:, 1]
    else:
        y_pred_proba = model.predict_proba(X_test[feature_names].values)[:, 1]

    y_pred = (y_pred_proba > 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    accuracy = accuracy_score(y_test, y_pred)

    # 获取特征重要性/系数
    if hasattr(model, 'coef_'):
        importance = np.abs(model.coef_[0])
    elif hasattr(model, 'feature_importances_'):
        importance = model.feature_importances_
    else:
        importance = np.ones(len(feature_names))

    feature_importance = {col: float(imp) for col, imp in zip(feature_names, importance)}

    logger.info("AUC: %.4f", auc)
    logger.info("准确率: %.4f", accuracy)
    logger.info("预测概率范围: min=%.4f, max=%.4f, mean=%.4f",
                y_pred_proba.min(), y_pred_proba.max(), y_pred_proba.mean())

    logger.info("特征重要性/系数:")
    for col, imp in sorted(feature_importance.items(), key=lambda x: -abs(x[1])):
        logger.info("  %s: %.6f", col, imp)

    return {
        'auc': auc,
        'accuracy': accuracy,
        'feature_importance': feature_importance,
        'y_pred_proba': y_pred_proba
    }


def register_scorecard(
    model: LogisticRegression,
    model_name: str,
    model_version: str,
    feature_names: List[str],
    binning_config: Dict[str, List],
    eval_result: Dict[str, Any],
    coef_map: Dict[str, float],
    intercept: float,
    activate: bool = True,
    set_production: bool = True
) -> str:
    """
    注册评分卡模型（包含WOE分箱配置）

    参数:
        model: 训练好的逻辑回归模型
        model_name: 模型名称
        model_version: 模型版本
        feature_names: 特征名称列表
        binning_config: 分箱配置（Bin对象列表）
        eval_result: 评估结果
        coef_map: 特征系数映射
        intercept: 截距
        activate: 是否激活
        set_production: 是否设为生产

    返回:
        模型ID
    """
    # 将Bin对象转换为可序列化的字典
    binning_serializable = {}
    for col, bins in binning_config.items():
        binning_serializable[col] = [b.to_dict() for b in bins]

    # 构建评分卡参数
    scorecard_config = {
        "binning": binning_serializable,
        "coefficients": coef_map,
        "intercept": intercept,
        "base_score": 600,
        "pdo": 50,
        "base_odds": 20,
        "min_score": 300,
        "max_score": 900,
        "direction": "lower_better"
    }

    # 保存模型到临时文件
    with tempfile.NamedTemporaryFile(suffix='.pkl', delete=False) as tmp:
        joblib.dump(model, tmp.name)
        model_path = tmp.name

    try:
        model_id = model_registry.register_model(
            model_name=model_name,
            model_version=model_version,
            task_type=TaskType.SCORING.value,
            model_type=ModelType.LOGISTIC_REGRESSION.value,
            framework=Framework.SKLEARN.value,
            input_features=feature_names,
            output_schema={"score": "float", "probability": "float", "feature_scores": "dict"},
            created_by="demo",
            model_file=open(model_path, 'rb'),
            description=f"评分卡模型（WOE转换），AUC={eval_result['auc']:.4f}",
            model_params={
                "coefficients": coef_map,
                "intercept": intercept,
                "feature_importance": eval_result['feature_importance']
            },
            scorecard_config=scorecard_config  # 关键：传入WOE分箱配置
        )
        logger.info("模型注册成功，ID: %s", model_id)

        if activate:
            model_registry.activate_model(model_id=model_id, operator="demo", reason="示例模型激活")
            logger.info("模型已激活")

        if set_production:
            model_registry.promote_to_production(model_id=model_id, operator="demo", reason="示例模型设为生产")
            logger.info("已设置为生产模型")

        return model_id

    finally:
        if os.path.exists(model_path):
            os.unlink(model_path)


def register_pipeline(
    pipeline: Pipeline,
    model_name: str,
    model_version: str,
    feature_names: List[str],
    eval_result: Dict[str, Any],
    model_params: Dict[str, Any],
    activate: bool = True,
    set_production: bool = True
) -> str:
    """
    注册标准 Pipeline 模型（无WOE分箱）

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
        classifier = pipeline.named_steps['classifier']
        if isinstance(classifier, RandomForestClassifier):
            model_type = ModelType.RANDOM_FOREST.value
        else:
            model_type = ModelType.LOGISTIC_REGRESSION.value

        model_id = model_registry.register_model(
            model_name=model_name,
            model_version=model_version,
            task_type=TaskType.SCORING.value,
            model_type=model_type,
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
        logger.info("模型注册成功，ID: %s", model_id)

        if activate:
            model_registry.activate_model(model_id=model_id, operator="demo", reason="示例模型激活")
            logger.info("模型已激活")

        if set_production:
            model_registry.promote_to_production(model_id=model_id, operator="demo", reason="示例模型设为生产")
            logger.info("已设置为生产模型")

        return model_id

    finally:
        if os.path.exists(model_path):
            os.unlink(model_path)


def train_model(
    model_type: str = 'logistic_regression',
    train_mode: str = 'woe',  # 'woe' 或 'raw'
    n_estimators: int = 100,
    max_depth: int = 5,
    save_to_registry: bool = True,
    activate: bool = True,
    set_production: bool = True,
    output_path: Optional[str] = None
) -> dict:
    """
    训练示例评分卡模型

    参数:
        model_type: 模型类型 ('random_forest', 'logistic_regression')
        train_mode: 训练模式 ('woe': WOE转换训练, 'raw': 原始特征训练)
        n_estimators: 随机森林的树数量
        max_depth: 树的最大深度
        save_to_registry: 是否保存到模型注册中心
        activate: 是否激活模型
        set_production: 是否设置为生产模型
        output_path: 输出路径（如果不保存到注册中心）

    返回:
        训练结果字典
    """
    logger.info("=" * 60)
    logger.info("开始训练示例评分卡模型")
    logger.info("模型类型: %s", model_type)
    logger.info("训练模式: %s", train_mode)
    logger.info("=" * 60)

    # 1. 生成数据
    logger.info("1. 生成示例数据...")
    X, y = generate_data(n_samples=10000, target_rate=0.15)
    feature_names = list(X.columns)
    logger.info("特征维度: %s", X.shape)
    logger.info("特征列表: %s", feature_names)
    logger.info("正样本比例: %.2f%%", y.mean() * 100)

    if y.sum() < 2:
        logger.warning("正样本数量太少，重新生成数据...")
        X, y = generate_data(n_samples=10000, target_rate=0.15)

    # 2. 划分数据集
    logger.info("2. 划分训练集和测试集...")
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except ValueError:
        logger.warning("分层抽样失败，使用普通抽样")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
    logger.info("训练集: %d 样本", len(X_train))
    logger.info("测试集: %d 样本", len(X_test))

    # 3. 训练模型
    logger.info("3. 训练模型...")

    if train_mode == 'woe' and model_type == 'logistic_regression':
        # 使用WOE转换训练逻辑回归（推荐）
        logger.info("使用WOE转换训练逻辑回归模型...")
        model, coef_map = train_scorecard(X_train, y_train, BINNING_CONFIG, feature_names)
        is_woe_model = True
    else:
        # 使用原始特征训练
        logger.info("使用原始特征训练模型...")
        model = train_pipeline(X_train, y_train, model_type, n_estimators, max_depth)
        is_woe_model = False

    logger.info("模型训练完成")

    # 4. 评估模型
    logger.info("4. 评估模型...")
    if is_woe_model:
        eval_result = evaluate_model(
            model, X_test, y_test, feature_names,
            is_woe_model=True, binning_config=BINNING_CONFIG
        )
    else:
        eval_result = evaluate_model(
            model, X_test, y_test, feature_names, is_woe_model=False
        )

    # 5. 保存模型
    logger.info("5. 保存模型...")
    model_name = f"demo_{model_type}"
    if train_mode == 'woe':
        model_name = f"{model_name}_woe"
    model_version = "1.0.0"

    if save_to_registry:
        # 初始化数据库连接
        try:
            logger.info("初始化数据库连接...")
            db_manager.initialize()
            logger.info("数据库连接初始化成功")
        except Exception as e:
            logger.error("数据库连接初始化失败: %s", e)
            return {
                'success': False,
                'message': f"数据库连接初始化失败: {e}"
            }

        if is_woe_model:
            # 注册WOE模型（包含分箱配置）
            intercept = float(model.intercept_[0])
            model_id = register_scorecard(
                model, model_name, model_version, feature_names,
                BINNING_CONFIG, eval_result, coef_map, intercept,
                activate, set_production
            )
        else:
            # 注册标准Pipeline模型
            model_params = {
                "n_estimators": n_estimators if model_type == 'random_forest' else None,
                "max_depth": max_depth if model_type == 'random_forest' else None,
                "feature_importance": eval_result['feature_importance']
            }
            model_id = register_pipeline(
                model, model_name, model_version, feature_names,
                eval_result, model_params, activate, set_production
            )

        result = {
            'success': True,
            'model_id': model_id,
            'model_name': model_name,
            'model_version': model_version,
            'model_type': model_type,
            'train_mode': train_mode,
            'auc': eval_result['auc'],
            'accuracy': eval_result['accuracy'],
            'feature_importance': eval_result['feature_importance'],
            'message': f'模型 {model_name} v{model_version} 训练并注册成功'
        }
    else:
        if output_path is None:
            output_path = f"./{model_name}_{model_version}.pkl"
        joblib.dump(model, output_path)
        logger.info("模型已保存到: %s", output_path)

        # 如果使用WOE训练，也保存分箱配置
        if is_woe_model:
            binning_path = output_path.replace('.pkl', '_binning.json')
            binning_serializable = {}
            for col, bins in BINNING_CONFIG.items():
                binning_serializable[col] = [b.to_dict() for b in bins]
            with open(binning_path, 'w') as f:
                json.dump(binning_serializable, f, indent=2)
            logger.info("分箱配置已保存到: %s", binning_path)

        result = {
            'success': True,
            'model_path': output_path,
            'model_name': model_name,
            'model_version': model_version,
            'model_type': model_type,
            'train_mode': train_mode,
            'auc': eval_result['auc'],
            'accuracy': eval_result['accuracy'],
            'feature_importance': eval_result['feature_importance'],
            'message': f'模型已保存到 {output_path}'
        }

    logger.info("=" * 60)
    logger.info("训练完成!")
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="训练示例评分卡模型")
    parser.add_argument(
        "--type", choices=["random_forest", "logistic_regression"],
        default="logistic_regression", help="模型类型"
    )
    parser.add_argument(
        "--mode", choices=["woe", "raw"],
        default="woe", help="训练模式: woe=WOE转换训练, raw=原始特征训练"
    )
    parser.add_argument(
        "--no-registry", action="store_true", help="不保存到注册中心，保存到本地文件"
    )
    parser.add_argument(
        "--output", help="输出路径（配合 --no-registry 使用）"
    )
    parser.add_argument(
        "--n-estimators", type=int, default=100, help="随机森林的树数量"
    )
    parser.add_argument(
        "--max-depth", type=int, default=5, help="树的最大深度"
    )

    args = parser.parse_args()

    result = train_model(
        model_type=args.type,
        train_mode=args.mode,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        save_to_registry=not args.no_registry,
        output_path=args.output
    )

    if result['success']:
        print(f"\n{result['message']}")
        if 'model_id' in result:
            print(f"模型ID: {result['model_id']}")
        if 'model_path' in result:
            print(f"模型路径: {result['model_path']}")
        print(f"AUC: {result['auc']:.4f}")
        print(f"准确率: {result['accuracy']:.4f}")
    else:
        print(f"\n错误: {result['message']}")