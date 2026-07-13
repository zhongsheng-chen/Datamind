# tests/runtime/test_registry.py

"""运行时模型注册表测试

验证模型注册、查询、访问统计、卸载和失败重载恢复能力。

核心功能：
  - 验证运行时模型注册和参数校验
  - 验证模型查询及访问统计
  - 验证注册表集合操作
  - 验证失败重载后恢复原模型
"""

from datetime import datetime, timezone

import pytest

from datamind.runtime.registry import RuntimeModel, RuntimeRegistry


def test_runtime_model_touch_and_to_dict() -> None:
    """测试运行时模型记录访问并转换为字典"""
    loaded_at = datetime.now(timezone.utc)
    runtime_model = RuntimeModel(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
        metadata={"task_type": "scoring"},
        loaded_at=loaded_at,
    )

    runtime_model.touch()
    result = runtime_model.to_dict()

    assert runtime_model.access_count == 1
    assert runtime_model.last_used_at is not None
    assert result == {
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "metadata": {"task_type": "scoring"},
        "loaded_at": loaded_at.isoformat(),
        "last_used_at": runtime_model.last_used_at.isoformat(),
        "access_count": 1,
    }


def test_register_copies_metadata() -> None:
    """测试注册模型时复制元数据"""
    registry = RuntimeRegistry()
    metadata = {
        "task_type": "scoring",
    }

    runtime_model = registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=object(),
        metadata=metadata,
    )
    metadata["task_type"] = "classification"

    assert runtime_model.metadata == {
        "task_type": "scoring",
    }
    assert registry.count() == 1


@pytest.mark.parametrize(
    "field",
    [
        "deployment_id",
        "model_id",
        "version_id",
        "framework",
    ],
)
def test_register_rejects_missing_required_field(
        field: str,
) -> None:
    """测试注册模型拒绝空必填字段"""
    values = {
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        field: "",
    }

    with pytest.raises(
            ValueError,
            match=f"{field} 不能为空",
    ):
        RuntimeRegistry().register(
            **values,
            model=object(),
        )


def test_register_rejects_missing_model() -> None:
    """测试注册模型拒绝空模型对象"""
    with pytest.raises(
            ValueError,
            match="model 不能为空",
    ):
        RuntimeRegistry().register(
            deployment_id="dep_test",
            model_id="mdl_test",
            version_id="ver_test",
            framework="sklearn",
            model=None,
        )


def test_get_and_get_model_update_access_state() -> None:
    """测试查询运行时模型默认更新访问状态"""
    registry = RuntimeRegistry()
    model = object()
    runtime_model = registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        model=model,
    )

    assert registry.get("dep_test") is runtime_model
    assert registry.get_model("dep_test") is model
    assert runtime_model.access_count == 2
    assert registry.get("dep_test", touch=False) is runtime_model
    assert runtime_model.access_count == 2


def test_missing_or_empty_deployment_returns_empty_result() -> None:
    """测试空标识和未知部署返回空结果"""
    registry = RuntimeRegistry()

    assert registry.get("") is None
    assert registry.get("dep_missing") is None
    assert registry.get_model("dep_missing") is None
    assert registry.exists("") is False
    assert registry.exists("dep_missing") is False
    assert registry.unregister("") is None
    assert registry.unregister("dep_missing") is None


def test_registry_collection_operations() -> None:
    """测试注册表查询、卸载和清空操作"""
    registry = RuntimeRegistry()
    first = registry.register(
        deployment_id="dep_1",
        model_id="mdl_1",
        version_id="ver_1",
        framework="sklearn",
        model=object(),
    )
    second = registry.register(
        deployment_id="dep_2",
        model_id="mdl_2",
        version_id="ver_2",
        framework="xgboost",
        model=object(),
    )

    assert registry.exists("dep_1") is True
    assert registry.all() == [first, second]
    assert [
        item["deployment_id"]
        for item in registry.to_dicts()
    ] == ["dep_1", "dep_2"]
    assert registry.unregister("dep_1") is first
    assert registry.count() == 1

    registry.clear()

    assert registry.all() == []
    assert registry.count() == 0


def test_restore_preserves_previous_runtime_model() -> None:
    """测试恢复原运行时模型对象"""
    registry = RuntimeRegistry()
    previous = registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_old",
        framework="sklearn",
        model=object(),
    )
    registry.register(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_new",
        framework="sklearn",
        model=object(),
    )

    registry.restore(previous)

    assert registry.get("dep_test", touch=False) is previous
