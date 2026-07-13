# examples/scorecard/train.py

"""信用评分模型训练示例

使用可复现的合成数据训练逻辑回归模型并保存制品。

核心功能：
  - build_training_data: 构造合成训练数据
  - train_model: 训练逻辑回归模型
  - save_model: 保存模型制品
  - main: 执行训练流程

使用示例：
  python examples/scorecard/train.py
  python examples/scorecard/train.py --output ./scorecard.pkl
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import LogisticRegression


SAMPLE_COUNT = 1000
RANDOM_SEED = 42
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "scorecard.pkl"
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
        "age": random.integers(
            18,
            71,
            sample_count,
        ),
        "annual_income": random.uniform(
            20,
            200,
            sample_count,
        ),
        "debt_to_income_ratio": random.uniform(
            0,
            1,
            sample_count,
        ),
        "credit_utilization_ratio": random.uniform(
            0,
            1,
            sample_count,
        ),
        "delinquency_count": random.poisson(
            0.8,
            sample_count,
        ),
    })
    log_odds = (
        -1.2
        - 0.012 * features["age"]
        - 0.008 * features["annual_income"]
        + 2.4 * features["debt_to_income_ratio"]
        + 2.0 * features["credit_utilization_ratio"]
        + 0.5 * features["delinquency_count"]
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
) -> LogisticRegression:
    """训练逻辑回归模型"""
    model = LogisticRegression(
        max_iter=1000,
        random_state=RANDOM_SEED,
    )
    model.fit(
        features,
        labels,
    )

    return model


def save_model(
        model: LogisticRegression,
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
        description="训练信用评分示例模型",
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
