# tests/core/model/adapters/test_sklearn.py

"""Sklearn 模型适配器测试

验证 Sklearn 二分类模型的能力检测、概率预测、Logit 预测、
批量推理、正类方向处理和特征重要性计算。

核心功能：
  - 验证逻辑回归模型能力
  - 验证概率和批量概率预测
  - 验证 Logit 和批量 Logit 预测
  - 验证正类方向处理
  - 验证特征重要性
  - 验证非逻辑回归模型不提供 Logit 能力
  - 验证二分类模型约束
"""

import numpy as np
import pytest

pytest.importorskip(
    "sklearn"
)

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import (
    LogisticRegression,
    LogisticRegressionCV,
)
from sklearn.svm import LinearSVC

from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.sklearn import SklearnAdapter


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
def logistic_adapter(
        logistic_model: LogisticRegression,
) -> SklearnAdapter:
    """提供逻辑回归模型适配器"""
    return SklearnAdapter(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


def test_logistic_regression_capabilities(
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试逻辑回归声明完整推理能力"""
    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        logistic_adapter.get_capabilities()
        == expected
    )


def test_logistic_regression_cv_supports_log_odds(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试交叉验证逻辑回归支持 Logit"""
    X, y = binary_training_data

    model = LogisticRegressionCV(
        Cs=3,
        cv=2,
        l1_ratios=(
            0.0,
        ),
        scoring="neg_log_loss",
        use_legacy_attributes=False,
        max_iter=1000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    adapter = SklearnAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    assert adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )


def test_predict_probability_matches_model(
        logistic_model: LogisticRegression,
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试概率预测与原始模型一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    expected = float(
        logistic_model.predict_proba(
            np.array([
                [-0.75, 0.25],
            ])
        )[0, 1]
    )

    result = logistic_adapter.predict(
        features
    )

    assert isinstance(
        result,
        float,
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_probability_batch_matches_model(
        logistic_model: LogisticRegression,
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试批量概率预测与原始模型一致"""
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

    array = np.array([
        [-0.75, 0.25],
        [1.20, 0.80],
    ])

    expected = (
        logistic_model.predict_proba(
            array
        )[:, 1]
    )

    result = logistic_adapter.predict(
        features
    )

    assert isinstance(
        result,
        list,
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_predict_logit_matches_model_decision_function(
        logistic_model: LogisticRegression,
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试 Logit 与原始模型决策函数一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    expected = float(
        logistic_model.decision_function(
            np.array([
                [-0.75, 0.25],
            ])
        )[0]
    )

    result = logistic_adapter.predict_logit(
        features
    )

    assert isinstance(
        result,
        float,
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_logit_batch_matches_model(
        logistic_model: LogisticRegression,
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试批量 Logit 与原始模型决策函数一致"""
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

    array = np.array([
        [-0.75, 0.25],
        [1.20, 0.80],
    ])

    expected = logistic_model.decision_function(
        array
    )

    result = logistic_adapter.predict_logit(
        features
    )

    assert isinstance(
        result,
        list,
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_positive_class_zero_reverses_logit_direction(
        logistic_model: LogisticRegression,
) -> None:
    """测试正类为类别零时反转 Logit 方向"""
    adapter = SklearnAdapter(
        model=logistic_model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    features = {
        "feature_a": -0.75,
        "feature_b": 0.25,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected_probability = float(
        logistic_model.predict_proba(
            array
        )[0, 0]
    )

    expected_logit = -float(
        logistic_model.decision_function(
            array
        )[0]
    )

    probability = adapter.predict(
        features
    )

    logit = adapter.predict_logit(
        features
    )

    if not isinstance(
            probability,
            float,
    ):
        raise AssertionError(
            "predict 应返回 float"
        )

    if isinstance(
            logit,
            list,
    ):
        raise AssertionError(
            "predict_logit 应返回 float"
        )

    else:
        scalar_logit = logit

    assert probability == pytest.approx(
        expected_probability
    )

    assert scalar_logit == pytest.approx(
        expected_logit
    )

    recovered_probability = (
        1.0
        / (
            1.0
            + np.exp(-scalar_logit)
        )
    )

    assert recovered_probability == pytest.approx(
        probability
    )


def test_logistic_feature_importance_uses_absolute_coefficients(
        logistic_model: LogisticRegression,
        logistic_adapter: SklearnAdapter,
) -> None:
    """测试逻辑回归特征重要性使用系数绝对值"""
    expected_values = np.abs(
        logistic_model.coef_[0]
    )

    result = (
        logistic_adapter.get_feature_importance()
    )

    assert list(
        result
    ) == FEATURE_NAMES

    assert list(
        result.values()
    ) == pytest.approx(
        expected_values.tolist()
    )


def test_feature_importance_uses_default_feature_names(
        logistic_model: LogisticRegression,
) -> None:
    """测试未配置特征名称时生成默认名称"""
    adapter = SklearnAdapter(
        model=logistic_model,
        positive_class=1,
    )

    result = adapter.get_feature_importance()

    assert list(
        result
    ) == [
        "f0",
        "f1",
    ]


def test_feature_importance_rejects_name_count_mismatch(
        logistic_model: LogisticRegression,
) -> None:
    """测试特征名称数量必须与重要性数量一致"""
    adapter = SklearnAdapter(
        model=logistic_model,
        feature_names=[
            "feature_a",
        ],
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征名称数量与特征重要性数量不一致",
    ):
        adapter.get_feature_importance()


def test_random_forest_does_not_support_log_odds(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试随机森林不声明 Logit 能力"""
    X, y = binary_training_data

    model = RandomForestClassifier(
        n_estimators=20,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    adapter = SklearnAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        adapter.get_capabilities()
        == expected
    )

    assert not adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        adapter.predict_logit(
            np.array([
                0.1,
                0.2,
            ])
        )


def test_random_forest_feature_importance_matches_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试树模型特征重要性与原始模型一致"""
    X, y = binary_training_data

    model = RandomForestClassifier(
        n_estimators=20,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    adapter = SklearnAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    result = adapter.get_feature_importance()

    assert list(
        result.values()
    ) == pytest.approx(
        model.feature_importances_.tolist()
    )


def test_linear_svc_only_exposes_feature_importance(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> None:
    """测试无概率接口的线性模型只提供特征重要性"""
    X, y = binary_training_data

    model = LinearSVC(
        max_iter=5000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    adapter = SklearnAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    assert (
        adapter.get_capabilities()
        == ModelCapability.FEATURE_IMPORTANCE
    )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_PROBA",
    ):
        adapter.predict(
            np.array([
                0.1,
                0.2,
            ])
        )

    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        adapter.predict_logit(
            np.array([
                0.1,
                0.2,
            ])
        )


def test_multiclass_model_is_rejected(
) -> None:
    """测试多分类模型初始化时被拒绝"""
    X = np.array([
        [-2.0, -1.0],
        [-1.5, -0.5],
        [-1.0, -1.5],
        [0.0, 0.5],
        [0.3, 1.0],
        [0.8, 0.2],
        [1.0, -0.5],
        [1.5, -1.0],
        [2.0, -1.5],
    ])

    y = np.array([
        0,
        0,
        0,
        1,
        1,
        1,
        2,
        2,
        2,
    ])

    model = LogisticRegression(
        max_iter=1000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    with pytest.raises(
            ValueError,
            match="仅支持二分类模型",
    ):
        SklearnAdapter(
            model=model,
            feature_names=FEATURE_NAMES,
            positive_class=1,
        )


def test_missing_positive_class_is_rejected(
        logistic_model: LogisticRegression,
) -> None:
    """测试模型类别中必须存在指定正类"""
    with pytest.raises(
            ValueError,
            match="模型类别中不存在指定正类",
    ):
        SklearnAdapter(
            model=logistic_model,
            feature_names=FEATURE_NAMES,
            positive_class="bad",
        )
