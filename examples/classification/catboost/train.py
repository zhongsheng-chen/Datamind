"""CatBoost 分类模型训练示例.

使用可复现的合成数据训练 CatBoost 二分类模型，并保存原生 CBM 制品。

使用示例：
  python examples/classification/catboost/train.py
  python examples/classification/catboost/train.py --output ./catboost.cbm
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.datasets import make_classification
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split


SAMPLE_COUNT = 2000
RANDOM_SEED = 42
TEST_SIZE = 0.25
NEGATIVE_LABEL = "benign"
POSITIVE_LABEL = "fraudulent"
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
    / "catboost.cbm"
)


def build_training_data(
        *,
        sample_count: int = SAMPLE_COUNT,
        random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, pd.Series]:
    """构造可复现的交易风险二分类数据."""
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
    labels = pd.Series(
        np.where(
            generated_labels == 1,
            POSITIVE_LABEL,
            NEGATIVE_LABEL,
        ),
        name="label",
    )

    return features, labels


def split_training_data(
        features: pd.DataFrame,
        labels: pd.Series,
        *,
        test_size: float = TEST_SIZE,
        random_seed: int = RANDOM_SEED,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.Series,
    pd.Series,
]:
    """按标签分层划分训练集和测试集."""
    return train_test_split(
        features,
        labels,
        test_size=test_size,
        random_state=random_seed,
        stratify=labels,
    )


def train_model(
        features: pd.DataFrame,
        labels: pd.Series,
        *,
        random_seed: int = RANDOM_SEED,
) -> CatBoostClassifier:
    """训练 CatBoost 分类模型."""
    model = CatBoostClassifier(
        iterations=100,
        depth=6,
        learning_rate=0.08,
        loss_function="Logloss",
        random_seed=random_seed,
        thread_count=1,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(features, labels)

    return model


def evaluate_model(
        model: CatBoostClassifier,
        features: pd.DataFrame,
        labels: pd.Series,
) -> dict[str, float]:
    """计算测试集准确率和 ROC AUC."""
    predictions = np.asarray(model.predict(features)).reshape(-1)
    probabilities = model.predict_proba(features)[:, 1]

    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "auc": float(roc_auc_score(
            labels == POSITIVE_LABEL,
            probabilities,
        )),
    }


def save_model(model: CatBoostClassifier, output_path: Path) -> Path:
    """保存 Datamind 加载器支持的原生 CBM 制品."""
    resolved_path = output_path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(resolved_path), format="cbm")

    return resolved_path


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(
        description="训练 CatBoost 风险分类示例模型",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--sample-count", type=int, default=SAMPLE_COUNT)
    parser.add_argument("--random-seed", type=int, default=RANDOM_SEED)

    return parser.parse_args(arguments)


def main() -> None:
    """执行数据生成、划分、训练、评估和保存流程."""
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

    print("CatBoost 训练完成")
    print(f"类别标签：{NEGATIVE_LABEL} / {POSITIVE_LABEL}")
    print(f"训练集：{len(training_features):,} 条")
    print(f"测试集：{len(test_features):,} 条")
    print(f"测试集准确率：{metrics['accuracy']:.4f}")
    print(f"测试集 AUC：{metrics['auc']:.4f}")
    print(f"模型文件：{output_path}")


if __name__ == "__main__":
    main()
