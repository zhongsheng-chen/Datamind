# examples/scorecard/train.py

"""信用评分卡模型训练示例

使用带缺失值和类别变量的可复现合成信贷数据，训练信用评分卡。

使用示例：
  python examples/scorecard/train.py
  python examples/scorecard/train.py --output ./scorecard.pkl
"""

import argparse
import math
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from optbinning import BinningProcess, Scorecard
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split


SAMPLE_SIZE = 5000
RANDOM_SEED = 42
DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "artifacts"
    / "scorecard.pkl"
)

FEATURE_NAMES = [
    "age",
    "annual_income",
    "debt_to_income_ratio",
    "credit_utilization_ratio",
    "delinquency_count",
    "credit_history_years",
    "employment_type",
    "residence_status",
]

CATEGORICAL_FEATURES = [
    "employment_type",
    "residence_status",
]

NUMERICAL_FEATURES = [
    name
    for name in FEATURE_NAMES
    if name not in CATEGORICAL_FEATURES
]

MANUAL_NUMERICAL_SPLITS = {
    "age": [30, 40, 50, 60],
    "annual_income": [60_000, 100_000, 160_000, 250_000],
    "debt_to_income_ratio": [0.15, 0.30, 0.45, 0.60],
    "credit_utilization_ratio": [0.20, 0.40, 0.60],
    "delinquency_count": [0.5, 1.5],
    "credit_history_years": [2, 5, 10, 15],
}

MANUAL_CATEGORICAL_SPLITS = {
    "employment_type": [
        ["salaried"],
        ["self_employed"],
        ["contract", "unemployed"],
    ],
    "residence_status": [
        ["owner", "mortgage"],
        ["rent", "family"],
    ],
}

SCORING_CONFIG = {
    "base_score": 650.0,
    "base_odds": 45.0,
    "pdo": 40.0,
    "min_score": 90.0,
    "max_score": 900.0,
}


def validate_n_jobs(n_jobs: int) -> int:
    """校验并行任务数不超过本机逻辑处理器数量"""
    processor_count = os.cpu_count() or 1

    if (
            not isinstance(n_jobs, bool)
            and isinstance(n_jobs, int)
            and (
                n_jobs == -1
                or 1 <= n_jobs <= processor_count
            )
    ):
        return n_jobs

    raise ValueError(
        "n_jobs 必须为 -1，或介于 1 和 "
        f"{processor_count} 之间"
    )


def parse_n_jobs(value: str) -> int:
    """解析命令行并行任务数"""
    try:
        return validate_n_jobs(
            int(value)
        )
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            str(error)
        ) from error


def parse_split_size(value: str) -> int | float:
    """按 sklearn 约定解析样本数量或比例"""
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(
                "必须为整数样本数或浮点比例"
            ) from error


def _with_missing_values(
        values: NDArray[Any],
        *,
        rate: float,
        random: np.random.Generator,
) -> NDArray[Any]:
    """按指定比例注入缺失值"""
    result = values.astype(
        object,
        copy=True,
    )
    missing = random.random(
        len(result)
    ) < rate
    result[missing] = None

    return result


def build_training_data(
        *,
        sample_size: int = SAMPLE_SIZE,
        random_seed: int = RANDOM_SEED,
) -> tuple[pd.DataFrame, NDArray[np.int64]]:
    """构造包含类别变量和缺失值的合成信贷数据"""
    if sample_size < 500:
        raise ValueError(
            "sample_size 不能小于 500"
        )

    random = np.random.default_rng(
        random_seed
    )

    application_days_ago = random.integers(
        0,
        730,
        sample_size,
    )
    application_date = (
        pd.Timestamp.today().normalize()
        - pd.to_timedelta(
            application_days_ago,
            unit="D",
        )
    )

    age = random.integers(
        21,
        71,
        sample_size,
    ).astype(float)

    annual_income = np.clip(
        random.lognormal(
            mean=math.log(110_000),
            sigma=0.55,
            size=sample_size,
        ),
        24_000,
        600_000,
    )

    debt_to_income_ratio = np.clip(
        random.beta(
            2.0,
            4.5,
            sample_size,
        ),
        0,
        1,
    )

    credit_utilization_ratio = np.clip(
        random.beta(
            1.8,
            2.5,
            sample_size,
        ),
        0,
        1,
    )

    delinquency_count = np.clip(
        random.poisson(
            0.45,
            sample_size,
        ),
        0,
        6,
    ).astype(float)

    credit_history_years = np.clip(
        random.gamma(
            2.2,
            3.2,
            sample_size,
        ),
        0.25,
        35,
    )

    employment_type = random.choice(
        [
            "salaried",
            "self_employed",
            "contract",
            "unemployed",
        ],
        size=sample_size,
        p=[
            0.58,
            0.22,
            0.16,
            0.04,
        ],
    )

    residence_status = random.choice(
        [
            "owner",
            "mortgage",
            "rent",
            "family",
        ],
        size=sample_size,
        p=[
            0.22,
            0.35,
            0.35,
            0.08,
        ],
    )

    income_missing = random.random(
        sample_size
    ) < 0.03
    history_missing = random.random(
        sample_size
    ) < 0.02
    employment_missing = random.random(
        sample_size
    ) < 0.02

    observed_income = annual_income.copy()
    observed_income[income_missing] = np.nan

    observed_history = credit_history_years.copy()
    observed_history[history_missing] = np.nan

    observed_employment = employment_type.astype(
        object,
        copy=True,
    )
    observed_employment[employment_missing] = None

    features = pd.DataFrame({
        "application_date": application_date,
        "age": age,
        "annual_income": observed_income,
        "debt_to_income_ratio": debt_to_income_ratio,
        "credit_utilization_ratio": credit_utilization_ratio,
        "delinquency_count": delinquency_count,
        "credit_history_years": observed_history,
        "employment_type": observed_employment,
        "residence_status": _with_missing_values(
            residence_status,
            rate=0.015,
            random=random,
        ),
    })

    employment_risk = pd.Series(
        employment_type
    ).map({
        "salaried": -0.25,
        "self_employed": 0.10,
        "contract": 0.35,
        "unemployed": 0.95,
    }).to_numpy(
        dtype=float
    )

    residence_risk = pd.Series(
        residence_status
    ).map({
        "owner": -0.30,
        "mortgage": -0.12,
        "rent": 0.22,
        "family": 0.10,
    }).to_numpy(
        dtype=float
    )

    log_odds = (
        -3.45
        - 0.018 * (age - 35)
        - 0.000004 * (annual_income - 100_000)
        + 3.1 * debt_to_income_ratio
        + 2.3 * credit_utilization_ratio
        + 0.62 * delinquency_count
        - 0.055 * (credit_history_years - 5)
        + employment_risk
        + residence_risk
        + 0.35 * income_missing
        + 0.30 * history_missing
        + 0.40 * employment_missing
        + 0.12
        * (
            application_days_ago
            / 365
        )
        + 0.08
        * np.sin(
            2
            * np.pi
            * application_date.month.to_numpy()
            / 12
        )
    )

    probabilities = 1 / (
        1 + np.exp(-log_odds)
    )

    labels: NDArray[np.int64] = np.asarray(
        random.binomial(
            1,
            probabilities,
        ),
        dtype=np.int64,
    )

    return features, labels


def split_out_of_time(
        features: pd.DataFrame,
        labels: NDArray[np.int64],
        *,
        train_size: int | float | None = None,
        test_size: int | float | None = None,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    NDArray[np.int64],
    NDArray[np.int64],
]:
    """按申请日期进行训练集和跨时间测试集切分"""
    order = np.argsort(
        features[
            "application_date"
        ].to_numpy()
    )
    ordered_features = features.iloc[
        order
    ].reset_index(
        drop=True
    )
    ordered_labels = labels[order]

    return train_test_split(
        ordered_features,
        ordered_labels,
        train_size=train_size,
        test_size=test_size,
        shuffle=False,
    )


def train_model(
        features: pd.DataFrame,
        labels: NDArray[np.int64],
        *,
        n_jobs: int = -1,
        random_seed: int = RANDOM_SEED,
) -> Scorecard:
    """构造并训练信用评分卡"""
    n_jobs = validate_n_jobs(n_jobs)

    numerical_binning_params = {
        name: {
            "monotonic_trend": None,
            "max_pvalue": None,
            "user_splits": splits,
            "user_splits_fixed": [True] * len(splits),
        }
        for name, splits in MANUAL_NUMERICAL_SPLITS.items()
    }

    categorical_binning_params = {
        name: {
            "cat_unknown": 0.0,
            "monotonic_trend": None,
            "max_pvalue": None,
            "user_splits": splits,
            "user_splits_fixed": [True] * len(splits),
        }
        for name, splits in MANUAL_CATEGORICAL_SPLITS.items()
    }

    binning_fit_params: dict[
        str,
        dict[str, Any],
    ] = {
        **numerical_binning_params,
        **categorical_binning_params,
    }

    binning_transform_params = {
        name: {
            "metric": "woe",
            "metric_missing": "empirical",
            "metric_special": "empirical",
        }
        for name in FEATURE_NAMES
    }

    binning_process = BinningProcess(
        variable_names=FEATURE_NAMES,
        categorical_variables=CATEGORICAL_FEATURES,
        max_n_prebins=20,
        min_prebin_size=0.03,
        max_n_bins=6,
        min_bin_size=0.05,
        max_pvalue=0.10,
        max_pvalue_policy="consecutive",
        binning_fit_params=binning_fit_params,
        binning_transform_params=(
            binning_transform_params
        ),
        n_jobs=n_jobs,
    )

    estimator = LogisticRegression(
        C=np.inf,
        solver="lbfgs",
        max_iter=1000,
        random_state=random_seed,
    )

    model = Scorecard(
        binning_process=binning_process,
        estimator=estimator,
        scaling_method="pdo_odds",
        scaling_method_params={
            "pdo": SCORING_CONFIG["pdo"],
            "odds": SCORING_CONFIG["base_odds"],
            "scorecard_points": SCORING_CONFIG[
                "base_score"
            ],
        },
    )
    model.fit(
        features,
        labels,
        metric_missing="empirical",
        metric_special="empirical",
    )

    return model


def evaluate_model(
        model: Scorecard,
        features: pd.DataFrame,
        labels: NDArray[np.int64],
) -> dict[str, float]:
    """计算留出集 AUC、Gini 和 KS"""
    probabilities = model.predict_proba(
        features
    )[:, 1]

    auc = float(
        roc_auc_score(
            labels,
            probabilities,
        )
    )

    false_positive_rate, true_positive_rate, _ = (
        roc_curve(
            labels,
            probabilities,
        )
    )

    ks = float(
        np.max(
            true_positive_rate
            - false_positive_rate
        )
    )

    return {
        "auc": auc,
        "gini": 2 * auc - 1,
        "ks": ks,
        "bad_rate": float(
            np.mean(labels)
        ),
    }


def save_model(
        model: Scorecard,
        output_path: Path,
) -> Path:
    """保存评分卡"""
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


def print_binning_summary(
        model: Scorecard,
) -> None:
    """打印分箱摘要"""
    print("\n分箱摘要：")
    print(
        model.binning_process_.summary().to_string(
            index=False
        )
    )


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="训练信用评分卡示例模型",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="评分卡保存路径",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=SAMPLE_SIZE,
        help="合成数据总样本数（划分前）",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=RANDOM_SEED,
        help="随机种子",
    )
    parser.add_argument(
        "--train-size",
        type=parse_split_size,
        default=None,
        help="训练集大小：整数表示数量，小数表示比例",
    )
    parser.add_argument(
        "--test-size",
        type=parse_split_size,
        default=None,
        help="测试集大小：整数表示数量，小数表示比例",
    )
    parser.add_argument(
        "--n-jobs",
        type=parse_n_jobs,
        default=-1,
        help="并行分箱任务数，-1 表示使用全部处理器",
    )

    return parser.parse_args()


def main() -> None:
    """执行训练、测试和保存流程"""
    arguments = parse_arguments()
    features, labels = build_training_data(
        sample_size=arguments.sample_size,
        random_seed=arguments.random_seed,
    )

    (
        training_features,
        test_features,
        training_labels,
        test_labels,
    ) = split_out_of_time(
        features,
        labels,
        train_size=arguments.train_size,
        test_size=arguments.test_size,
    )

    model = train_model(
        training_features,
        training_labels,
        n_jobs=arguments.n_jobs,
        random_seed=arguments.random_seed,
    )
    metrics = evaluate_model(
        model,
        test_features,
        test_labels,
    )
    output_path = save_model(
        model,
        arguments.output,
    )

    sample = test_features.iloc[
        [0]
    ]
    sample_probability = float(
        model.predict_proba(
            sample
        )[0, 1]
    )
    sample_score = float(
        model.score(sample)[0]
    )

    print("评分卡训练完成")
    print(f"评分卡保存路径：{output_path}")
    print("\n数据划分")
    print(
        f"训练集：{len(training_features):,} 条，"
        f"{training_features['application_date'].min().date()}"
        " 至 "
        f"{training_features['application_date'].max().date()}"
    )
    print(
        f"测试集：{len(test_features):,} 条，"
        f"{test_features['application_date'].min().date()}"
        " 至 "
        f"{test_features['application_date'].max().date()}"
    )

    print("\n测试指标")
    print(f"坏样本率：{metrics['bad_rate']:.2%}")
    print(f"AUC：{metrics['auc']:.4f}")
    print(f"Gini：{metrics['gini']:.4f}")
    print(f"KS：{metrics['ks']:.4f}")

    print("\n评分示例")
    print(f"违约概率：{sample_probability:.4%}")
    print(f"信用分：{sample_score:.2f}")
    print_binning_summary(
        model
    )


if __name__ == "__main__":
    main()
