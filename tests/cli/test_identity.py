# tests/cli/test_identity.py

"""CLI 身份管理命令测试

验证用户和角色命令使用当前认证身份执行高风险操作。

核心功能：
  - test_create_user_uses_authenticated_operator:
    验证创建用户使用当前认证操作人
  - test_reset_current_user_password_clears_session:
    验证重置当前用户密码后清理会话
  - test_delete_user_passes_required_reason:
    验证删除用户传递删除原因
  - test_grant_role_uses_authenticated_operator:
    验证角色授予使用当前认证操作人
  - test_create_role_renders_colored_result_fields:
    验证创建角色使用标准结果字段布局
  - test_user_list_renders_count_and_updated_at:
    验证用户列表显示总数和更新时间
  - test_role_list_renders_count_and_updated_at:
    验证角色列表显示总数和更新时间
  - test_show_user_renders_standard_detail_layout:
    验证用户详情使用标准文本布局
  - test_show_role_renders_standard_detail_layout:
    验证角色详情使用标准文本布局
"""

from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from typer.testing import CliRunner

import datamind.cli.role.create as role_create_module
import datamind.cli.role.grant as grant_module
import datamind.cli.role.list as role_list_module
import datamind.cli.role.show as role_show_module
import datamind.cli.user.create as create_module
import datamind.cli.user.delete as delete_module
import datamind.cli.user.list as user_list_module
import datamind.cli.user.reset as reset_module
import datamind.cli.user.show as show_module
from datamind.cli.main import app


runner = CliRunner()


class FakeCLIContext:
    """身份命令测试 CLI 上下文"""

    def __init__(self) -> None:
        self.user = "admin"
        self.authenticated_user = SimpleNamespace(
            user_id="usr_admin",
            username="admin",
        )

    async def __aenter__(self) -> "FakeCLIContext":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def install_command(
        monkeypatch: pytest.MonkeyPatch,
        command_module: object,
        service: MagicMock,
) -> None:
    """安装身份命令服务和上下文替身"""
    namespace = vars(
        command_module
    )
    monkeypatch.setitem(
        namespace,
        "IdentityService",
        lambda: service,
    )
    monkeypatch.setitem(
        namespace,
        "cli_context",
        lambda **_kwargs: FakeCLIContext(),
    )


def test_create_user_uses_authenticated_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建用户使用当前认证操作人"""
    service = MagicMock()
    service.create_user = AsyncMock(
        return_value={
            "user_id": "usr_analyst",
            "username": "analyst",
            "roles": [
                "model-reader"
            ],
        }
    )
    install_command(
        monkeypatch,
        create_module,
        service,
    )

    result = runner.invoke(
        app,
        [
            "user",
            "create",
            "analyst",
            "--role",
            "model-reader",
        ],
        input="secret\nsecret\n",
    )

    assert result.exit_code == 0
    assert "用户创建成功" in result.output
    assert "USER ID" in result.output
    assert "USERNAME" in result.output
    assert "ROLES" in result.output
    service.create_user.assert_awaited_once_with(
        username="analyst",
        password="secret",
        display_name=None,
        email=None,
        role_names=[
            "model-reader"
        ],
        operator_id="usr_admin",
        operator="admin",
    )


def test_reset_current_user_password_clears_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重置当前用户密码后清理会话"""
    service = MagicMock()
    service.reset_password = AsyncMock(
        return_value={
            "username": "admin"
        }
    )
    store = MagicMock()
    install_command(
        monkeypatch,
        reset_module,
        service,
    )
    monkeypatch.setitem(
        vars(reset_module),
        "CredentialStore",
        lambda: store,
    )

    result = runner.invoke(
        app,
        [
            "user",
            "reset-password",
            "admin",
        ],
        input="new-secret\nnew-secret\n",
    )

    assert result.exit_code == 0
    assert "请重新登录" in result.output
    store.clear.assert_called_once_with()


def test_delete_user_passes_required_reason(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试删除用户传递删除原因"""
    service = MagicMock()
    service.delete_user = AsyncMock(
        return_value={
            "username": "analyst"
        }
    )
    install_command(
        monkeypatch,
        delete_module,
        service,
    )

    result = runner.invoke(
        app,
        [
            "user",
            "delete",
            "analyst",
            "--reason",
            "员工离职",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    service.delete_user.assert_awaited_once_with(
        username="analyst",
        reason="员工离职",
        operator_id="usr_admin",
        operator="admin",
    )


def test_grant_role_uses_authenticated_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试角色授予使用当前认证操作人"""
    service = MagicMock()
    service.grant_role = AsyncMock(
        return_value={
            "username": "analyst",
            "role": "model-reader",
        }
    )
    install_command(
        monkeypatch,
        grant_module,
        service,
    )

    result = runner.invoke(
        app,
        [
            "role",
            "grant",
            "analyst",
            "model-reader",
        ],
    )

    assert result.exit_code == 0
    service.grant_role.assert_awaited_once_with(
        username="analyst",
        role_name="model-reader",
        operator_id="usr_admin",
        operator="admin",
    )


def test_create_role_renders_colored_result_fields(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建角色使用标准结果字段布局"""
    service = MagicMock()
    service.create_role = AsyncMock(
        return_value={
            "name": "developer",
            "permissions": [
                "model.read",
                "model.write",
            ],
        }
    )
    install_command(
        monkeypatch,
        role_create_module,
        service,
    )

    result = runner.invoke(
        app,
        [
            "role",
            "create",
            "developer",
            "--permission",
            "model.read",
            "--permission",
            "model.write",
        ],
    )

    assert result.exit_code == 0
    assert "角色创建成功" in result.output
    assert "NAME" in result.output
    assert "developer" in result.output
    assert "PERMISSIONS" in result.output
    assert "model.read, model.write" in result.output


def test_user_list_renders_count_and_updated_at(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试用户列表显示总数和更新时间"""
    service = MagicMock()
    service.list_users = AsyncMock(
        return_value=[
            {
                "username": "alice",
                "status": "active",
                "display_name": "Alice",
                "roles": [
                    "developer"
                ],
                "updated_at": (
                    "2026-08-03T09:30:00.000Z"
                ),
            }
        ]
    )
    install_command(
        monkeypatch,
        user_list_module,
        service,
    )
    monkeypatch.setitem(
        vars(user_list_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=SimpleNamespace(
                timezone="Asia/Shanghai"
            )
        ),
    )

    result = runner.invoke(
        app,
        [
            "user",
            "list",
        ],
    )

    assert result.exit_code == 0
    assert "共找到 1 个用户" in result.output
    assert "UPDATED AT" in result.output
    assert "DELETED AT" not in result.output


def test_role_list_renders_count_and_updated_at(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试角色列表显示总数和更新时间"""
    service = MagicMock()
    service.list_roles = AsyncMock(
        return_value=[
            {
                "name": "developer",
                "status": "active",
                "permissions": [
                    "model.read"
                ],
                "updated_at": (
                    "2026-08-03T09:30:00.000Z"
                ),
            }
        ]
    )
    install_command(
        monkeypatch,
        role_list_module,
        service,
    )
    monkeypatch.setitem(
        vars(role_list_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=SimpleNamespace(
                timezone="Asia/Shanghai"
            )
        ),
    )

    result = runner.invoke(
        app,
        [
            "role",
            "list",
        ],
    )

    assert result.exit_code == 0
    assert "共找到 1 个角色" in result.output
    assert "UPDATED AT" in result.output
    assert "DELETED AT" not in result.output


def test_show_user_renders_standard_detail_layout(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试用户详情使用标准文本布局"""
    service = MagicMock()
    service.get_user = AsyncMock(
        return_value={
            "user_id": "usr_alice",
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "status": "active",
            "roles": [
                "developer"
            ],
            "last_login_at": None,
            "created_at": "2026-08-04T01:00:00+00:00",
            "deleted_at": None,
        }
    )
    install_command(
        monkeypatch,
        show_module,
        service,
    )
    monkeypatch.setitem(
        vars(show_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=SimpleNamespace(
                timezone="Asia/Shanghai"
            )
        ),
    )

    result = runner.invoke(
        app,
        [
            "user",
            "show",
            "alice",
        ],
    )

    assert result.exit_code == 0
    assert "用户详情" in result.output
    assert "USER ID" in result.output
    assert "usr_alice" in result.output
    assert "USERNAME" in result.output
    assert "alice" in result.output
    assert "ROLES" in result.output
    assert "developer" in result.output
    assert "CREATED AT" in result.output
    assert "DELETED AT" not in result.output


def test_show_role_renders_standard_detail_layout(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试角色详情使用标准文本布局"""
    service = MagicMock()
    service.get_role = AsyncMock(
        return_value={
            "role_id": "rol_developer",
            "name": "developer",
            "description": "模型开发角色",
            "permissions": [
                "model.read",
                "model.write",
            ],
            "status": "active",
            "created_at": "2026-08-04T01:00:00+00:00",
            "deleted_at": None,
        }
    )
    install_command(
        monkeypatch,
        role_show_module,
        service,
    )
    monkeypatch.setitem(
        vars(role_show_module),
        "get_settings",
        lambda: SimpleNamespace(
            logging=SimpleNamespace(
                timezone="Asia/Shanghai"
            )
        ),
    )

    result = runner.invoke(
        app,
        [
            "role",
            "show",
            "developer",
        ],
    )

    assert result.exit_code == 0
    assert "角色详情" in result.output
    assert "ROLE ID" in result.output
    assert "rol_developer" in result.output
    assert "NAME" in result.output
    assert "developer" in result.output
    assert "PERMISSIONS" in result.output
    assert "model.read, model.write" in result.output
    assert "CREATED AT" in result.output
    assert "DELETED AT" not in result.output
