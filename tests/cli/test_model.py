"""CLI 模型命令测试

验证模型命令使用认证上下文中的操作人和对应权限。

核心功能：
  - test_activate_model_versions:
    验证激活模型时批量激活模型版本
  - test_activate_uses_authenticated_actor:
    验证激活模型使用认证用户作为实际操作人
  - test_activate_renders_clean_business_error:
    验证激活模型使用简洁的业务错误提示
  - test_deactivate_renders_clean_business_error:
    验证停用模型使用简洁的业务错误提示
  - test_deprecate_uses_authenticated_actor:
    验证弃用模型使用认证用户作为实际操作人
  - test_deletion_commands_render_clean_business_error:
    验证模型删除相关命令使用简洁的业务错误提示
  - test_show_rejects_foreign_version_without_traceback:
    验证查看模型拒绝不属于当前模型的版本
  - test_register_renders_clean_business_error:
    验证注册模型使用简洁的业务错误提示
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

import datamind.cli.model.activate as activate_module
import datamind.cli.model.deactivate as deactivate_module
import datamind.cli.model.deprecate as deprecate_module
import datamind.cli.model.delete as delete_module
import datamind.cli.model.purge as purge_module
import datamind.cli.model.register as register_module
import datamind.cli.model.restore as restore_module
import datamind.cli.model.show as show_module
from datamind.cli.main import app
from datamind.models.errors import (
    InvalidModelStateError,
    VersionNotFoundError,
)


runner = CliRunner()


DELETION_COMMAND_CASES = (
    (
        delete_module,
        "delete",
        [
            "model",
            "delete",
            "scorecard",
            "--yes",
        ],
        "模型删除失败：",
    ),
    (
        purge_module,
        "purge",
        [
            "model",
            "purge",
            "scorecard",
            "--yes",
        ],
        "模型永久清理失败：",
    ),
    (
        restore_module,
        "restore",
        [
            "model",
            "restore",
            "scorecard",
        ],
        "模型恢复失败：",
    ),
)


class FakeCLIContext:
    """CLI 认证上下文替身"""

    async def __aenter__(self) -> SimpleNamespace:
        return SimpleNamespace(
            user="alice"
        )

    async def __aexit__(self, *_args: object) -> bool:
        return False


class FakeUnitOfWork:
    """模型命令测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.parametrize(
    (
        "command_module",
        "method_name",
        "arguments",
        "message_prefix",
    ),
    DELETION_COMMAND_CASES,
)
def test_deletion_commands_render_clean_business_error(
        monkeypatch: pytest.MonkeyPatch,
        command_module: object,
        method_name: str,
        arguments: list[str],
        message_prefix: str,
) -> None:
    """测试模型删除相关命令使用简洁的业务错误提示"""
    error_message = (
        "模型或版本存在活动部署，请先禁用相关部署"
    )
    service = MagicMock()
    setattr(
        service,
        method_name,
        AsyncMock(
            side_effect=InvalidModelStateError(
                error_message
            )
        ),
    )

    monkeypatch.setitem(
        vars(command_module),
        "ModelDeletionService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(command_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )
    monkeypatch.setitem(
        vars(command_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    result = runner.invoke(
        app,
        arguments,
    )

    assert result.exit_code == 1
    assert (
        message_prefix + error_message
    ) in result.output
    assert "Traceback" not in result.output


def test_activate_model_versions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未指定版本时批量激活模型版本"""
    lifecycle = MagicMock()
    lifecycle.activate = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "name": "scorecard",
            "model_status": "active",
            "version_id": None,
            "version": None,
            "version_status": None,
            "activated_version_count": 2,
        }
    )
    monkeypatch.setitem(
        vars(activate_module),
        "ModelLifecycleService",
        lambda: lifecycle,
    )
    monkeypatch.setitem(
        vars(activate_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )
    monkeypatch.setitem(
        vars(activate_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    result = runner.invoke(
        app,
        [
            "model",
            "activate",
            "scorecard",
        ],
    )

    assert result.exit_code == 0
    assert "VERSION CHANGES" in result.output
    lifecycle.activate.assert_awaited_once_with(
        name="scorecard",
        model_id=None,
        version=None,
        version_id=None,
        updated_by="alice",
    )


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


def test_deprecate_uses_authenticated_actor(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试弃用模型使用认证用户作为实际操作人"""
    lifecycle = MagicMock()
    lifecycle.deprecate = AsyncMock(
        return_value={
            "model_id": "mdl_test",
            "name": "scorecard",
            "model_status": "deprecated",
            "version_id": None,
            "version": None,
            "version_status": None,
            "deprecated_version_count": 2,
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

    monkeypatch.setitem(
        vars(deprecate_module),
        "ModelLifecycleService",
        lambda: lifecycle,
    )
    monkeypatch.setitem(
        vars(deprecate_module),
        "cli_context",
        create_context,
    )
    monkeypatch.setitem(
        vars(deprecate_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    deprecate_module.deprecate_model(
        name="scorecard",
        model_id=None,
        version=None,
        version_id=None,
        output="json",
    )

    lifecycle.deprecate.assert_awaited_once_with(
        name="scorecard",
        model_id=None,
        version=None,
        version_id=None,
        updated_by="alice",
    )
    assert context_options == {
        "required_permission": "model.write",
    }


def test_activate_renders_clean_business_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试激活模型使用简洁的业务错误提示"""
    lifecycle = MagicMock()
    lifecycle.activate = AsyncMock(
        side_effect=InvalidModelStateError(
            "当前状态不允许激活"
        )
    )

    monkeypatch.setitem(
        vars(activate_module),
        "ModelLifecycleService",
        lambda: lifecycle,
    )
    monkeypatch.setitem(
        vars(activate_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )
    monkeypatch.setitem(
        vars(activate_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    result = runner.invoke(
        app,
        [
            "model",
            "activate",
            "scorecard",
            "--version",
            "1.0.0",
        ],
    )

    assert result.exit_code == 1
    assert (
        "模型激活失败："
        "当前状态不允许激活"
    ) in result.output
    assert "Traceback" not in result.output


def test_deactivate_renders_clean_business_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试停用模型使用简洁的业务错误提示"""
    lifecycle = MagicMock()
    lifecycle.deactivate = AsyncMock(
        side_effect=InvalidModelStateError(
            "模型版本存在活动部署，"
            "请先禁用相关部署"
        )
    )

    monkeypatch.setitem(
        vars(deactivate_module),
        "ModelLifecycleService",
        lambda: lifecycle,
    )
    monkeypatch.setitem(
        vars(deactivate_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )
    monkeypatch.setitem(
        vars(deactivate_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    result = runner.invoke(
        app,
        [
            "model",
            "deactivate",
            "scorecard",
            "--version",
            "1.0.0",
        ],
    )

    assert result.exit_code == 1
    assert (
        "模型停用失败："
        "模型版本存在活动部署，"
        "请先禁用相关部署"
    ) in result.output
    assert "Traceback" not in result.output


def test_show_rejects_foreign_version_without_traceback(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试查看模型拒绝不属于当前模型的版本"""
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(
        return_value=SimpleNamespace(
            model_id="mdl_scorecard",
        )
    )
    resolver.resolve_version = AsyncMock(
        side_effect=VersionNotFoundError(
            "版本不存在: ver_another"
        )
    )

    monkeypatch.setitem(
        vars(show_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(show_module),
        "MetadataRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(show_module),
        "VersionRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(show_module),
        "ModelResolver",
        lambda **_repositories: resolver,
    )
    monkeypatch.setitem(
        vars(show_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )

    result = runner.invoke(
        app,
        [
            "model",
            "show",
            "scorecard",
            "--version-id",
            "ver_another",
        ],
    )

    assert result.exit_code == 1
    assert (
        "查看模型失败："
        "版本不存在: ver_another"
    ) in result.output
    assert "Traceback" not in result.output


def test_register_renders_clean_business_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试注册模型使用简洁的业务错误提示"""
    service = MagicMock()
    service.register = AsyncMock(
        side_effect=ValueError(
            "模型已存在，注册新版本时不能修改模型描述"
        )
    )

    monkeypatch.setitem(
        vars(register_module),
        "ModelRegistrationService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(register_module),
        "cli_context",
        lambda **_options: FakeCLIContext(),
    )
    monkeypatch.setitem(
        vars(register_module),
        "audit",
        lambda **_options: (
            lambda function: function
        ),
    )

    result = runner.invoke(
        app,
        [
            "model",
            "register",
            "scorecard",
            "--version",
            "3.0.0",
            "--model-path",
            "scorecard.pkl",
            "--framework",
            "sklearn",
            "--model-type",
            "logistic_regression",
            "--task-type",
            "scoring",
            "--description",
            "新描述",
        ],
    )

    assert result.exit_code == 1
    assert (
        "模型注册失败：模型已存在，"
        "注册新版本时不能修改模型描述"
    ) in result.output
    assert "Traceback" not in result.output

