# tests/core/model/adapters/test_lightgbm.py

"""LightGBM 模型适配器测试

验证 LightGBM 二分类模型的能力检测、概率预测、批量预测、
正类选择、Gain 特征重要性和异常处理。

核心功能：
  - 验证 LightGBM 分类模型能力
  - 验证概率和批量概率预测
  - 验证正类概率选择
  - 验证不提供 Logit 能力
  - 验证 Gain 特征重要性
  - 验证特征名称解析优先级
  - 验证模型和预测输出校验
"""

from typing import Any

import numpy as np
import pytest

pytest.importorskip(
    "lightgbm"
)

from lightgbm import LGBMClassifier

from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.lightgbm import LightGBMAdapter


FEATURE_NAMES = [
    "feature_a",
    "feature_b",
]


class FakeBooster:
    """LightGBM Booster 测试替身"""

    def __init__(
            self,
            importance: list[float],
            feature_names: Any = None,
    ) -> None:
        self.importance = np.asarray(
            importance,
            dtype=float,
        )
        self.feature_names = feature_names

    def feature_importance(
            self,
            *,
            importance_type: str,
    ) -> np.ndarray:
        """返回固定特征重要性"""
        if importance_type != "gain":
            raise AssertionError(
                "importance_type 应为 gain"
            )

        return self.importance.copy()

    def feature_name(
            self,
    ) -> Any:
        """返回固定特征名称"""
        return self.feature_names


class FakeLightGBMModel:
    """LightGBM 分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
    ])

    def __init__(
            self,
            probabilities: Any,
            *,
            booster: FakeBooster | None = None,
            model_feature_names: Any = None,
    ) -> None:
        self.probabilities = probabilities
        self.booster_ = (
            booster
            if booster is not None
            else FakeBooster(
                [
                    0.0,
                    0.0,
                ]
            )
        )
        self._Booster = self.booster_

        if model_feature_names is not None:
            self.feature_names_in_ = model_feature_names

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


class MissingProbabilityModel:
    """未提供概率接口的测试模型"""

    classes_ = np.array([
        0,
        1,
    ])

    def __init__(
            self,
    ) -> None:
        self.booster_ = FakeBooster([
            0.0,
            0.0,
        ])
        self._Booster = self.booster_


class UntrainedModel:
    """未训练分类模型测试替身"""

    classes_ = None

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.4,
                0.6,
            ],
        ])
        self.booster_ = FakeBooster([
            0.0,
            0.0,
        ])
        self._Booster = self.booster_

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


class MissingBoosterModel:
    """缺少 Booster 的已分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
    ])

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.4,
                0.6,
            ],
        ])

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


class MulticlassModel:
    """多分类模型测试替身"""

    classes_ = np.array([
        0,
        1,
        2,
    ])

    def __init__(
            self,
    ) -> None:
        self.probabilities = np.array([
            [
                0.2,
                0.3,
                0.5,
            ],
        ])
        self.booster_ = FakeBooster([
            0.0,
            0.0,
        ])
        self._Booster = self.booster_

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> np.ndarray:
        """返回多分类概率"""
        sample_count = len(
            np.asarray(X)
        )

        return np.repeat(
            self.probabilities,
            sample_count,
            axis=0,
        )


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
def lightgbm_model(
        binary_training_data: tuple[
            np.ndarray,
            np.ndarray,
        ],
) -> LGBMClassifier:
    """提供已训练 LightGBM 二分类模型"""
    X, y = binary_training_data

    model = LGBMClassifier(
        n_estimators=12,
        max_depth=2,
        num_leaves=3,
        learning_rate=0.3,
        min_child_samples=1,
        objective="binary",
        random_state=0,
        n_jobs=1,
        verbosity=-1,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.fixture
def lightgbm_adapter(
        lightgbm_model: LGBMClassifier,
) -> LightGBMAdapter:
    """提供 LightGBM 模型适配器"""
    return LightGBMAdapter(
        model=lightgbm_model,
        feature_names=FEATURE_NAMES,
        positive_class=1,
    )


def test_lightgbm_capabilities(
        lightgbm_adapter: LightGBMAdapter,
) -> None:
    """测试 LightGBM 声明分类推理能力"""
    expected = (
        ModelCapability.PREDICT_PROBA
        | ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.BATCH_PREDICT
    )

    assert (
        lightgbm_adapter.get_capabilities()
        == expected
    )

    assert not lightgbm_adapter.has_capability(
        ModelCapability.PREDICT_LOG_ODDS
    )


@pytest.mark.filterwarnings(
    "ignore:X does not have valid feature names"
)
def test_predict_probability_matches_model(
        lightgbm_model: LGBMClassifier,
        lightgbm_adapter: LightGBMAdapter,
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
        lightgbm_model.predict_proba(
            array
        )[0, 1]
    )

    result = require_scalar(
        lightgbm_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected
    )


@pytest.mark.filterwarnings(
    "ignore:X does not have valid feature names"
)
def test_predict_probability_batch_matches_model(
        lightgbm_model: LGBMClassifier,
        lightgbm_adapter: LightGBMAdapter,
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
        lightgbm_model.predict_proba(
            array
        )[:, 1]
    )

    result = require_batch(
        lightgbm_adapter.predict(
            features
        )
    )

    assert result == pytest.approx(
        expected.tolist()
    )


@pytest.mark.filterwarnings(
    "ignore:X does not have valid feature names"
)
def test_positive_class_zero_selects_first_probability_column(
        lightgbm_model: LGBMClassifier,
) -> None:
    """测试正类为类别零时选择第一列概率"""
    adapter = LightGBMAdapter(
        model=lightgbm_model,
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
        lightgbm_model.predict_proba(
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
        lightgbm_adapter: LightGBMAdapter,
) -> None:
    """测试 LightGBM 不提供 Logit 预测"""
    with pytest.raises(
            NotImplementedError,
            match="PREDICT_LOG_ODDS",
    ):
        lightgbm_adapter.predict_logit(
            np.array([
                -0.75,
                0.25,
            ])
        )


def test_gain_feature_importance_matches_booster(
        lightgbm_model: LGBMClassifier,
        lightgbm_adapter: LightGBMAdapter,
) -> None:
    """测试 Gain 特征重要性与 Booster 一致"""
    expected_values = (
        lightgbm_model.booster_.feature_importance(
            importance_type="gain"
        )
    )

    result = (
        lightgbm_adapter.get_feature_importance()
    )

    assert list(
        result
    ) == FEATURE_NAMES

    assert list(
        result.values()
    ) == pytest.approx(
        expected_values.tolist()
    )


def test_configured_feature_names_have_highest_priority(
) -> None:
    """测试显式特征名称优先于模型元数据"""
    model = FakeLightGBMModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            [
                1.5,
                3.0,
            ],
            feature_names=[
                "booster_a",
                "booster_b",
            ],
        ),
        model_feature_names=[
            "model_a",
            "model_b",
        ],
    )

    adapter = LightGBMAdapter(
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


def test_booster_feature_names_are_used_when_not_configured(
) -> None:
    """测试优先使用 Booster 特征名称"""
    model = FakeLightGBMModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            [
                1.5,
                3.0,
            ],
            feature_names=[
                "booster_a",
                "booster_b",
            ],
        ),
        model_feature_names=[
            "model_a",
            "model_b",
        ],
    )

    adapter = LightGBMAdapter(
        model=model,
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "booster_a": 1.5,
        "booster_b": 3.0,
    }


def test_model_feature_names_are_used_as_fallback(
) -> None:
    """测试 Booster 名称不可用时使用模型特征名称"""
    model = FakeLightGBMModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            [
                1.5,
                3.0,
            ],
            feature_names="invalid",
        ),
        model_feature_names=np.array([
            "model_a",
            "model_b",
        ]),
    )

    adapter = LightGBMAdapter(
        model=model,
        positive_class=1,
    )

    assert adapter.get_feature_importance() == {
        "model_a": 1.5,
        "model_b": 3.0,
    }


def test_default_feature_names_are_generated(
) -> None:
    """测试缺少特征元数据时生成默认名称"""
    model = FakeLightGBMModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            [
                1.5,
                0.0,
            ],
            feature_names=None,
        ),
    )

    adapter = LightGBMAdapter(
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
    model = FakeLightGBMModel(
        probabilities=[
            [
                0.4,
                0.6,
            ],
        ],
        booster=FakeBooster(
            [
                1.5,
                3.0,
            ],
            feature_names=[
                "booster_a",
                "booster_b",
            ],
        ),
    )

    adapter = LightGBMAdapter(
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


def test_missing_probability_interface_is_rejected(
) -> None:
    """测试拒绝不提供概率接口的模型"""
    with pytest.raises(
            TypeError,
            match="仅支持提供 predict_proba 接口",
    ):
        LightGBMAdapter(
            model=MissingProbabilityModel(),
            feature_names=FEATURE_NAMES,
        )


def test_untrained_model_is_rejected(
) -> None:
    """测试拒绝未训练分类模型"""
    with pytest.raises(
            ValueError,
            match="模型尚未训练或不属于分类模型",
    ):
        LightGBMAdapter(
            model=UntrainedModel(),
            feature_names=FEATURE_NAMES,
        )


def test_missing_booster_is_rejected(
) -> None:
    """测试拒绝缺少 Booster 的模型"""
    with pytest.raises(
            ValueError,
            match="模型尚未训练，缺少 booster_",
    ):
        LightGBMAdapter(
            model=MissingBoosterModel(),
            feature_names=FEATURE_NAMES,
        )


def test_multiclass_model_is_rejected(
) -> None:
    """测试拒绝多分类模型"""
    with pytest.raises(
            ValueError,
            match="仅支持二分类模型",
    ):
        LightGBMAdapter(
            model=MulticlassModel(),
            feature_names=FEATURE_NAMES,
            positive_class=1,
        )


def test_missing_positive_class_is_rejected(
        lightgbm_model: LGBMClassifier,
) -> None:
    """测试模型类别中必须存在指定正类"""
    with pytest.raises(
            ValueError,
            match="模型类别中不存在指定正类",
    ):
        LightGBMAdapter(
            model=lightgbm_model,
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
    model = FakeLightGBMModel(
        probabilities=probabilities,
    )

    adapter = LightGBMAdapter(
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
    model = FakeLightGBMModel(
        probabilities=[
            [
                np.nan,
                0.6,
            ],
        ],
    )

    adapter = LightGBMAdapter(
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
