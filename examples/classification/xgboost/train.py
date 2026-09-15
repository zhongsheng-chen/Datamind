"""XGBoost 分类模型训练示例

使用可复现的合成数据训练 XGBoost 二分类模型，并保存原生 Booster 制品。

使用示例：
  python examples/classification/xgboost/train.py
  python examples/classification/xgboost/train.py --output ./xgboost.ubj
"""

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.datasets import make_classification
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier


SAMPLE_COUNT = 2000
RANDOM_SEED = 42
TEST_SIZE = 0.25
FEATURE_NAMES = [
    "transaction_amount",
    "account_age_days",
    "transaction_hour",
    "distance_from_home",
    "recent_transaction_count",
]
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "xgboost.ubj"
)


def build_training_data(
        *,
        sample_count: int = SAMPLE_COUNT,
        random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, NDArray[Any]]:
    """构造可复现的交易风险二分类数据。"""
    if sample_count < 100:
        raise ValueError("sample_count 不能小于 100")

    values, generated_labels = make_classification(
        n_samples=sample_count,
        n_features=len(FEATURE_NAMES),
        n_informative=4,
        n_redundant=1,
        weights=[0.85, 0.15],
        class_sep=1.2,
        random_state=random_seed,
    )
    features = pd.DataFrame(values, columns=FEATURE_NAMES)
    labels: NDArray[Any] = generated_labels

    return features, labels


def split_training_data(
        features: pd.DataFrame,
        labels: NDArray[np.int64],
        *,
        test_size: float = TEST_SIZE,
        random_seed: int = RANDOM_SEED,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    NDArray[np.int64],
    NDArray[np.int64],
]:
    """按标签分层划分训练集和测试集。"""
    return train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=random_seed,
        stratify=labels,
    )


def train_model(
        features: pd.DataFrame,
        labels: NDArray[np.int64],
        *,
        random_seed: int = RANDOM_SEED,
) -> XGBClassifier:
    """训练 XGBoost 分类模型。"""
    model = XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.08,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="logloss",
        random_state=random_seed,
        n_jobs=1,
    )
    model.fit(features, labels)

    return model


def evaluate_model(
        model: XGBClassifier,
        features: pd.DataFrame,
        labels: NDArray[np.int64],
) -> dict[str, float]:
    """计算测试集准确率和 ROC AUC。"""
    predictions = model.predict(features)
    probabilities = model.predict_proba(features)[:, 1]

    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "auc": float(roc_auc_score(labels, probabilities)),
    }


def save_model(model: XGBClassifier, output_path: Path) -> Path:
    """保存 Datamind 加载器支持的原生 Booster 制品。"""
    resolved_path = output_path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(resolved_path)

    return resolved_path


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="训练 XGBoost 风险分类示例模型",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--sample-count", type=int, default=SAMPLE_COUNT)
    parser.add_argument("--random-seed", type=int, default=RANDOM_SEED)

    return parser.parse_args()


def main() -> None:
    """执行数据生成、划分、训练、评估和保存流程。"""
    arguments = parse_arguments()
    features, labels = build_training_data(
        sample_count=arguments.sample_count,
        random_seed=arguments.random_seed,
    )
    (
        training_features,
        test_features,
        training_labels,
        test_labels,
    ) = split_training_data(
        features,
        labels,
        random_seed=arguments.random_seed,
    )
    model = train_model(
        training_features,
        training_labels,
        random_seed=arguments.random_seed,
    )
    metrics = evaluate_model(model, test_features, test_labels)
    output_path = save_model(model, arguments.output)

    print("XGBoost 训练完成")
    print(f"训练集：{len(training_features):,} 条")
    print(f"测试集：{len(test_features):,} 条")
    print(f"测试集准确率：{metrics['accuracy']:.4f}")
    print(f"测试集 AUC：{metrics['auc']:.4f}")
    print(f"模型文件：{output_path}")


if __name__ == "__main__":
    main()
