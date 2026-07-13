# tests/cli/test_model.py

"""CLI 模型命令测试

验证模型命令使用认证上下文中的操作人和对应权限。

核心功能：
  - test_activate_uses_authenticated_actor:
    验证激活模型使用认证用户作为实际操作人
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.cli.model.activate as activate_module


class FakeCLIContext:
    """CLI 认证上下文替身"""

    async def __aenter__(self) -> SimpleNamespace:
        return SimpleNamespace(
            user="alice"
        )

    async def __aexit__(self, *_args: object) -> bool:
        return False


def test_activate_uses_authenticated_actor(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型使用认证用户作为实际操作人"""
    lifecycle = MagicMock()
    lifecycle.activate = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "name": "scorecard",
            "model_status": "active",
        }
    )
    context_options: dict[str, object] = {}

    def create_context(
            **options: object,
    ) -> FakeCLIContext:
        context_options.update(
            options
        )
        return FakeCLIContext()

    def passthrough_audit(
            **_options: object,
    ):
        return lambda function: function

    monkeypatch.setitem(
        vars(activate_module),
        "ModelLifecycleService",
        lambda: lifecycle,
    )
    monkeypatch.setitem(
        vars(activate_module),
        "cli_context",
        create_context,
    )
    monkeypatch.setitem(
        vars(activate_module),
        "audit",
        passthrough_audit,
    )

    activate_module.activate_model(
        name="scorecard",
        model_id=None,
        version="1.0.0",
        version_id=None,
        output="json",
    )

    lifecycle.activate.assert_awaited_once_with(
        name="scorecard",
        model_id=None,
        version="1.0.0",
        version_id=None,
        updated_by="alice",
    )
    assert context_options == {
        "required_permission": "model.write",
    }

