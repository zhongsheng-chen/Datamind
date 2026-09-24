"""管理控制台资源动作分派测试.

验证资源动作到生命周期服务的映射及参数传递。

核心功能：
  - test_dispatch_restore_actions:
    验证恢复动作分派到对应服务
  - test_dispatch_version_purge_keeps_reason:
    验证版本清除动作保留操作原因
  - test_dispatch_model_deletion_actions_use_model_id:
    验证模型删除动作使用模型 ID
  - test_dispatch_model_lifecycle_actions_use_model_id:
    验证模型生命周期动作使用模型 ID
  - test_dispatch_variant_toggle_maps_active_flag:
    验证实验分组开关映射启用状态
  - test_dispatch_batch_actions:
    验证批次取消和重试动作分派到批次生命周期服务
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.console.actions import dispatch_resource_action


def _unused_factory(*_args: object, **_kwargs: object) -> MagicMock:
    """返回未配置服务替身."""
    return MagicMock()


def _arguments(**overrides: object) -> dict[str, object]:
    """构造资源动作的公共参数."""
    arguments: dict[str, object] = {
        "resource": "deployments",
        "identifier": "dep_test",
        "action": "restore",
        "reason": None,
        "user_id": "usr_test",
        "username": "operator",
        "model_lifecycle_factory": _unused_factory,
        "model_deletion_factory": _unused_factory,
        "deployment_factory": _unused_factory,
        "routing_factory": _unused_factory,
        "experiment_factory": _unused_factory,
        "identity_factory": _unused_factory,
        "batch_factory": _unused_factory,
    }
    arguments.update(overrides)
    return arguments


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resource", "identifier", "method", "identifier_name"),
    [
        ("deployments", "dep_test", "restore_deployment", "deployment_id"),
        ("routings", "rtn_test", "restore_routing", "routing_id"),
        ("experiments", "exp_test", "restore_experiment", "experiment_id"),
        ("variants", "var_test", "restore_variant", "variant_id"),
    ],
)
async def test_dispatch_restore_actions(
        resource: str,
        identifier: str,
        method: str,
        identifier_name: str,
) -> None:
    """测试可回收资源统一调用各自的恢复方法."""
    service = MagicMock()
    setattr(
        service,
        method,
        AsyncMock(return_value={identifier_name: identifier}),
    )
    factory_name = {
        "deployments": "deployment_factory",
        "routings": "routing_factory",
        "experiments": "experiment_factory",
        "variants": "experiment_factory",
    }[resource]

    result = await dispatch_resource_action(
        **_arguments(
            resource=resource,
            identifier=identifier,
            **{factory_name: lambda: service},
        )
    )

    assert result[identifier_name] == identifier
    getattr(service, method).assert_awaited_once_with(
        **{
            identifier_name: identifier,
            "restored_by": "operator",
        }
    )


@pytest.mark.asyncio
async def test_dispatch_version_purge_keeps_reason() -> None:
    """测试版本永久清理交由删除服务并保留原因."""
    service = MagicMock()
    service.purge = AsyncMock(
        return_value={"version_id": "ver_test"}
    )

    await dispatch_resource_action(
        **_arguments(
            resource="versions",
            identifier="ver_test",
            action="purge",
            reason="超过保留期",
            model_deletion_factory=lambda: service,
        )
    )

    service.purge.assert_awaited_once_with(
        version_id="ver_test",
        reason="超过保留期",
        operator="operator",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "expected_arguments"),
    [
        (
            "delete",
            {
                "model_id": "mdl_test",
                "reason": "不再使用",
                "operator": "operator",
            },
        ),
        (
            "restore",
            {
                "model_id": "mdl_test",
                "operator": "operator",
            },
        ),
        (
            "purge",
            {
                "model_id": "mdl_test",
                "reason": "不再使用",
                "operator": "operator",
            },
        ),
    ],
)
async def test_dispatch_model_deletion_actions_use_model_id(
        action: str,
        expected_arguments: dict[str, str],
) -> None:
    """测试模型回收站动作按模型 ID 调用删除服务."""
    service = MagicMock()
    setattr(
        service,
        action,
        AsyncMock(return_value={"model_id": "mdl_test"}),
    )

    result = await dispatch_resource_action(
        **_arguments(
            resource="models",
            identifier="mdl_test",
            action=action,
            reason="不再使用",
            model_deletion_factory=lambda: service,
        )
    )

    assert result["model_id"] == "mdl_test"
    getattr(service, action).assert_awaited_once_with(**expected_arguments)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    ["activate", "deactivate", "deprecate", "archive"],
)
async def test_dispatch_model_lifecycle_actions_use_model_id(
        action: str,
) -> None:
    """测试模型生命周期动作按模型 ID 调用生命周期服务."""
    service = MagicMock()
    setattr(
        service,
        action,
        AsyncMock(return_value={"model_id": "mdl_test"}),
    )

    result = await dispatch_resource_action(
        **_arguments(
            resource="models",
            identifier="mdl_test",
            action=action,
            model_lifecycle_factory=lambda: service,
        )
    )

    assert result["model_id"] == "mdl_test"
    getattr(service, action).assert_awaited_once_with(
        model_id="mdl_test",
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_dispatch_variant_toggle_maps_active_flag() -> None:
    """测试分组启停动作统一映射为活动状态."""
    service = MagicMock()
    service.set_variant_active = AsyncMock(
        return_value={"variant_id": "var_test"}
    )

    await dispatch_resource_action(
        **_arguments(
            resource="variants",
            identifier="var_test",
            action="disable",
            experiment_factory=lambda: service,
        )
    )

    service.set_variant_active.assert_awaited_once_with(
        variant_id="var_test",
        active=False,
        updated_by="operator",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "retry"])
async def test_dispatch_batch_actions(
        action: str,
) -> None:
    """测试批次动作按批次 ID 调用生命周期服务."""
    service = MagicMock()
    setattr(
        service,
        action,
        AsyncMock(return_value={"batch_id": "bat_test"}),
    )

    result = await dispatch_resource_action(
        **_arguments(
            resource="batches",
            identifier="bat_test",
            action=action,
            batch_factory=lambda: service,
        )
    )

    assert result["batch_id"] == "bat_test"
    getattr(service, action).assert_awaited_once_with(
        batch_id="bat_test"
    )
