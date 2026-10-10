"""CLI 主入口测试.

验证主要命令组和新增业务入口能够被 Typer 正确加载。

核心功能：
  - test_main_initializes_configured_logging:
    验证主入口使用日志配置初始化日志系统
  - test_main_help_lists_command_groups:
    验证主入口列出全部命令组
  - test_main_version_reports_build_identity:
    验证版本命令仅为正式构建展示 Commit 与 Build Date
  - test_init_help_lists_initialization_options:
    验证系统初始化命令可用
  - test_main_help_lists_session_commands:
    验证顶层登录会话命令可用
  - test_identity_help_lists_management_commands:
    验证用户和角色管理命令可用
  - test_business_command_help_is_available:
    验证全部业务命令能够生成帮助信息
  - test_service_and_runtime_commands_have_separate_responsibilities:
    测试服务进程与运行状态命令边界清晰
  - test_cli_uses_configured_service_environment:
    测试单环境 CLI 不公开环境参数
  - test_init_help_does_not_list_credential_options:
    测试系统初始化命令不公开管理员凭据参数
  - test_removed_feedback_command_is_unavailable:
    测试 CLI 不再公开业务结果提交入口
"""

from unittest.mock import MagicMock

import pytest
import typer
from click import unstyle
from typer.core import TyperGroup
from typer.testing import CliRunner

import datamind.cli.main as main_module
from datamind.cli.main import app
from datamind.cli.runtime import app as runtime_app
from datamind.cli.service import app as service_app

runner = CliRunner()

BUSINESS_COMMANDS = [
    "model register",
    "model list",
    "model show",
    "model activate",
    "model deactivate",
    "model deprecate",
    "model delete",
    "model restore",
    "model purge",
    "deployment create",
    "deployment list",
    "deployment show",
    "deployment enable",
    "deployment disable",
    "deployment delete",
    "deployment restore",
    "route create",
    "route list",
    "route show",
    "route update",
    "route enable",
    "route disable",
    "route delete",
    "route restore",
    "experiment create",
    "experiment list",
    "experiment show",
    "experiment update",
    "experiment start",
    "experiment pause",
    "experiment stop",
    "experiment complete",
    "experiment archive",
    "experiment analyze",
    "experiment delete",
    "experiment restore",
    "experiment variant add",
    "experiment variant list",
    "experiment variant show",
    "experiment variant update",
    "experiment variant activate",
    "experiment variant deactivate",
    "experiment variant archive",
    "experiment variant delete",
    "experiment variant restore",
    "service run",
    "service healthcheck",
    "runtime list",
    "runtime show",
    "console run",
    "console healthcheck",
    "worker run",
    "worker healthcheck",
    "user create",
    "user list",
    "user show",
    "user enable",
    "user disable",
    "user reset-password",
    "user delete",
    "role create",
    "role list",
    "role show",
    "role grant",
    "role revoke",
    "role delete",
]

SERVICE_ENVIRONMENT_COMMANDS = [
    "deployment create",
    "deployment list",
    "route create",
    "route list",
    "route update",
    "experiment create",
    "experiment list",
    "experiment update",
    "runtime list",
    "service run",
    "service healthcheck",
]


@pytest.mark.parametrize(
    ("commit", "build_date", "expected"),
    [
        (
            "dev",
            None,
            "datamind version 0.1.0",
        ),
        (
            "0123456789abcdef0123456789abcdef01234567",
            "2026-09-21T02:09:32Z",
            (
                "datamind version 0.1.0 "
                "(commit 01234567, "
                "built 2026-09-21T02:09:32Z)"
            ),
        ),
    ],
)
def test_main_version_reports_build_identity(
        monkeypatch: pytest.MonkeyPatch,
        commit: str,
        build_date: str | None,
        expected: str,
) -> None:
    """测试开发构建隐藏默认值，正式构建展示短提交哈希."""
    requested_distributions: list[str] = []
    monkeypatch.setitem(vars(main_module), "BUILD_COMMIT", commit)
    monkeypatch.setitem(vars(main_module), "BUILD_DATE", build_date)
    monkeypatch.setitem(
        vars(main_module),
        "version",
        lambda name: requested_distributions.append(name) or "0.1.0",
    )

    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert unstyle(result.stdout).strip() == expected
    assert requested_distributions == ["pydatamind"]


def test_main_initializes_configured_logging(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试主入口使用日志配置初始化日志系统."""
    logging_config = MagicMock()
    setup_logging = MagicMock()
    monkeypatch.setitem(
        vars(main_module),
        "get_logging_config",
        lambda: logging_config,
    )
    monkeypatch.setitem(
        vars(main_module),
        "setup_logging",
        setup_logging,
    )

    main_module.main()

    setup_logging.assert_called_once_with(
        logging_config
    )


def test_main_help_lists_command_groups() -> None:
    """测试主入口列出业务命令组."""
    result = runner.invoke(
        app,
        ["--help"],
    )

    assert result.exit_code == 0
    assert "init" in result.stdout
    assert "user" in result.stdout
    assert "role" in result.stdout
    assert "runtime" in result.stdout
    assert "console" in result.stdout
    assert "worker" in result.stdout


def test_service_and_runtime_commands_have_separate_responsibilities() -> None:
    """测试服务进程与运行状态命令边界清晰."""
    service_group = typer.main.get_command(service_app)
    runtime_group = typer.main.get_command(runtime_app)

    assert isinstance(service_group, TyperGroup)
    assert isinstance(runtime_group, TyperGroup)

    service_commands = set(service_group.commands)
    runtime_commands = set(runtime_group.commands)

    assert service_commands == {"run", "healthcheck"}
    assert runtime_commands == {"list", "show"}


@pytest.mark.parametrize("command", SERVICE_ENVIRONMENT_COMMANDS)
def test_cli_uses_configured_service_environment(command: str) -> None:
    """测试单环境 CLI 不公开环境参数."""
    result = runner.invoke(
        app,
        [*command.split(), "--help"],
    )

    assert result.exit_code == 0
    assert "--environment" not in result.stdout


def test_init_help_does_not_list_credential_options() -> None:
    """测试系统初始化命令不公开管理员凭据参数."""
    result = runner.invoke(
        app,
        [
            "init",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--username" not in result.stdout
    assert "--password-file" not in result.stdout


def test_main_help_lists_session_commands() -> None:
    """测试主入口列出顶层登录会话命令."""
    result = runner.invoke(
        app,
        ["--help"],
    )

    assert result.exit_code == 0

    for command in (
            "login",
            "whoami",
            "logout",
    ):
        assert command in result.stdout




def test_identity_help_lists_management_commands() -> None:
    """测试用户和角色命令列出完整管理操作."""
    user_result = runner.invoke(
        app,
        ["user", "--help"],
    )
    role_result = runner.invoke(
        app,
        ["role", "--help"],
    )

    assert user_result.exit_code == 0
    assert role_result.exit_code == 0

    for command in (
            "create",
            "list",
            "show",
            "enable",
            "disable",
            "reset-password",
            "delete",
    ):
        assert command in user_result.stdout

    for command in (
            "create",
            "list",
            "show",
            "grant",
            "revoke",
            "delete",
    ):
        assert command in role_result.stdout


@pytest.mark.parametrize(
    "command_path",
    BUSINESS_COMMANDS,
)
def test_business_command_help_is_available(
        command_path: str,
) -> None:
    """测试业务命令帮助可用且不接受外部操作人."""
    result = runner.invoke(
        app,
        [
            *command_path.split(),
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--operator" not in result.stdout
    assert "--owner" not in result.stdout

    if command_path == "model list":
        assert "--created-by" in unstyle(result.stdout)


def test_removed_feedback_command_is_unavailable() -> None:
    """测试 CLI 不再公开业务结果提交入口."""
    result = runner.invoke(app, ["outcome", "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output
