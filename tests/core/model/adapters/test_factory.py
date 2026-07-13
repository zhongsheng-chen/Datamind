# tests/core/model/adapters/test_factory.py

"""模型适配器工厂测试

验证模型框架识别、适配器创建、适配器注册和异常处理。

核心功能：
  - 验证内置框架识别
  - 验证 Sklearn 适配器创建
  - 验证内置适配器映射
  - 验证自定义适配器注册
  - 验证重复注册和覆盖注册
  - 验证非法参数和未支持模型
"""

from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from datamind.constants import (
    DataType,
    Framework,
)
from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.base import BaseModelAdapter
from datamind.core.model.adapters.catboost import CatBoostAdapter
from datamind.core.model.adapters.factory import ModelAdapterFactory
from datamind.core.model.adapters.lightgbm import LightGBMAdapter
from datamind.core.model.adapters.sklearn import SklearnAdapter
from datamind.core.model.adapters.xgboost import XGBoostAdapter


class DummyAdapter(BaseModelAdapter):
    """测试模型适配器"""

    SUPPORTED_CAPABILITIES = ModelCapability.PREDICT_PROBA

    def predict_proba(
            self,
            X: np.ndarray,
    ) -> float:
        """返回固定概率"""
        return 0.5


class InvalidAdapter:
    """未继承基础适配器的测试类"""


class UnsupportedModel:
    """不属于已支持框架的测试模型"""


@pytest.fixture(autouse=True)
def restore_sklearn_adapter(
) -> Iterator[None]:
    """测试结束后恢复 Sklearn 适配器注册"""
    original_adapter = (
        ModelAdapterFactory.get_adapter_class(
            Framework.SKLEARN
        )
    )

    try:
        yield

    finally:
        ModelAdapterFactory.register_adapter(
            Framework.SKLEARN,
            original_adapter,
            override=True,
        )


@pytest.fixture
def logistic_model(
) -> LogisticRegression:
    """提供已训练逻辑回归模型"""
    X = np.array([
        [-2.0, -1.0],
        [-1.0, -0.5],
        [0.5, 0.3],
        [1.5, 1.0],
    ])

    y = np.array([
        1,
        1,
        0,
        0,
    ])

    model = LogisticRegression(
        max_iter=1000,
        random_state=0,
    )

    model.fit(
        X,
        y,
    )

    return model


@pytest.mark.parametrize(
    (
        "module_name",
        "expected_framework",
    ),
    [
        (
            "sklearn.linear_model._logistic",
            Framework.SKLEARN,
        ),
        (
            "xgboost.sklearn",
            Framework.XGBOOST,
        ),
        (
            "lightgbm.sklearn",
            Framework.LIGHTGBM,
        ),
        (
            "catboost.core",
            Framework.CATBOOST,
        ),
    ],
)
def test_get_framework_recognizes_supported_frameworks(
        module_name: str,
        expected_framework: Framework,
) -> None:
    """测试识别已支持的模型框架"""
    model_class = type(
        "FrameworkModel",
        (),
        {
            "__module__": module_name,
        },
    )

    model = model_class()

    assert (
        ModelAdapterFactory.get_framework(
            model
        )
        == expected_framework
    )


def test_get_framework_accepts_sklearn_root_module(
) -> None:
    """测试识别 sklearn 根模块"""
    model_class = type(
        "SklearnRootModel",
        (),
        {
            "__module__": "sklearn",
        },
    )

    assert (
        ModelAdapterFactory.get_framework(
            model_class()
        )
        == Framework.SKLEARN
    )


def test_get_framework_rejects_none(
) -> None:
    """测试模型不能为空"""
    with pytest.raises(
            ValueError,
            match="model 不能为空",
    ):
        ModelAdapterFactory.get_framework(
            None
        )


def test_get_framework_rejects_unsupported_model(
) -> None:
    """测试拒绝未支持的模型类型"""
    with pytest.raises(
            ValueError,
            match="不支持的模型类型: UnsupportedModel",
    ):
        ModelAdapterFactory.get_framework(
            UnsupportedModel()
        )


@pytest.mark.parametrize(
    (
        "framework",
        "expected_adapter",
    ),
    [
        (
            Framework.SKLEARN,
            SklearnAdapter,
        ),
        (
            Framework.XGBOOST,
            XGBoostAdapter,
        ),
        (
            Framework.LIGHTGBM,
            LightGBMAdapter,
        ),
        (
            Framework.CATBOOST,
            CatBoostAdapter,
        ),
    ],
)
def test_get_adapter_class_returns_builtin_adapter(
        framework: Framework,
        expected_adapter: type[BaseModelAdapter],
) -> None:
    """测试获取内置模型适配器类"""
    assert (
        ModelAdapterFactory.get_adapter_class(
            framework
        )
        is expected_adapter
    )


def test_create_returns_sklearn_adapter(
        logistic_model: LogisticRegression,
) -> None:
    """测试创建 Sklearn 模型适配器"""
    feature_names = [
        "feature_a",
        "feature_b",
    ]

    data_types = {
        "feature_a": DataType.NUMERIC,
        "feature_b": DataType.NUMERIC,
    }

    adapter = ModelAdapterFactory.create(
        model=logistic_model,
        feature_names=feature_names,
        data_types=data_types,
        positive_class=0,
    )

    assert isinstance(
        adapter,
        SklearnAdapter,
    )

    assert adapter.model is logistic_model
    assert adapter.feature_names == feature_names
    assert adapter.data_types == data_types
    assert adapter.positive_class == 0


def test_register_adapter_rejects_duplicate_without_override(
) -> None:
    """测试禁止未授权的重复注册"""
    with pytest.raises(
            ValueError,
            match="模型适配器已注册: sklearn",
    ):
        ModelAdapterFactory.register_adapter(
            Framework.SKLEARN,
            DummyAdapter,
        )


def test_register_adapter_allows_override(
) -> None:
    """测试允许覆盖已注册适配器"""
    ModelAdapterFactory.register_adapter(
        Framework.SKLEARN,
        DummyAdapter,
        override=True,
    )

    assert (
        ModelAdapterFactory.get_adapter_class(
            Framework.SKLEARN
        )
        is DummyAdapter
    )


def test_create_uses_overridden_adapter(
        logistic_model: LogisticRegression,
) -> None:
    """测试创建模型时使用覆盖后的适配器"""
    ModelAdapterFactory.register_adapter(
        Framework.SKLEARN,
        DummyAdapter,
        override=True,
    )

    adapter = ModelAdapterFactory.create(
        model=logistic_model,
        feature_names=[
            "feature_a",
            "feature_b",
        ],
        positive_class=0,
    )

    assert isinstance(
        adapter,
        DummyAdapter,
    )

    assert adapter.model is logistic_model
    assert adapter.positive_class == 0


@pytest.mark.parametrize(
    "framework",
    [
        "sklearn",
        None,
        1,
    ],
)
def test_register_adapter_rejects_invalid_framework(
        framework: Any,
) -> None:
    """测试框架参数必须是 Framework 枚举"""
    with pytest.raises(
            TypeError,
            match="framework 必须是 Framework 枚举",
    ):
        ModelAdapterFactory.register_adapter(
            framework,
            DummyAdapter,
        )


@pytest.mark.parametrize(
    "adapter_class",
    [
        InvalidAdapter,
        object,
        1,
        None,
    ],
)
def test_register_adapter_rejects_invalid_adapter_class(
        adapter_class: Any,
) -> None:
    """测试适配器类必须继承基础适配器"""
    with pytest.raises(
            TypeError,
            match="adapter_class 必须继承 BaseModelAdapter",
    ):
        ModelAdapterFactory.register_adapter(
            Framework.SKLEARN,
            adapter_class,
            override=True,
        )
