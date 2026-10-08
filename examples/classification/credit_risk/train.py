"""使用合成信贷数据训练信用风险分类演示模型.

标签 0 表示未违约，1 表示违约。运行示例：
  python examples/classification/credit_risk/train.py
"""

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split


FEATURE_NAMES = [
    "age",
    "annual_income",
    "debt_to_income_ratio",
    "credit_utilization_ratio",
    "delinquency_count",
]
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent / "artifacts" / "default_probability.pkl"
)


def build_training_data(
    *,
    sample_count: int = 2000,
    random_seed: int = 42,
) -> tuple[pd.DataFrame, np.ndarray]:
    """生成仅用于服务演示的借款人特征和违约标签."""
    if sample_count < 100:
        raise ValueError("sample_count 不能小于 100")
    random = np.random.default_rng(random_seed)
    features = pd.DataFrame(
        {
            "age": random.integers(21, 71, sample_count),
            "annual_income": np.clip(
                random.lognormal(np.log(110_000), 0.55, sample_count),
                24_000,
                600_000,
            ),
            "debt_to_income_ratio": random.beta(2.0, 4.5, sample_count),
            "credit_utilization_ratio": random.beta(1.8, 2.5, sample_count),
            "delinquency_count": random.poisson(0.45, sample_count),
        },
        columns=FEATURE_NAMES,
    )
    log_odds = (
        -3.0
        + 3.0 * features["debt_to_income_ratio"]
        + 1.5 * features["credit_utilization_ratio"]
        + 0.7 * features["delinquency_count"]
        - 0.5 * np.log(features["annual_income"] / 110_000)
    )
    probability = 1.0 / (1.0 + np.exp(-log_odds))
    labels = random.binomial(1, probability).astype(np.int64)
    return features, labels


def main() -> None:
    parser = argparse.ArgumentParser(description="训练信用风险分类演示模型")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    features, labels = build_training_data(random_seed=args.random_seed)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.25,
        random_state=args.random_seed,
        stratify=labels,
    )
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        min_samples_leaf=12,
        random_state=args.random_seed,
        n_jobs=1,
    )
    model.fit(x_train, y_train)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output)
    print("信用风险分类演示模型训练完成")
    print("标签：0 = 未违约，1 = 违约")
    print(f"测试集 AUC：{roc_auc_score(y_test, model.predict_proba(x_test)[:, 1]):.4f}")
    print(f"模型文件：{output}")


if __name__ == "__main__":
    main()
