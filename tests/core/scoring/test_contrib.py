# tests/core/scoring/test_contrib.py

"""逻辑回归评分贡献测试

验证逻辑回归评分贡献分解器的能力声明、截距评分、
特征评分、原始评分、批量分解和异常处理。

核心功能：
  - 验证评分贡献能力
  - 验证截距评分和特征评分
  - 验证原始评分分解关系
  - 验证批量评分贡献
  - 验证正类方向
  - 验证默认特征名称
  - 验证模型参数和特征名称
  - 验证非法特征值
"""

import math
from typing import Any

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from datamind.config.scorecard import ScorecardConfig
from datamind.core.capability import ScorecardCapability
from datamind.core.inference import Inference
from datamind.core.scoring.contrib import LRContrib
from datamind.core.scoring.transformer import ScoreTransformer


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


@pytest.fixture
def binary_training_data(
) -> tuple[np.ndarray, np.ndarray]:
    """提供二分类训练数据"""
    X = np.array([
        [-2.0, -1.5],
        [-1.5, -0.8],
        [-1.0, -1.2],
        [-0.5, -0.2],
        [0.2, 0.1],
        [0.8, 0.6],
        [1.3, 1.0],
        [2.0, 1.5],
    ])

    y = np.array([
        1,
        1,
        1,
        1,
        0,
        0,
        0,
        0,
    ])

    return (
        X,
        y,
    )


@pytest.fixture
def logistic_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> LogisticRegression:
    """提供已训练逻辑回归模型"""
    X, y = binary_training_data

    model = LogisticRegression(
        max_iter=1000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.fixture
def inference(
        logistic_model: LogisticRegression,
) -> Inference:
    """提供统一推理实例"""
    return Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


@pytest.fixture
def transformer(
) -> ScoreTransformer:
    """提供评分转换器"""
    return ScoreTransformer(
        config=ScorecardConfig(
            base_score=600.0,
            base_odds=50.0,
            pdo=20.0,
            min_score=0.0,
            max_score=1000.0,
        )
    )


@pytest.fixture
def contrib(
        inference: Inference,
        transformer: ScoreTransformer,
) -> LRContrib:
    """提供评分贡献分解器"""
    return LRContrib(
        inference=inference,
        transformer=transformer,
    )


# noinspection PyUnresolvedReferences
def build_parameterized_logistic_model(
        *,
        coefficients: Any,
        intercepts: Any,
) -> LogisticRegression:
    """构造具有指定参数的逻辑回归模型"""
    model = LogisticRegression()

    model.classes_ = np.array([
        0,
        1,
    ])
    model.coef_ = np.asarray(
        coefficients,
        dtype=float,
    )
    model.intercept_ = np.asarray(
        intercepts,
        dtype=float,
    )
    model.n_features_in_ = int(
        model.coef_.shape[-1]
    )

    return model


def test_contrib_capabilities(
        contrib: LRContrib,
) -> None:
    """测试贡献分解器仅声明特征评分能力"""
    assert (
        contrib.get_capabilities()
        == ScorecardCapability.SCORECARD_FEATURE_SCORE
    )

    assert contrib.has_capability(
        ScorecardCapability.SCORECARD_FEATURE_SCORE
    )

    assert not contrib.has_capability(
        ScorecardCapability.SCORECARD_TOTAL_SCORE
    )

    assert not contrib.has_capability(
        ScorecardCapability.SCORECARD_LOGIT
    )


def test_init_uses_provided_dependencies(
        inference: Inference,
        transformer: ScoreTransformer,
) -> None:
    """测试初始化保留推理接口和评分转换器"""
    contrib = LRContrib(
        inference=inference,
        transformer=transformer,
    )

    assert contrib.inference is inference
    assert contrib.transformer is transformer
    assert contrib.factor == transformer.factor
    assert contrib.offset == transformer.offset


def test_init_creates_default_transformer(
        inference: Inference,
) -> None:
    """测试未提供转换器时创建默认实例"""
    contrib = LRContrib(
        inference=inference
    )

    assert isinstance(
        contrib.transformer,
        ScoreTransformer,
    )


def test_init_reads_model_parameters(
        logistic_model: LogisticRegression,
        contrib: LRContrib,
) -> None:
    """测试初始化读取逻辑回归系数和截距"""
    assert contrib.coef == pytest.approx(
        logistic_model.coef_[0].tolist()
    )

    assert contrib.intercept == pytest.approx(
        float(
            logistic_model.intercept_[0]
        )
    )

    assert contrib.feature_names == FEATURE_NAMES


def test_explain_matches_contribution_formula(
        logistic_model: LogisticRegression,
        contrib: LRContrib,
        transformer: ScoreTransformer,
) -> None:
    """测试评分贡献符合分解公式"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    values = np.array([
        -0.75,
        0.25,
    ])

    coefficients = logistic_model.coef_[0]

    expected_feature_values = (
        -transformer.factor
        * coefficients
        * values
    )

    expected_intercept_score = (
        transformer.offset
        - transformer.factor
        * float(
            logistic_model.intercept_[0]
        )
    )

    expected_feature_score = float(
        expected_feature_values.sum()
    )

    expected_raw_score = (
        expected_intercept_score
        + expected_feature_score
    )

    result = contrib.explain(
        features
    )

    assert list(
        result
    ) == [
        "intercept_score",
        "feature_score",
        "raw_score",
        "feature_a",
        "feature_b",
    ]

    assert result[
        "intercept_score"
    ] == pytest.approx(
        expected_intercept_score
    )

    assert result[
        "feature_a"
    ] == pytest.approx(
        float(
            expected_feature_values[0]
        )
    )

    assert result[
        "feature_b"
    ] == pytest.approx(
        float(
            expected_feature_values[1]
        )
    )

    assert result[
        "feature_score"
    ] == pytest.approx(
        expected_feature_score
    )

    assert result[
        "raw_score"
    ] == pytest.approx(
        expected_raw_score
    )


def test_raw_score_matches_model_logit_formula(
        logistic_model: LogisticRegression,
        contrib: LRContrib,
        transformer: ScoreTransformer,
) -> None:
    """测试原始评分与模型 Logit 转换一致"""
    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    logit = float(
        logistic_model.decision_function(
            array
        )[0]
    )

    expected = (
        transformer.offset
        - transformer.factor * logit
    )

    result = contrib.explain(
        features
    )

    assert result[
        "raw_score"
    ] == pytest.approx(
        expected
    )

    assert result[
        "raw_score"
    ] == pytest.approx(
        result["intercept_score"]
        + result["feature_score"]
    )


def test_explain_batch_matches_individual_results(
        contrib: LRContrib,
) -> None:
    """测试批量贡献分解与逐条结果一致"""
    features = [
        {
            "feature_b": 0.25,
            "feature_a": -0.75,
        },
        {
            "feature_b": 0.80,
            "feature_a": 1.20,
        },
    ]

    expected = [
        contrib.explain(
            item
        )
        for item in features
    ]

    result = contrib.explain_batch(
        features
    )

    assert result == pytest.approx(
        expected
    )


def test_explain_batch_preserves_input_order(
        contrib: LRContrib,
) -> None:
    """测试批量贡献分解保持输入顺序"""
    first = {
        "feature_a": -2.0,
        "feature_b": -1.5,
    }

    second = {
        "feature_a": 2.0,
        "feature_b": 1.5,
    }

    result = contrib.explain_batch([
        first,
        second,
    ])

    assert result[0] == pytest.approx(
        contrib.explain(
            first
        )
    )

    assert result[1] == pytest.approx(
        contrib.explain(
            second
        )
    )


def test_positive_class_zero_reverses_contributions(
        logistic_model: LogisticRegression,
        transformer: ScoreTransformer,
) -> None:
    """测试正类为类别零时反转模型参数方向"""
    inference = Inference(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    contrib = LRContrib(
        inference=inference,
        transformer=transformer,
    )

    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    values = np.array([
        -0.75,
        0.25,
    ])

    expected_coefficients = (
        -logistic_model.coef_[0]
    )

    expected_intercept = -float(
        logistic_model.intercept_[0]
    )

    expected_feature_values = (
        -transformer.factor
        * expected_coefficients
        * values
    )

    expected_intercept_score = (
        transformer.offset
        - transformer.factor
        * expected_intercept
    )

    result = contrib.explain(
        features
    )

    assert contrib.coef == pytest.approx(
        expected_coefficients.tolist()
    )

    assert contrib.intercept == pytest.approx(
        expected_intercept
    )

    assert result[
        "intercept_score"
    ] == pytest.approx(
        expected_intercept_score
    )

    assert result[
        "feature_a"
    ] == pytest.approx(
        float(
            expected_feature_values[0]
        )
    )

    assert result[
        "feature_b"
    ] == pytest.approx(
        float(
            expected_feature_values[1]
        )
    )


def test_default_feature_names_are_generated(
        logistic_model: LogisticRegression,
        transformer: ScoreTransformer,
) -> None:
    """测试未配置特征名称时生成默认名称"""
    inference = Inference(
        model=logistic_model,
        positive_class=1,
    )

    contrib = LRContrib(
        inference=inference,
        transformer=transformer,
    )

    assert contrib.feature_names == [
        "f0",
        "f1",
    ]


def test_feature_name_count_must_match_coefficient_count(
        logistic_model: LogisticRegression,
) -> None:
    """测试特征名称数量必须与模型系数数量一致"""
    inference = Inference(
        model=logistic_model,
        feature_names=[
            "feature_a",
        ],
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征名称数量与模型系数数量不一致",
    ):
        LRContrib(
            inference=inference
        )


@pytest.mark.parametrize(
    "reserved_name",
    [
        "intercept_score",
        "feature_score",
        "raw_score",
    ],
)
def test_reserved_feature_names_are_rejected(
        logistic_model: LogisticRegression,
        reserved_name: str,
) -> None:
    """测试拒绝评分贡献保留字段作为特征名"""
    inference = Inference(
        model=logistic_model,
        feature_names=[
            reserved_name,
            "feature_b",
        ],
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征名称与评分贡献保留字段冲突",
    ):
        LRContrib(
            inference=inference
        )


def test_non_2d_coefficients_are_rejected(
) -> None:
    """测试拒绝非二维逻辑回归系数"""
    model = build_parameterized_logistic_model(
        coefficients=[
            0.5,
            -0.25,
        ],
        intercepts=[
            0.1,
        ],
    )

    inference = Inference(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            NotImplementedError,
            match="仅支持二维 coef_",
    ):
        LRContrib(
            inference=inference
        )


def test_multiple_coefficient_outputs_are_rejected(
) -> None:
    """测试拒绝多输出逻辑回归系数"""
    model = build_parameterized_logistic_model(
        coefficients=[
            [
                0.5,
                -0.25,
            ],
            [
                -0.2,
                0.4,
            ],
        ],
        intercepts=[
            0.1,
        ],
    )

    inference = Inference(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            NotImplementedError,
            match="仅支持二分类单输出逻辑回归模型",
    ):
        LRContrib(
            inference=inference
        )


def test_multiple_intercepts_are_rejected(
) -> None:
    """测试拒绝多个逻辑回归截距"""
    model = build_parameterized_logistic_model(
        coefficients=[
            [
                0.5,
                -0.25,
            ],
        ],
        intercepts=[
            0.1,
            0.2,
        ],
    )

    inference = Inference(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            NotImplementedError,
            match="仅支持单一截距的二分类模型",
    ):
        LRContrib(
            inference=inference
        )


def test_random_forest_is_rejected(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试非逻辑回归模型不能用于贡献分解"""
    X, y = binary_training_data

    model = RandomForestClassifier(
        n_estimators=20,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    inference = Inference(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        LRContrib(
            inference=inference
        )


@pytest.mark.parametrize(
    (
        "value",
        "message",
    ),
    [
        (
            None,
            "逻辑回归特征必须是有限数值",
        ),
        (
            "invalid",
            "逻辑回归特征必须是数值",
        ),
        (
            math.nan,
            "逻辑回归特征必须是有限数值",
        ),
        (
            math.inf,
            "逻辑回归特征必须是有限数值",
        ),
        (
            -math.inf,
            "逻辑回归特征必须是有限数值",
        ),
    ],
)
def test_invalid_feature_values_are_rejected(
        contrib: LRContrib,
        value: Any,
        message: str,
) -> None:
    """测试拒绝非法逻辑回归特征值"""
    features = {
        "feature_a": value,
        "feature_b": 0.25,
    }

    with pytest.raises(
            ValueError,
            match=message,
    ):
        contrib.explain(
            features
        )


def test_missing_feature_is_rejected(
        contrib: LRContrib,
) -> None:
    """测试缺失特征转换为 NaN 后被拒绝"""
    with pytest.raises(
            ValueError,
            match="逻辑回归特征必须是有限数值",
    ):
        contrib.explain({
            "feature_a": 0.1,
        })


def test_empty_batch_is_rejected(
        contrib: LRContrib,
) -> None:
    """测试拒绝空批量输入"""
    with pytest.raises(
            ValueError,
            match="features_list 不能为空",
    ):
        contrib.explain_batch(
            []
        )
