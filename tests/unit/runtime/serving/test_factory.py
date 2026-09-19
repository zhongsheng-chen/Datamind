"""运行时服务工厂测试

验证任务类型解析、分类阈值解析和具体服务创建行为。

核心功能：
  - test_create_classification_service_from_explicit_task_type:
    验证根据显式任务类型创建分类服务
  - test_create_classification_service_resolves_metadata_threshold:
    验证分类服务解析元数据阈值
  - test_create_scoring_service:
    验证创建评分服务
  - test_create_scoring_service_uses_deployment_threshold:
    验证评分服务使用部署阈值
  - test_create_rejects_invalid_task_type:
    验证拒绝无效任务类型
  - test_create_rejects_missing_runtime_model:
    验证拒绝缺失运行时模型
  - test_create_rejects_invalid_threshold:
    验证拒绝无效阈值
  - test_explicit_threshold_takes_precedence_over_metadata:
    验证显式阈值优先于元数据阈值
"""

from typing import Any
from unittest.mock import MagicMock

import pytest

import datamind.runtime.serving.factory as factory_module
from datamind.constants import DataType
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.factory import RuntimeServiceFactory


def create_runtime_model(
        metadata: dict[str, Any] | None = None,
) -> RuntimeModel:
    """创建运行时模型"""
    return RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
        metadata=metadata or {},
    )


def install_service_factories(
        monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock]:
    """安装具体运行时服务工厂替身"""
    classification_factory = MagicMock(
        return_value=MagicMock()
    )
    scoring_factory = MagicMock(
        return_value=MagicMock()
    )
    monkeypatch.setitem(
        vars(factory_module),
        "_classification_service_type",
        lambda: classification_factory,
    )
    monkeypatch.setitem(
        vars(factory_module),
        "_scoring_service_type",
        lambda: scoring_factory,
    )

    return classification_factory, scoring_factory


def test_create_classification_service_from_explicit_task_type(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试显式任务类型创建分类服务"""
    classification_factory, _ = install_service_factories(
        monkeypatch
    )
    runtime_model = create_runtime_model()
    feature_names = ["age"]
    data_types = {
        "age": DataType.NUMERIC,
    }

    result = RuntimeServiceFactory.create(
        runtime_model=runtime_model,
        task_type=" Classification ",
        feature_names=feature_names,
        data_types=data_types,
        threshold=0.65,
    )

    assert result is classification_factory.return_value
    classification_factory.assert_called_once_with(
        runtime_model=runtime_model,
        feature_names=feature_names,
        data_types=data_types,
        threshold=0.65,
    )


@pytest.mark.parametrize(
    ("metadata", "expected_threshold"),
    [
        (
            {
                "task_type": "classification",
                "threshold": 0.6,
            },
            0.6,
        ),
        ({"task_type": "classification"}, 0.5),
    ],
)
def test_create_classification_service_resolves_metadata_threshold(
        monkeypatch: pytest.MonkeyPatch,
        metadata: dict[str, Any],
        expected_threshold: float,
) -> None:
    """测试分类服务从元数据解析阈值"""
    classification_factory, _ = install_service_factories(
        monkeypatch
    )
    runtime_model = create_runtime_model(metadata)

    RuntimeServiceFactory.create(
        runtime_model=runtime_model
    )

    assert classification_factory.call_args.kwargs[
        "threshold"
    ] == expected_threshold


def test_create_scoring_service(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建评分服务并传递评分决策阈值"""
    _, scoring_factory = install_service_factories(
        monkeypatch
    )
    runtime_model = create_runtime_model({
        "task_type": "classification",
    })
    result = RuntimeServiceFactory.create(
        runtime_model=runtime_model,
        task_type="scoring",
    )

    assert result is scoring_factory.return_value
    scoring_factory.assert_called_once_with(
        runtime_model=runtime_model,
        feature_names=None,
        data_types=None,
        threshold=600.0,
    )


def test_create_scoring_service_uses_deployment_threshold(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分服务读取部署配置中的阈值"""
    _, scoring_factory = install_service_factories(monkeypatch)
    runtime_model = create_runtime_model({
        "task_type": "scoring",
        "threshold": 650.0,
    })

    RuntimeServiceFactory.create(runtime_model=runtime_model)

    assert scoring_factory.call_args.kwargs["threshold"] == 650.0


@pytest.mark.parametrize(
    ("task_type", "metadata", "message"),
    [
        (None, {}, "task_type 不能为空"),
        (" ", {}, "task_type 不能为空"),
        ("regression", {}, "不支持的任务类型"),
    ],
)
def test_create_rejects_invalid_task_type(
        monkeypatch: pytest.MonkeyPatch,
        task_type: str | None,
        metadata: dict[str, Any],
        message: str,
) -> None:
    """测试服务工厂拒绝缺失或不受支持的任务类型"""
    install_service_factories(monkeypatch)

    with pytest.raises(
            ValueError,
            match=message,
    ):
        RuntimeServiceFactory.create(
            runtime_model=create_runtime_model(metadata),
            task_type=task_type,
        )


def test_create_rejects_missing_runtime_model() -> None:
    """测试服务工厂拒绝空运行时模型"""
    runtime_model: Any = None

    with pytest.raises(
            ValueError,
            match="runtime_model 不能为空",
    ):
        RuntimeServiceFactory.create(
            runtime_model=runtime_model,
            task_type="classification",
        )


@pytest.mark.parametrize(
    ("threshold", "message"),
    [
        (True, "不能是布尔值"),
        ([0.5], "valid number"),
        ("invalid", "unable to parse string"),
        (-0.1, "必须在 0 到 1 之间"),
        (1.1, "必须在 0 到 1 之间"),
    ],
)
def test_create_rejects_invalid_threshold(
        monkeypatch: pytest.MonkeyPatch,
        threshold: Any,
        message: str,
) -> None:
    """测试分类服务工厂拒绝非法阈值"""
    install_service_factories(monkeypatch)

    with pytest.raises(
            ValueError,
            match=message,
    ):
        RuntimeServiceFactory.create(
            runtime_model=create_runtime_model(),
            task_type="classification",
            threshold=threshold,
        )


def test_explicit_threshold_takes_precedence_over_metadata(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试显式阈值优先于部署配置"""
    classification_factory, _ = install_service_factories(
        monkeypatch
    )

    RuntimeServiceFactory.create(
        runtime_model=create_runtime_model({
            "task_type": "classification",
            "threshold": 0.6,
        }),
        threshold=0.7,
    )

    assert classification_factory.call_args.kwargs[
        "threshold"
    ] == 0.7
