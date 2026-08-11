# tests/cli/test_auth.py

"""CLI 认证会话命令测试

验证本地登录、身份查询和退出登录命令。

核心功能：
  - test_login_saves_session_without_rendering_tokens:
    验证登录保存会话且不显示令牌
  - test_whoami_uses_cli_context:
    验证查询当前 CLI 身份
  - test_logout_revokes_and_clears_session:
    验证退出并清理本地会话
  - test_auth_commands_render_clean_error:
    验证认证失败不显示 traceback
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import (
    ModuleType,
    SimpleNamespace,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from typer.testing import CliRunner

import datamind.cli.auth.login as login_module
import datamind.cli.auth.logout as logout_module
import datamind.cli.auth.whoami as whoami_module
from datamind.auth.errors import InvalidCredentialsError
from datamind.auth.schemas import TokenResponse
from datamind.cli.credentials import CLICredentials
from datamind.cli.errors import CredentialError
from datamind.context import (
    get_context,
    is_valid_trace_id,
)
from datamind.context.scope import context_scope
from datamind.cli.main import app


runner = CliRunner()


class FakeUnitOfWork:
    """认证命令测试工作单元"""

    exit_exception_type: type[BaseException] | None = None

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(
            self,
            exception_type: type[BaseException] | None,
            *_args: object,
    ) -> bool:
        type(self).exit_exception_type = exception_type
        return False


@asynccontextmanager
async def fake_cli_context(
        *,
        user: object | None = None,
        error: Exception | None = None,
) -> AsyncIterator[SimpleNamespace]:
    """创建身份查询命令测试上下文"""
    if error is not None:
        raise error

    context_user = getattr(
        user,
        "username",
        "system",
    )
    if not isinstance(context_user, str):
        context_user = "system"

    context = SimpleNamespace(
        authenticated_user=user,
        user=context_user,
    )
    with context_scope(
            trace_id="1" * 32,
            request_id="req_0123456789abcdef",
            source="cli",
            user=context_user,
            ip="127.0.0.1",
            hostname="datamind-host",
    ):
        yield context


@pytest.fixture(autouse=True)
def isolate_cli_logging(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """隔离认证命令日志"""
    for command_module in (
            login_module,
            logout_module,
            whoami_module,
    ):
        monkeypatch.setitem(
            vars(command_module),
            "logger",
            MagicMock(),
        )


def create_tokens() -> TokenResponse:
    """创建认证命令测试令牌"""
    return TokenResponse(
        access_token="access-token",
        refresh_token="refresh-token",
        expires_in=1800,
    )


def create_credentials() -> CLICredentials:
    """创建认证命令测试凭据"""
    return CLICredentials(
        access_token="access-token",
        refresh_token="refresh-token",
    )


def install_auth_service(
        monkeypatch: pytest.MonkeyPatch,
        command_module: ModuleType,
        service: MagicMock,
) -> None:
    """安装认证服务替身"""
    FakeUnitOfWork.exit_exception_type = None
    monkeypatch.setitem(
        vars(command_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(command_module),
        "create_auth_service",
        lambda **_kwargs: service,
    )

    if command_module in (
            login_module,
            logout_module,
    ):
        service.authenticate_access_token = AsyncMock(
            return_value=SimpleNamespace(
                username="current-user"
            )
        )

    if command_module is login_module:
        monkeypatch.setitem(
            vars(command_module),
            "get_host_ip",
            lambda: "127.0.0.1",
        )
        monkeypatch.setitem(
            vars(command_module),
            "get_hostname",
            lambda: "datamind-host",
        )


def install_store(
        monkeypatch: pytest.MonkeyPatch,
        command_module: ModuleType,
        store: MagicMock,
) -> None:
    """安装 CLI 凭据存储替身"""
    monkeypatch.setitem(
        vars(command_module),
        "CredentialStore",
        lambda: store,
    )


def test_login_saves_session_without_rendering_tokens(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录保存会话且不显示令牌"""
    tokens = create_tokens()
    service = MagicMock()
    service.login = AsyncMock(
        return_value=tokens
    )
    store = MagicMock()
    store.load.return_value = None
    install_auth_service(
        monkeypatch,
        login_module,
        service,
    )
    install_store(
        monkeypatch,
        login_module,
        store,
    )
    log_contexts: list[dict[str, object]] = []
    login_module.logger.info.side_effect = (
        lambda *_args, **_kwargs: log_contexts.append(
            get_context().copy()
        )
    )

    result = runner.invoke(
        app,
        [
            "login",
            "--username",
            "alice",
        ],
        input="secret\n",
    )

    assert result.exit_code == 0
    assert "登录成功" in result.output
    assert "登录成功：alice" not in result.output
    assert "访问令牌有效期" not in result.output
    assert "access-token" not in result.output
    assert "refresh-token" not in result.output
    store.save.assert_called_once_with(
        tokens
    )
    login_call = service.login.await_args
    assert login_call is not None
    request = login_call.args[0]
    assert request.username == "alice"
    assert request.password.get_secret_value() == "secret"
    assert login_call.kwargs == {
        "ip": "127.0.0.1",
        "hostname": "datamind-host",
        "user_agent": "datamind-cli",
    }
    assert len(log_contexts) == 2
    start_context, success_context = log_contexts
    trace_id = start_context["trace_id"]
    assert isinstance(trace_id, str)
    assert is_valid_trace_id(
        trace_id
    )
    assert start_context["request_id"] == (
        success_context["request_id"]
    )
    assert start_context["trace_id"] == (
        success_context["trace_id"]
    )
    assert start_context["user"] == "anonymous"
    assert success_context["user"] == "alice"
    assert success_context["source"] == "cli"
    assert success_context["ip"] == "127.0.0.1"
    assert success_context["hostname"] == "datamind-host"


def test_login_revokes_previous_session_before_saving_new_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试登录成功后撤销并替换已有本地会话"""
    tokens = create_tokens()
    service = MagicMock()
    service.login = AsyncMock(
        return_value=tokens
    )
    service.logout = AsyncMock(
        return_value=True
    )
    store = MagicMock()
    store.load.return_value = create_credentials()
    install_auth_service(
        monkeypatch,
        login_module,
        service,
    )
    install_store(
        monkeypatch,
        login_module,
        store,
    )
    log_contexts: list[dict[str, object]] = []
    login_module.logger.info.side_effect = (
        lambda *_args, **_kwargs: log_contexts.append(
            get_context().copy()
        )
    )

    result = runner.invoke(
        app,
        [
            "login",
            "--username",
            "alice",
        ],
        input="secret\n",
    )

    assert result.exit_code == 0
    logout_call = service.logout.await_args
    assert logout_call is not None
    request = logout_call.args[0]
    assert request.refresh_token.get_secret_value() == (
        "refresh-token"
    )
    store.save.assert_called_once_with(
        tokens
    )
    service.authenticate_access_token.assert_awaited_once_with(
        "access-token"
    )
    assert log_contexts[0]["user"] == "current-user"
    assert log_contexts[1]["user"] == "alice"


def test_login_replaces_invalid_stored_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有凭据损坏时仍可保存新的登录会话"""
    tokens = create_tokens()
    service = MagicMock()
    service.login = AsyncMock(
        return_value=tokens
    )
    store = MagicMock()
    store.load.side_effect = CredentialError(
        "CLI 凭据文件格式无效"
    )
    install_auth_service(
        monkeypatch,
        login_module,
        service,
    )
    install_store(
        monkeypatch,
        login_module,
        store,
    )

    result = runner.invoke(
        app,
        [
            "login",
            "--username",
            "alice",
        ],
        input="secret\n",
    )

    assert result.exit_code == 0
    service.logout.assert_not_called()
    store.save.assert_called_once_with(
        tokens
    )


def test_login_failure_preserves_previous_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试新登录失败时不撤销或覆盖已有会话"""
    service = MagicMock()
    service.login = AsyncMock(
        side_effect=InvalidCredentialsError(
            "认证被拒绝"
        )
    )
    service.logout = AsyncMock()
    store = MagicMock()
    store.load.return_value = create_credentials()
    install_auth_service(
        monkeypatch,
        login_module,
        service,
    )
    install_store(
        monkeypatch,
        login_module,
        store,
    )

    result = runner.invoke(
        app,
        [
            "login",
            "--username",
            "alice",
        ],
        input="wrong-secret\n",
    )

    assert result.exit_code == 1
    service.logout.assert_not_awaited()
    store.save.assert_not_called()
    assert FakeUnitOfWork.exit_exception_type is None


def test_whoami_uses_cli_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份查询使用当前 CLI 登录会话"""
    user = SimpleNamespace(
        username="alice",
        model_dump=lambda **_kwargs: {
            "user_id": "usr_alice",
            "username": "alice",
            "display_name": "Alice",
            "email": "alice@example.com",
            "status": "active",
            "roles": [
                "developer"
            ],
            "permissions": [
                "model.read",
                "model.write",
            ],
        }
    )
    monkeypatch.setitem(
        vars(whoami_module),
        "cli_context",
        lambda: fake_cli_context(
            user=user
        ),
    )
    log_contexts: list[dict[str, object]] = []
    whoami_module.logger.info.side_effect = (
        lambda *_args, **_kwargs: log_contexts.append(
            get_context().copy()
        )
    )

    result = runner.invoke(
        app,
        [
            "whoami",
        ],
    )

    assert result.exit_code == 0
    assert "当前登录身份" in result.output
    assert "USER ID" in result.output
    assert "usr_alice" in result.output
    assert "USERNAME" in result.output
    assert "alice" in result.output
    assert "ROLES" in result.output
    assert "developer" in result.output
    assert "PERMISSIONS" in result.output
    assert "model.read, model.write" in result.output
    assert '"username"' not in result.output
    assert len(log_contexts) == 2
    assert log_contexts[0]["trace_id"] == (
        log_contexts[1]["trace_id"]
    )
    assert log_contexts[0]["request_id"] == (
        log_contexts[1]["request_id"]
    )
    whoami_start = (
        whoami_module.logger.info.call_args_list[0]
    )
    assert whoami_start.kwargs[
        "identity_verified"
    ] is True


def test_whoami_does_not_expose_format_option() -> None:
    """测试身份查询仅提供文本输出"""
    result = runner.invoke(
        app,
        [
            "whoami",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--format" not in result.output


def test_logout_revokes_and_clears_session(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试退出登录撤销刷新令牌并清理凭据"""
    service = MagicMock()
    service.logout = AsyncMock(
        return_value=True
    )
    store = MagicMock()
    store.load.return_value = create_credentials()
    install_auth_service(
        monkeypatch,
        logout_module,
        service,
    )
    install_store(
        monkeypatch,
        logout_module,
        store,
    )
    log_contexts: list[dict[str, object]] = []
    logout_module.logger.info.side_effect = (
        lambda *_args, **_kwargs: log_contexts.append(
            get_context().copy()
        )
    )

    result = runner.invoke(
        app,
        [
            "logout",
        ],
    )

    assert result.exit_code == 0
    assert "已退出登录" in result.output
    logout_call = service.logout.await_args
    assert logout_call is not None
    request = logout_call.args[0]
    assert request.refresh_token.get_secret_value() == (
        "refresh-token"
    )
    store.clear.assert_called_once_with()
    assert len(log_contexts) == 2
    trace_id = log_contexts[0]["trace_id"]
    assert isinstance(trace_id, str)
    assert is_valid_trace_id(
        trace_id
    )
    assert log_contexts[0]["trace_id"] == (
        log_contexts[1]["trace_id"]
    )
    assert log_contexts[0]["request_id"] == (
        log_contexts[1]["request_id"]
    )
    assert log_contexts[0]["source"] == "cli"
    assert log_contexts[0]["user"] == "current-user"
    assert log_contexts[1]["user"] == "current-user"
    logout_complete = (
        logout_module.logger.info.call_args_list[-1]
    )
    assert logout_complete.kwargs[
        "refresh_token_revoked"
    ] is True


@pytest.mark.parametrize(
    (
        "command_module",
        "method_name",
        "arguments",
        "input_text",
        "expected_message",
    ),
    [
        (
            login_module,
            "login",
            [
                "login",
                "--username",
                "alice",
            ],
            "secret\n",
            "登录失败：认证被拒绝",
        ),
        (
            logout_module,
            "logout",
            [
                "logout",
            ],
            None,
            "退出登录失败：认证被拒绝",
        ),
    ],
)
def test_auth_commands_render_clean_error(
        monkeypatch: pytest.MonkeyPatch,
        command_module: ModuleType,
        method_name: str,
        arguments: list[str],
        input_text: str | None,
        expected_message: str,
) -> None:
    """测试认证失败输出简洁错误且不显示 traceback"""
    service = MagicMock()
    setattr(
        service,
        method_name,
        AsyncMock(
            side_effect=InvalidCredentialsError(
                "认证被拒绝"
            )
        ),
    )
    store = MagicMock()
    store.load.return_value = create_credentials()
    install_auth_service(
        monkeypatch,
        command_module,
        service,
    )
    install_store(
        monkeypatch,
        command_module,
        store,
    )
    log_contexts: list[dict[str, object]] = []
    command_module.logger.warning.side_effect = (
        lambda *_args, **_kwargs: log_contexts.append(
            get_context().copy()
        )
    )

    result = runner.invoke(
        app,
        arguments,
        input=input_text,
    )

    assert result.exit_code == 1
    assert expected_message in result.output
    assert "Traceback" not in result.output
    assert len(log_contexts) == 1
    trace_id = log_contexts[0]["trace_id"]
    request_id = log_contexts[0]["request_id"]
    assert isinstance(trace_id, str)
    assert isinstance(request_id, str)
    assert is_valid_trace_id(
        trace_id
    )
    assert request_id.startswith("req_")
    assert log_contexts[0]["source"] == "cli"
    assert log_contexts[0]["user"] == "current-user"


def test_whoami_renders_clean_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试身份查询失败时不显示 traceback"""
    monkeypatch.setitem(
        vars(whoami_module),
        "cli_context",
        lambda: fake_cli_context(
            error=InvalidCredentialsError(
                "认证被拒绝"
            )
        ),
    )

    result = runner.invoke(
        app,
        [
            "whoami",
        ],
    )

    assert result.exit_code == 1
    assert "认证失败：认证被拒绝" in result.output
    assert "Traceback" not in result.output
