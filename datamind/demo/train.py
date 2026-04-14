"""模型训练脚本

提供示例评分卡模型的训练、评估和注册功能。

使用示例：
    # 逻辑回归（WOE编码）
    python -m datamind.demo.train

    # 逻辑回归（无编码）
    python -m datamind.demo.train --encoder none

    # 逻辑回归（标准化编码）
    python -m datamind.demo.train --encoder standard

    # 随机森林
    python -m datamind.demo.train --model random_forest

    # 自定义模型名称和版本
    python -m datamind.demo.train --model_name my_model --model_version 2.0.0

    # 强制覆盖已存在的模型
    python -m datamind.demo.train --force

    # 只保存本地文件，不注册
    python -m datamind.demo.train --local --output ./model.pkl
"""

import os
import argparse
import logging
import tempfile
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from datamind.config import get_settings
from datamind.core.domain.enums import Framework, ModelType, TaskType
from datamind.core.db.database import db_manager
from datamind.core.model import get_model_registry
from datamind.demo.binning_config import BINNING_CONFIG

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()
model_registry = get_model_registry()


@dataclass
class ScorecardConfig:
    """评分卡参数配置

    属性:
        base_score: 基准分，对应 base_odds 时的分数
        pdo: 分数翻倍比（Points to Double the Odds）
        base_odds: 基准 odds，对应 base_score 时的 odds
        min_score: 最低分限制
        max_score: 最高分限制
        direction: 评分方向，higher_better 或 lower_better
    """
    base_score: int = 600
    pdo: int = 50
    base_odds: float = 20.0
    min_score: int = 300
    max_score: int = 900
    direction: str = "higher_better"


# 全局默认配置
DEFAULT_SCORECARD_CONFIG = ScorecardConfig()


def generate_data(n_samples: int = 10000) -> Tuple[pd.DataFrame, np.ndarray]:
    """
    生成示例信贷数据

    参数:
        n_samples: 样本数量，默认 10000

    返回:
        (特征DataFrame, 标签数组)
    """
    np.random.seed(42)

    X = pd.DataFrame({
        "age": np.random.normal(35, 10, n_samples).clip(18, 80),
        "income": np.random.normal(50000, 20000, n_samples).clip(0, 200000),
        "debt_ratio": np.random.beta(2, 5, n_samples) * 0.6,
        "credit_history": np.random.normal(700, 50, n_samples).clip(300, 850),
        "employment_years": np.random.exponential(5, n_samples).clip(0, 40),
        "loan_amount": np.random.normal(50000, 30000, n_samples).clip(1000, 200000),
    })

    # 风险评分计算
    age_norm = (X["age"] - 35) / 10
    income_norm = (X["income"] - 50000) / 20000
    debt_ratio_norm = X["debt_ratio"] * 2
    credit_history_norm = (X["credit_history"] - 700) / 50
    employment_years_norm = X["employment_years"] / 10
    loan_amount_norm = X["loan_amount"] / 50000

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
    threshold = np.percentile(prob, 85)
    y = (prob > threshold).astype(int)

    return X, y


def woe_transform(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    WOE（Weight of Evidence）转换

    参数:
        df: 原始特征数据
        config: 分箱配置字典

    返回:
        WOE转换后的数据
    """
    df_woe = pd.DataFrame(index=df.index)
    for col in df.columns:
        if col not in config:
            df_woe[col] = df[col]
            continue
        bins = config[col]
        df_woe[col] = df[col].apply(
            lambda x: next((b.woe for b in bins if b.contains(x)), bins[-1].woe if bins else 0.0)
        )
    return df_woe


def encode_features(
        X: pd.DataFrame,
        encoder: str,
        feature_names: List[str]
) -> pd.DataFrame:
    """
    特征编码

    参数:
        X: 原始特征数据
        encoder: 编码方式，可选值：'woe', 'standard', 'none'
        feature_names: 特征名称列表

    返回:
        编码后的特征数据
    """
    if encoder == "woe":
        return woe_transform(X, BINNING_CONFIG)[feature_names]
    elif encoder == "standard":
        scaler = StandardScaler()
        return pd.DataFrame(
            scaler.fit_transform(X[feature_names]),
            columns=feature_names,
            index=X.index
        )
    else:
        return X[feature_names]


def train_logistic_regression(
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        feature_names: List[str],
        encoder: str = "woe"
) -> Tuple[LogisticRegression, Dict[str, float], float, Optional[pd.DataFrame]]:
    """
    训练逻辑回归模型

    参数:
        X_train: 训练特征数据
        y_train: 训练标签
        feature_names: 特征名称列表
        encoder: 编码方式，默认 'woe'

    返回:
        (模型, 特征系数, 截距, 编码后的训练数据)
    """
    X_encoded = encode_features(X_train, encoder, feature_names)

    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(X_encoded.values, y_train)

    coef = {col: float(model.coef_[0][i]) for i, col in enumerate(feature_names)}
    intercept = float(model.intercept_[0])

    return model, coef, intercept, X_encoded


def train_random_forest(
        X_train: pd.DataFrame,
        y_train: np.ndarray,
        n_estimators: int = 100,
        max_depth: int = 5
) -> Pipeline:
    """
    训练随机森林模型

    参数:
        X_train: 训练特征数据
        y_train: 训练标签
        n_estimators: 决策树数量，默认 100
        max_depth: 树的最大深度，默认 5

    返回:
        包含标准化和随机森林的管道模型
    """
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            random_state=42
        ))
    ])
    pipeline.fit(X_train, y_train)
    return pipeline


def evaluate(
        model: Union[LogisticRegression, Pipeline],
        X_test: pd.DataFrame,
        y_test: np.ndarray,
        feature_names: List[str],
        encoder: str = "woe"
) -> Dict[str, Any]:
    """
    评估模型性能

    参数:
        model: 训练好的模型
        X_test: 测试特征数据
        y_test: 测试标签
        feature_names: 特征名称列表
        encoder: 编码方式，默认 'woe'

    返回:
        评估结果，包含 auc, accuracy, feature_importance
    """
    X_encoded = encode_features(X_test, encoder, feature_names)
    y_proba = model.predict_proba(X_encoded.values)[:, 1]
    y_pred = (y_proba > 0.5).astype(int)

    # 获取特征重要性
    if hasattr(model, "coef_"):
        importance = {col: float(abs(model.coef_[0][i])) for i, col in enumerate(feature_names)}
    elif hasattr(model, "named_steps"):
        rf = model.named_steps["classifier"]
        importance = {col: float(imp) for col, imp in zip(feature_names, rf.feature_importances_)}
    else:
        importance = {col: 0.0 for col in feature_names}

    return {
        "auc": roc_auc_score(y_test, y_proba),
        "accuracy": accuracy_score(y_test, y_pred),
        "feature_importance": importance,
    }


def _clean_none(obj: Any) -> Any:
    """
    递归清理 None 值

    BentoML 的 metadata 不支持 None 值，需要转换为空字符串。

    参数:
        obj: 待清理的对象

    返回:
        清理后的对象
    """
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return {k: _clean_none(v) for k, v in obj.items() if v is not None}
    if isinstance(obj, list):
        return [_clean_none(v) for v in obj if v is not None]
    return obj


def register(
        model: Union[LogisticRegression, Pipeline],
        model_name: str,
        model_version: str,
        feature_names: List[str],
        evaluation: Dict[str, Any],
        encoder: str = "woe",
        coef: Optional[Dict] = None,
        intercept: Optional[float] = None,
        scorecard_config: Optional[dict] = None,
        force: bool = False,
) -> str:
    """注册模型到模型注册中心"""
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
        joblib.dump(model, tmp.name)
        tmp_path = tmp.name

    try:
        # 如果未传入配置，使用默认配置
        if scorecard_config is None:
            config = DEFAULT_SCORECARD_CONFIG
            scorecard_config = asdict(config)
        else:
            scorecard_config = scorecard_config.copy()

        if encoder == "woe":
            binning_serializable = {}
            for col, bins in BINNING_CONFIG.items():
                binning_serializable[col] = [b.to_dict() for b in bins]
            scorecard_config["binning"] = binning_serializable
            scorecard_config["coefficients"] = coef or {}
            scorecard_config["intercept"] = intercept or 0.0

        scorecard_config = _clean_none(scorecard_config)
        model_params = _clean_none({"feature_importance": evaluation["feature_importance"]})

        if isinstance(model, LogisticRegression):
            model_type = ModelType.LOGISTIC_REGRESSION
        else:
            model_type = ModelType.RANDOM_FOREST

        # 强制覆盖：删除已存在的旧模型
        if force:
            try:
                from datamind.core.db.database import get_db
                from datamind.core.db.models import ModelMetadata, ModelVersionHistory
                from datamind.core.model import get_model_registry
                import shutil

                # 获取模型注册中心实例和缓存路径
                registry = get_model_registry()
                cache_path = registry.cache_path

                with get_db() as session:
                    old_model = session.query(ModelMetadata).filter_by(
                        model_name=model_name,
                        model_version=model_version
                    ).first()

                    if old_model:
                        old_model_id = old_model.model_id

                        # 删除版本历史记录
                        session.query(ModelVersionHistory).filter_by(model_id=old_model_id).delete()
                        # 删除模型元数据
                        session.delete(old_model)
                        session.commit()
                        logger.info("已删除数据库记录: %s v%s (ID: %s)",
                                    model_name, model_version, old_model_id)

                        # 从 BentoML 删除
                        try:
                            import bentoml
                            bentoml.models.delete(old_model_id.lower())
                            logger.info("已从 BentoML 删除模型: %s", old_model_id.lower())
                        except Exception as e:
                            logger.warning("从 BentoML 删除模型失败: %s", e)

                        # 删除本地缓存目录
                        model_dir = cache_path / old_model_id
                        if model_dir.exists():
                            shutil.rmtree(model_dir)
                            logger.info("已删除本地缓存目录: %s", model_dir)
                    else:
                        logger.debug("未找到旧模型: %s v%s", model_name, model_version)

            except Exception as e:
                logger.warning("删除旧模型失败: %s", e)

        model_id = model_registry.register_model(
            model_name=model_name,
            model_version=model_version,
            task_type=TaskType.SCORING,
            model_type=model_type,
            framework=Framework.SKLEARN,
            input_features=feature_names,
            output_schema={"score": "float", "probability": "float"},
            created_by="demo",
            model_file=open(tmp_path, "rb"),
            description=f"AUC={evaluation['auc']:.4f}, encoder={encoder}",
            model_params=model_params,
            scorecard_config=scorecard_config,
        )

        model_registry.activate_model(model_id, operator="demo")
        model_registry.promote_to_production(model_id, operator="demo")

        return model_id
    finally:
        os.unlink(tmp_path)


def train(
        model_type: str = "logistic_regression",
        encoder: str = "woe",
        model_name: Optional[str] = None,
        model_version: str = "1.0.0",
        local: bool = False,
        output_path: Optional[str] = None,
        scorecard_config: Optional[dict] = None,
        force: bool = False,
) -> Dict[str, Any]:
    """
    训练模型主函数

    参数:
        model_type: 模型类型，可选值：'logistic_regression', 'random_forest'
        encoder: 编码方式，仅对逻辑回归有效，可选值：'woe', 'standard', 'none'
        model_name: 自定义模型名称，不指定时自动生成
        model_version: 模型版本，默认 '1.0.0'
        local: 是否只保存到本地文件（不注册）
        output_path: 本地输出路径
        scorecard_config: 评分卡配置字典，默认使用 DEFAULT_SCORECARD_CONFIG
        force: 是否强制覆盖已存在的模型，默认 False

    返回:
        训练结果，包含 success, model_id 或 path, auc 等字段
    """
    logger.info("=" * 50)
    logger.info("训练模型: model_type=%s, encoder=%s", model_type, encoder)
    if force:
        logger.info("强制覆盖模式: 已存在的同名模型将被覆盖")

    # 构建评分卡配置字典
    if scorecard_config is None:
        config = DEFAULT_SCORECARD_CONFIG
        scorecard_config = asdict(config)
        logger.info("使用默认评分卡参数: base_score=%s, pdo=%s, min_score=%s, max_score=%s",
                   scorecard_config["base_score"], scorecard_config["pdo"],
                   scorecard_config["min_score"], scorecard_config["max_score"])

    # 生成数据
    X, y = generate_data()
    feature_names = list(X.columns)

    # 划分数据集
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # 训练模型
    if model_type == "logistic_regression":
        logger.info("训练逻辑回归模型...")
        trained_model, coef, intercept, _ = train_logistic_regression(
            X_train, y_train, feature_names, encoder
        )
        evaluation = evaluate(trained_model, X_test, y_test, feature_names, encoder)
    elif model_type == "random_forest":
        logger.info("训练随机森林模型...")
        trained_model = train_random_forest(X_train, y_train)
        evaluation = evaluate(trained_model, X_test, y_test, feature_names, encoder="none")
        coef = intercept = None
    else:
        raise ValueError(f"不支持的模型类型: {model_type}")

    logger.info("评估结果 - AUC: %.4f, Accuracy: %.4f", evaluation["auc"], evaluation["accuracy"])

    # 生成模型名称
    if model_name is None:
        if model_type == "logistic_regression":
            if encoder == "woe":
                model_name = "demo_logistic_woe"
            elif encoder == "standard":
                model_name = "demo_logistic_standard"
            else:
                model_name = "demo_logistic_raw"
        else:
            model_name = "demo_random_forest"

    # 保存或注册模型
    if local:
        path = output_path or f"{model_name}_{model_version}.pkl"
        joblib.dump(trained_model, path)
        logger.info("模型已保存到本地: %s", path)
        return {"success": True, "path": path, "auc": evaluation["auc"]}
    else:
        db_manager.initialize()
        model_id = register(
            model=trained_model,
            model_name=model_name,
            model_version=model_version,
            feature_names=feature_names,
            evaluation=evaluation,
            encoder=encoder,
            coef=coef,
            intercept=intercept,
            scorecard_config=scorecard_config,
            force=force,
        )
        logger.info("模型注册成功，模型ID: %s", model_id)
        return {"success": True, "model_id": model_id, "auc": evaluation["auc"]}


def main():
    """命令行入口函数"""
    parser = argparse.ArgumentParser(
        description="训练示例评分卡模型",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python -m datamind.demo.train
  python -m datamind.demo.train --encoder standard
  python -m datamind.demo.train --model_type random_forest
  python -m datamind.demo.train --model_name my_model --model_version 2.0.0
  python -m datamind.demo.train --force
  python -m datamind.demo.train --local --output ./model.pkl
        """
    )
    parser.add_argument(
        "--model_type", choices=["logistic_regression", "random_forest"],
        default="logistic_regression", help="模型类型，默认为 logistic_regression"
    )
    parser.add_argument(
        "--encoder", choices=["woe", "standard", "none"],
        default="woe", help="特征编码方式，仅对逻辑回归有效，默认为 woe"
    )
    parser.add_argument("--model_name", help="自定义模型名称")
    parser.add_argument("--model_version", default="1.0.0", help="模型版本，默认为 1.0.0")
    parser.add_argument("--local", action="store_true", help="仅保存到本地文件，不注册到模型中心")
    parser.add_argument("--output", help="本地输出路径，仅在 --local 模式下有效")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在的同名模型")

    args = parser.parse_args()

    # 随机森林模式忽略 encoder 参数
    if args.model_type == "random_forest" and args.encoder != "woe":
        logger.info("随机森林模型忽略 --encoder 参数，使用默认标准化编码")

    result = train(
        model_type=args.model_type,
        encoder=args.encoder,
        model_name=args.model_name,
        model_version=args.model_version,
        local=args.local,
        output_path=args.output,
        force=args.force,
    )

    if result["success"]:
        print(f"\n训练成功！AUC: {result['auc']:.4f}")
        if "model_id" in result:
            print(f"模型ID: {result['model_id']}")
        if "path" in result:
            print(f"保存路径: {result['path']}")
    else:
        print(f"\n训练失败: {result.get('message', '未知错误')}")


if __name__ == "__main__":
    main()