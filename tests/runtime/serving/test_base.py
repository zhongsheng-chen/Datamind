# tests/runtime/serving/test_base.py

"""运行时服务基类测试

验证统一结果、模型能力、访问状态以及特征元数据解析行为。

核心功能：
  - 验证运行时模型信息和统一结果
  - 验证模型能力查询和校验
  - 验证特征名称及数据类型解析
  - 验证模型特征名称推断
"""

from types import SimpleNamespace
from typing import Any

import pytest

import datamind.runtime.serving.base as base_module
from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


CAPABILITIES = (
    ModelCapability.PREDICT_PROBA
    | ModelCapability.BATCH_PREDICT
)


class AdapterStub:
    """模型适配器替身"""

    def get_capabilities(self) -> ModelCapability:
        """返回模型能力"""
        return CAPABILITIES

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """判断模型能力"""
        return bool(CAPABILITIES & capability)

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验模型能力"""
        if not self.has_capability(capability):
            raise NotImplementedError("模型能力不受支持")


class InferenceStub:
    """推理组件替身"""

    def __init__(self, **_kwargs: Any) -> None:
        self.adapter = AdapterStub()


class RuntimeServiceStub(BaseRuntimeService):
    """可实例化的运行时服务替身"""

    SERVICE_TYPE = "test"

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        return self.build_result(features)

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.build_result({
            "predictions": features_list,
        })


def create_runtime_model(
        *,
        model: Any = None,
        metadata: dict[str, Any] | None = None,
) -> RuntimeModel:
    """创建运行时模型"""
    return RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=model if model is not None else object(),
        metadata=metadata or {},
    )


@pytest.fixture(autouse=True)
def install_inference_stub(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安装隔离的推理组件替身"""
    monkeypatch.setitem(
        vars(base_module),
        "Inference",
        InferenceStub,
    )


def test_service_exposes_runtime_information() -> None:
    """测试服务公开运行时模型信息"""
    runtime_model = create_runtime_model()
    service = RuntimeServiceStub(
        runtime_model=runtime_model
    )

    result = service.build_result({
        "probability": 0.8,
    })

    assert service.deployment_id == "dep_test"
    assert service.model_id == "mdl_test"
    assert service.version_id == "ver_test"
    assert service.framework == "sklearn"
    assert service.metadata == {}
    assert result == {
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "service_type": "test",
        "probability": 0.8,
    }


def test_service_delegates_capability_operations() -> None:
    """测试服务将模型能力操作委托给适配器"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model()
    )

    assert service.get_capabilities() == CAPABILITIES
    assert service.get_capability_names() == [
        "PREDICT_PROBA",
        "BATCH_PREDICT",
    ]
    assert service.has_capability(
        ModelCapability.PREDICT_PROBA
    ) is True

    with pytest.raises(
            NotImplementedError,
            match="模型能力不受支持",
    ):
        service.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )


def test_service_touch_updates_runtime_access_state() -> None:
    """测试服务记录运行时模型访问状态"""
    runtime_model = create_runtime_model()
    service = RuntimeServiceStub(
        runtime_model=runtime_model
    )

    service.touch()

    assert runtime_model.access_count == 1
    assert runtime_model.last_used_at is not None


def test_service_reads_feature_metadata() -> None:
    """测试服务从元数据读取特征名称和类型"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(metadata={
            "feature_names": ["age", 100],
            "data_types": {
                "age": "numeric",
                "income": DataType.NUMERIC,
                "invalid": "unknown",
                100: "numeric",
            },
        })
    )

    assert service.feature_names == ["age", "100"]
    assert service.data_types == {
        "age": DataType.NUMERIC,
        "income": DataType.NUMERIC,
    }


@pytest.mark.parametrize(
    "metadata",
    [
        {"feature_names": "age"},
        {"feature_names": 100},
        {"feature_names": []},
    ],
)
def test_service_ignores_invalid_feature_metadata(
        metadata: dict[str, Any],
) -> None:
    """测试服务忽略非法或空特征名称元数据"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(metadata=metadata)
    )

    assert service.feature_names is None


@pytest.mark.parametrize(
    "metadata",
    [
        {"data_types": "invalid"},
        {"data_types": {"age": "unknown"}},
        {"data_types": {}},
    ],
)
def test_service_ignores_invalid_data_type_metadata(
        metadata: dict[str, Any],
) -> None:
    """测试服务忽略非法或空特征类型元数据"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(metadata=metadata)
    )

    assert service.data_types == {}


@pytest.mark.parametrize(
    "attribute_name",
    [
        "feature_names_in_",
        "feature_name_",
        "feature_names_",
    ],
)
def test_service_infers_feature_names_from_model_attribute(
        attribute_name: str,
) -> None:
    """测试服务从模型属性推断特征名称"""
    model = SimpleNamespace(**{
        attribute_name: ["age", "annual_income"],
    })
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(model=model)
    )

    assert service.feature_names == [
        "age",
        "annual_income",
    ]


def test_service_infers_feature_names_from_booster() -> None:
    """测试服务从 XGBoost Booster 推断特征名称"""
    class ModelStub:
        """提供 Booster 的模型替身"""

        @staticmethod
        def get_booster() -> SimpleNamespace:
            return SimpleNamespace(
                feature_names=["age", "annual_income"]
            )

    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(model=ModelStub())
    )

    assert service.feature_names == [
        "age",
        "annual_income",
    ]


@pytest.mark.parametrize(
    "model",
    [
        object(),
        SimpleNamespace(feature_names_in_="age"),
        SimpleNamespace(get_booster=lambda: SimpleNamespace(
            feature_names="age"
        )),
        SimpleNamespace(get_booster=lambda: SimpleNamespace(
            feature_names=None
        )),
    ],
)
def test_service_returns_none_when_feature_names_cannot_be_inferred(
        model: Any,
) -> None:
    """测试无法推断模型特征名称时返回空值"""
    service = RuntimeServiceStub(
        runtime_model=create_runtime_model(model=model)
    )

    assert service.feature_names is None


def test_service_rejects_missing_runtime_model() -> None:
    """测试服务拒绝空运行时模型"""
    runtime_model: Any = None

    with pytest.raises(
            ValueError,
            match="runtime_model 不能为空",
    ):
        RuntimeServiceStub(
            runtime_model=runtime_model,
        )
