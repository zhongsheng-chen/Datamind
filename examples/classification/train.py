"""风险分类模型训练示例

使用可复现的合成数据训练随机森林二分类模型并保存制品。

核心功能：
  - build_training_data: 构造合成训练数据
  - train_model: 训练随机森林分类模型
  - save_model: 保存模型制品
  - main: 执行训练流程

使用示例：
  python examples/classification/train.py
  python examples/classification/train.py --output ./fraud.pkl
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.ensemble import RandomForestClassifier


SAMPLE_COUNT = 2000
RANDOM_SEED = 42
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "fraud.pkl"
)


def build_training_data(
        *,
        sample_count: int = SAMPLE_COUNT,
        random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, NDArray[np.int_]]:
    """构造合成训练数据"""
    random = np.random.default_rng(
        random_seed
    )
    features = pd.DataFrame({
        "transaction_amount": random.lognormal(
            mean=6.5,
            sigma=1.0,
            size=sample_count,
        ),
        "account_age_days": random.integers(
            1,
            3651,
            sample_count,
        ),
        "transaction_hour": random.integers(
            0,
            24,
            sample_count,
        ),
        "distance_from_home": np.clip(
            random.exponential(
                scale=30,
                size=sample_count,
            ),
            0,
            300,
        ),
        "recent_transaction_count": random.poisson(
            3,
            sample_count,
        ),
    })
    unusual_hour = (
        (features["transaction_hour"] <= 5)
        | (features["transaction_hour"] >= 23)
    ).astype(float)
    log_odds = (
        -4.0
        + features["transaction_amount"] / 2500
        - features["account_age_days"] / 4000
        + 1.6 * unusual_hour
        + features["distance_from_home"] / 100
        + 0.15 * features["recent_transaction_count"]
    )
    probabilities = 1 / (
        1 + np.exp(-log_odds)
    )
    labels = random.binomial(
        1,
        probabilities,
    ).astype(
        np.int_
    )

    return features, labels


def train_model(
        features: pd.DataFrame,
        labels: NDArray[np.int_],
) -> RandomForestClassifier:
    """训练随机森林分类模型"""
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_leaf=5,
        random_state=RANDOM_SEED,
        n_jobs=1,
    )
    model.fit(
        features,
        labels,
    )

    return model


def save_model(
        model: RandomForestClassifier,
        output_path: Path,
) -> Path:
    """保存模型制品"""
    resolved_path = output_path.resolve()
    resolved_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    joblib.dump(
        model,
        resolved_path,
    )

    return resolved_path


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="训练风险分类示例模型",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="模型制品输出路径",
    )

    return parser.parse_args()


def main() -> None:
    """执行训练流程"""
    arguments = parse_arguments()
    features, labels = build_training_data()
    model = train_model(
        features,
        labels,
    )
    output_path = save_model(
        model,
        arguments.output,
    )

    print("模型训练完成")
    print(f"模型文件：{output_path}")
    print(f"特征数量：{model.n_features_in_}")


if __name__ == "__main__":
    main()
