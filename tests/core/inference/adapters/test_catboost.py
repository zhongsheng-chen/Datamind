"""CatBoost 模型适配器测试

验证 CatBoost 二分类模型的能力检测、概率预测、批量预测、
正类选择、特征重要性和异常处理。

核心功能：
  - test_catboost_capabilities:
    验证 CatBoost 声明分类推理能力
  - test_predict_probability_matches_model:
    验证概率预测与原始模型一致
  - test_predict_probability_batch_matches_model:
    验证批量概率预测与原始模型一致
  - test_positive_class_zero_selects_first_probability_column:
    验证正类为类别零时选择第一列概率
  - test_predict_logit_is_not_supported:
    验证 CatBoost 不提供对数几率预测
  - test_feature_importance_matches_model:
    验证特征重要性与原始模型一致
  - test_prediction_values_change_type_is_requested:
    验证使用 PredictionValuesChange 特征重要性
  - test_configured_feature_names_have_highest_priority:
    验证显式特征名称优先于模型元数据
  - test_model_feature_names_are_used_when_not_configured:
    验证未配置时使用模型特征名称
  - test_default_feature_names_are_generated:
    验证缺少有效模型特征名称时生成默认名称
  - test_feature_name_count_must_match_importance_count:
    验证特征名称数量必须与重要性数量一致
  - test_probability_only_model_does_not_support_importance:
    验证无重要性接口的模型不声明特征重要性
  - test_missing_probability_interface_is_rejected:
    验证拒绝不提供概率接口的模型
  - test_untrained_model_is_rejected:
    验证拒绝未训练模型
  - test_missing_classes_is_rejected:
    验证拒绝缺少类别信息的模型
  - test_multiclass_model_is_rejected:
    验证拒绝多分类模型
  - test_missing_positive_class_is_rejected:
    验证模型类别中必须存在指定正类
  - test_invalid_probability_output_is_rejected:
    验证拒绝非法概率预测结果
  - test_invalid_probability_for_positive_class_zero_is_rejected:
    验证正类为类别零时校验第一列概率
  - test_invalid_feature_importance_is_rejected:
    验证拒绝非有限特征重要性"""

from typing import Any

import numpy as np
import pytest

pytest.importorskip(
    "catboost"
)

from catboost import CatBoostClassifier

from datamind.core.capability import ModelCapability
from datamind.core.inference.adapters.catboost import CatBoostAdapter


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


class FakeCatBoostModel:
    """CatBoost 分类模型测试替身"""

    def __init__(
            self,
            probabilities: Any,
            *,
            importance: list[float] | None = None,
            feature_names: Any = None,
            classes: Any = None,
            fitted: bool = True,
    ) -> None:
        self.probabilities = probabilities
        self.importance = np.asarray(
            importance
            if importance is not None
            else [
                0.0,
                0.0,
            ],
            dtype=float,
        )
        self.feature_names_ = feature_names
        self.classes_ = (
            np.array([
                0,
                1,
            ])
            if classes is None
            else classes
        )
        self.fitted = fitted
        self.requested_importance_type: str | None = None

    def is_fitted(
            self,
    ) -> bool:
        """返回固定训练状态"""
        return self.fitted

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> Any:
        """返回固定概率结果"""
        values = np.asarray(
            self.probabilities
        )

        sample_count = len(
            np.asarray(X)
        )

        if (
                values.ndim == 2
                and values.shape[0] == 1
                and sample_count > 1
        ):
            return np.repeat(
                values,
                sample_count,
                axis=0,
            )

        return values

    def get_feature_importance(
            self,
            **kwargs: Any,
    ) -> np.ndarray:
        """返回固定特征重要性"""
        importance_type = kwargs.get(
            "type"
        )

        if not isinstance(
                importance_type,
                str,
        ):
            raise AssertionError(
                "type 应为 str"
            )

        self.requested_importance_type = (
            importance_type
        )

        return self.importance.copy()


class ProbabilityOnlyModel:
    """不提供特征重要性接口的分类模型测试替身"""

    def __init__(
            self,
    ) -> None:
        self.classes_ = np.array([
            0,
            1,
        ])
        self.probabilities = np.array([
            [
                0.4,
                0.6,
            ],
        ])

    def is_fitted(
            self,
    ) -> bool:
        """返回已训练状态"""
        return bool(
            self.classes_.size
        )

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """返回固定概率"""
        sample_count = len(
            np.asarray(X)
        )

        return np.repeat(
            self.probabilities,
            sample_count,
            axis=0,
        )


class MissingProbabilityModel:
    """未提供概率接口的测试模型"""

    def __init__(
            self,
    ) -> None:
        self.classes_ = np.array([
            0,
            1,
        ])
        self.fitted = True

    def is_fitted(
            self,
    ) -> bool:
        """返回固定训练状态"""
        return self.fitted


def require_scalar(
        value: float | list[float],
) -> float:
    """校验预测结果为标量"""
    if isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "预测结果应为 float"
        )

    return value


def require_batch(
        value: float | list[float],
) -> list[float]:
    """校验预测结果为列表"""
    if not isinstance(
            value,
            list,
    ):
        raise AssertionError(
            "预测结果应为 list[float]"
        )

    return value


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
def catboost_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> CatBoostClassifier:
    """提供已训练 CatBoost 二分类模型"""
    X, y = binary_training_data

    model = CatBoostClassifier(
        iterations=20,
        depth=2,
        learning_rate=0.2,
        loss_function="Logloss",
        random_seed=0,
        verbose=False,
        allow_writing_files=False,
        thread_count=1,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.fixture
def catboost_adapter(
        catboost_model: CatBoostClassifier,
) -> CatBoostAdapter:
    """提供 CatBoost 模型适配器"""
    return CatBoostAdapter(
        model=catboost_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


def test_catboost_capabilities(
        catboost_adapter: CatBoostAdapter,
) -> None:
    """测试 CatBoost 声明分类推理能力"""
    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        catboost_adapter.get_capabilities()
        == expected
    )

    assert not catboost_adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )


def test_predict_probability_matches_model(
        catboost_model: CatBoostClassifier,
        catboost_adapter: CatBoostAdapter,
) -> None:
    """测试概率预测与原始模型一致"""
    features = {
        "feature_b": 0.25,
        "feature_a": -0.75,
    }

    array = np.array([
        [-0.75, 0.25],
    ])

    expected = float(
        catboost_model.predict_proba(
            array
        )[0, 1]
    )

    result = require_scalar(
        catboost_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_probability_batch_matches_model(
        catboost_model: CatBoostClassifier,
        catboost_adapter: CatBoostAdapter,
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
        catboost_model.predict_proba(
            array
        )[:, 1]
    )

    result = require_batch(
        catboost_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected.tolist()
    )


def test_positive_class_zero_selects_first_probability_column(
        catboost_model: CatBoostClassifier,
) -> None:
    """测试正类为类别零时选择第一列概率"""
    adapter = CatBoostAdapter(
        model=catboost_model,
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

    expected = float(
        catboost_model.predict_proba(
            array
        )[0, 0]
    )

    result = require_scalar(
        adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


def test_predict_logit_is_not_supported(
        catboost_adapter: CatBoostAdapter,
) -> None:
    """测试 CatBoost 不提供对数几率预测"""
    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        catboost_adapter.predict_logit(
            np.array([
                -0.75,
                0.25,
            ])
        )


def test_feature_importance_matches_model(
        catboost_model: CatBoostClassifier,
        catboost_adapter: CatBoostAdapter,
) -> None:
    """测试特征重要性与原始模型一致"""
    expected_values = np.asarray(
        catboost_model.get_feature_importance(
            type="PredictionValuesChange",
        ),
        dtype=float,
    )

    result = (
        catboost_adapter.get_feature_importance()
    )

    assert list(
        result
    ) == FEATURE_NAMES

    assert list(
        result.values()
    ) == pytest.approx(
        expected_values.tolist()
    )


def test_prediction_values_change_type_is_requested(
) -> None:
    """测试使用 PredictionValuesChange 特征重要性"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            3.0,
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    adapter.get_feature_importance()

    assert (
        model.requested_importance_type
        == "PredictionValuesChange"
    )


def test_configured_feature_names_have_highest_priority(
) -> None:
    """测试显式特征名称优先于模型元数据"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            3.0,
        ],
        feature_names=[
            "model_a",
            "model_b",
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=[
            "configured_a",
            "configured_b",
        ],
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "configured_a": 1.5,
        "configured_b": 3.0,
    }


def test_model_feature_names_are_used_when_not_configured(
) -> None:
    """测试未配置时使用模型特征名称"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            3.0,
        ],
        feature_names=[
            "model_a",
            "model_b",
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "model_a": 1.5,
        "model_b": 3.0,
    }


@pytest.mark.parametrize(
    "feature_names",
    [
        None,
        "invalid",
        1,
        [],
    ],
)
def test_default_feature_names_are_generated(
        feature_names: Any,
) -> None:
    """测试缺少有效模型特征名称时生成默认名称"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            0.0,
        ],
        feature_names=feature_names,
    )

    adapter = CatBoostAdapter(
        model=model,
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "f0": 1.5,
        "f1": 0.0,
    }


def test_feature_name_count_must_match_importance_count(
) -> None:
    """测试特征名称数量必须与重要性数量一致"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            3.0,
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=[
            "configured_a",
        ],
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征名称数量与特征重要性数量不一致",
    ):
        adapter.get_feature_importance()


def test_probability_only_model_does_not_support_importance(
) -> None:
    """测试无重要性接口的模型不声明特征重要性"""
    adapter = CatBoostAdapter(
        model=ProbabilityOnlyModel(),
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        adapter.get_capabilities()
        == expected
    )

    with pytest.raises(
            NotImplementedError,
            match="FEATURE_IMPORTANCE",
    ):
        adapter.get_feature_importance()


def test_missing_probability_interface_is_rejected(
) -> None:
    """测试拒绝不提供概率接口的模型"""
    with pytest.raises(
            TypeError,
            match="仅支持提供 predict_proba 接口",
    ):
        CatBoostAdapter(
            model=MissingProbabilityModel(),
            feature_names=FEATURE_NAMES,
        )


def test_untrained_model_is_rejected(
) -> None:
    """测试拒绝未训练模型"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        fitted=False,
    )

    with pytest.raises(
            ValueError,
            match="模型尚未训练",
    ):
        CatBoostAdapter(
            model=model,
            feature_names=FEATURE_NAMES,
        )


def test_missing_classes_is_rejected(
) -> None:
    """测试拒绝缺少类别信息的模型"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        classes=None,
    )
    model.classes_ = None

    with pytest.raises(
            ValueError,
            match="模型尚未训练或不属于分类模型",
    ):
        CatBoostAdapter(
            model=model,
            feature_names=FEATURE_NAMES,
        )


def test_multiclass_model_is_rejected(
) -> None:
    """测试拒绝多分类模型"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.2,
                0.3,
                0.5,
            ],
        ],
        classes=np.array([
            0,
            1,
            2,
        ]),
    )

    with pytest.raises(
            ValueError,
            match="仅支持二分类模型",
    ):
        CatBoostAdapter(
            model=model,
            feature_names=FEATURE_NAMES,
            positive_class=1,
        )


def test_missing_positive_class_is_rejected(
        catboost_model: CatBoostClassifier,
) -> None:
    """测试模型类别中必须存在指定正类"""
    with pytest.raises(
            ValueError,
            match="模型类别中不存在指定正类",
    ):
        CatBoostAdapter(
            model=catboost_model,
            feature_names=FEATURE_NAMES,
            positive_class="bad",
        )


@pytest.mark.parametrize(
    (
        "probabilities",
        "error_type",
        "message",
    ),
    [
        (
            [
                0.4,
                0.6,
            ],
            NotImplementedError,
            "仅支持二维概率预测结果",
        ),
        (
            [
                [
                    0.2,
                    0.3,
                    0.5,
                ],
            ],
            NotImplementedError,
            "仅支持二分类概率预测",
        ),
        (
            [
                [
                    -0.1,
                    1.1,
                ],
            ],
            ValueError,
            "模型返回了非法概率值",
        ),
        (
            [
                [
                    0.4,
                    np.nan,
                ],
            ],
            ValueError,
            "模型返回了非法概率值",
        ),
    ],
)
def test_invalid_probability_output_is_rejected(
        probabilities: Any,
        error_type: type[Exception],
        message: str,
) -> None:
    """测试拒绝非法概率预测结果"""
    model = FakeCatBoostModel(
        probabilities=probabilities,
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            error_type,
            match=message,
    ):
        adapter.predict(
            np.array([
                0.1,
                0.2,
            ])
        )


def test_invalid_probability_for_positive_class_zero_is_rejected(
) -> None:
    """测试正类为类别零时校验第一列概率"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                np.nan,
                0.6,
            ],
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=0,
    )

    with pytest.raises(
            ValueError,
            match="模型返回了非法概率值",
    ):
        adapter.predict(
            np.array([
                0.1,
                0.2,
            ])
        )


def test_invalid_feature_importance_is_rejected(
) -> None:
    """测试拒绝非有限特征重要性"""
    model = FakeCatBoostModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        importance=[
            1.5,
            np.nan,
        ],
    )

    adapter = CatBoostAdapter(
        model=model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )

    with pytest.raises(
            ValueError,
            match="特征重要性包含非有限数值",
    ):
        adapter.get_feature_importance()
