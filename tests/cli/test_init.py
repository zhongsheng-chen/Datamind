"""系统初始化 CLI 测试.

验证配置驱动的非交互初始化、成功输出和简洁错误处理。

核心功能：
  - test_init_uses_configured_credentials:
    验证使用配置中的管理员凭据完成初始化
  - test_init_rejects_missing_admin_password:
    验证未配置管理员密码时拒绝初始化
  - test_init_help_does_not_accept_credentials:
    验证初始化命令不接收管理员凭据参数
  - test_init_skips_initialized_system:
    验证系统已初始化时不读取管理员配置
  - test_init_handles_concurrent_initialization:
    验证并发完成初始化时正常退出
  - test_init_renders_clean_database_error:
    验证数据库失败不显示 traceback
  - test_init_reports_database_failure_details:
    验证数据库失败提示、实际异常类型和 SQLSTATE
  - test_init_records_outcome_logs:
    验证失败日志不包含敏感信息
"""

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from asyncpg import PostgresError, exceptions as postgres_errors
from pydantic import SecretStr
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from typer.testing import CliRunner

import datamind.cli.init as init_module
from datamind.cli.main import app
from datamind.services.errors import AlreadyInitializedError
from datamind.context.core import get_context
from datamind.services.initialization import (
    InitializationResult,
)


runner = CliRunner()


CURRENT_TIME = datetime(
    2026,
    8,
    2,
    8,
    30,
    tzinfo=timezone.utc,
)


def install_service(
        monkeypatch: pytest.MonkeyPatch,
        service: AsyncMock,
        *,
        username: str = "admin",
        password: str = "secret",
) -> MagicMock:
    """替换系统初始化服务和主机信息."""
    settings_loader = MagicMock(
        return_value=SimpleNamespace(
            admin_username=username,
            admin_password=SecretStr(
                password
            ),
        )
    )
    monkeypatch.setitem(
        vars(init_module),
        "InitializationService",
        lambda: service,
    )
    monkeypatch.setitem(
        vars(init_module),
        "get_host_ip",
        lambda: "10.0.0.10",
    )
    monkeypatch.setitem(
        vars(init_module),
        "get_hostname",
        lambda: "datamind-host",
    )
    monkeypatch.setitem(
        vars(init_module),
        "get_initialization_config",
        settings_loader,
    )

    return settings_loader


def create_service() -> AsyncMock:
    """创建成功的系统初始化服务替身."""
    service = AsyncMock()
    service.is_initialized.return_value = False
    service.initialize.return_value = InitializationResult(
        system_id="datamind",
        username="admin",
        user_id="usr_test",
        role_id="rol_test",
        initialized_at=CURRENT_TIME,
    )
    return service


def test_init_uses_configured_credentials(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试使用配置中的管理员凭据完成初始化."""
    service = create_service()
    install_service(
        monkeypatch,
        service,
        username="configured-admin",
        password="configured-secret",
    )

    result = runner.invoke(
        app,
        [
            "init"
        ],
    )

    assert result.exit_code == 0
    assert "初始化完成" in result.output
    assert "Datamind 初始化完成" not in result.output
    assert "管理员用户名" not in result.output
    assert "管理员密码" not in result.output
    assert "初始化时间" not in result.output
    assert "2026-08-02 16:30:00" not in result.output
    assert "configured-secret" not in result.output
    service.initialize.assert_awaited_once_with(
        username="configured-admin",
        password="configured-secret",
        ip="10.0.0.10",
        hostname="datamind-host",
    )


def test_init_rejects_missing_admin_password(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未配置管理员密码时拒绝初始化."""
    service = create_service()
    install_service(
        monkeypatch,
        service,
        password="",
    )

    result = runner.invoke(
        app,
        [
            "init",
        ],
    )

    assert result.exit_code == 1
    assert (
        "未配置管理员密码，请设置 "
        "DATAMIND_INIT_ADMIN_PASSWORD"
    ) in result.output
    service.initialize.assert_not_awaited()


def test_init_help_does_not_accept_credentials() -> None:
    """测试初始化命令不接收管理员凭据参数."""
    result = runner.invoke(
        app,
        [
            "init",
            "--help",
        ],
    )

    assert result.exit_code == 0
    assert "--username" not in result.output
    assert "--password-file" not in result.output


def test_init_skips_initialized_system(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试系统已初始化时跳过配置读取并正常退出."""
    init_logger = MagicMock()
    monkeypatch.setitem(vars(init_module), "logger", init_logger)
    service = create_service()
    service.is_initialized.return_value = True
    settings_loader = install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init",
        ],
    )

    assert result.exit_code == 0
    assert result.output.count("Datamind 已完成初始化，无需重复执行。") == 1
    init_logger.debug.assert_not_called()
    assert "Traceback" not in result.output
    assert "管理员密码" not in result.output
    service.initialize.assert_not_awaited()
    settings_loader.assert_not_called()


def test_init_handles_concurrent_initialization(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试预检查后其他进程完成初始化时正常退出."""
    service = create_service()
    service.initialize.side_effect = AlreadyInitializedError(
        "Datamind 已经完成初始化"
    )
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        ["init"],
    )

    assert result.exit_code == 0
    assert "Datamind 已完成初始化，无需重复执行。" in result.output
    service.initialize.assert_awaited_once()


def test_init_renders_clean_database_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库结构异常时输出简洁迁移提示."""
    service = create_service()
    service.is_initialized.side_effect = SQLAlchemyError(
        "relation systems does not exist"
    )
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init",
        ],
    )

    assert result.exit_code == 1
    assert "初始化失败：数据库操作失败" in result.output
    assert "relation systems does not exist" not in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("wrapper", ["direct", "cause", "orig"])
@pytest.mark.parametrize(
    ("error_type", "expected"),
    [
        (postgres_errors.InvalidPasswordError, "数据库认证失败"),
        (postgres_errors.ConnectionFailureError, "数据库连接失败"),
        (postgres_errors.UndefinedTableError, "datamind db upgrade"),
        (postgres_errors.UndefinedColumnError, "datamind db upgrade"),
        (postgres_errors.InvalidCatalogNameError, "数据库不存在"),
        (PostgresError, "数据库操作失败"),
        (ConnectionRefusedError, "数据库连接失败"),
        (TimeoutError, "数据库连接失败"),
    ],
)
def test_init_reports_database_failure_details(
        monkeypatch: pytest.MonkeyPatch,
        error_type: type[Exception],
        expected: str,
        wrapper: str,
) -> None:
    """测试数据库异常保留诊断字段并给出脱敏处理提示."""
    service = create_service()
    original = error_type("sensitive-password")
    if wrapper == "orig":
        error = DBAPIError(None, None, original)
    elif wrapper == "cause":
        error = SQLAlchemyError("sensitive-connection")
        error.__cause__ = original
    else:
        error = original

    service.is_initialized.side_effect = error
    install_service(monkeypatch, service)
    init_logger = MagicMock()
    monkeypatch.setitem(vars(init_module), "logger", init_logger)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert expected in result.output
    fields = init_logger.error.call_args.kwargs
    assert fields["error_type"] == type(error).__name__
    assert fields["database_error_type"] == error_type.__name__
    assert fields.get("sqlstate") == getattr(original, "sqlstate", None)
    assert "sensitive-" not in result.output
    assert "sensitive-" not in repr(init_logger.mock_calls)


@pytest.mark.parametrize(
    ("error", "level", "status", "exit_code"),
    [
        (ValueError("sensitive-password"), "error", "failed", 1),
        (SQLAlchemyError("sensitive-connection"), "error", "failed", 1),
        (ConnectionRefusedError("sensitive-address"), "error", "failed", 1),
    ],
)
def test_init_records_outcome_logs(
        monkeypatch: pytest.MonkeyPatch,
        error: Exception,
        level: str,
        status: str,
        exit_code: int,
) -> None:
    """测试失败日志携带请求标识且不暴露原始异常."""
    service = create_service()
    captured = {}

    async def check_state() -> bool:
        captured.update(get_context())
        raise error

    service.is_initialized.side_effect = check_state
    install_service(monkeypatch, service)
    init_logger = MagicMock()
    monkeypatch.setitem(vars(init_module), "logger", init_logger)
    previous = get_context().copy()

    result = runner.invoke(app, ["init"])

    assert result.exit_code == exit_code

    log = getattr(init_logger, level)
    log.assert_called_once()
    fields = log.call_args.kwargs
    assert fields["status"] == status
    assert fields["request_id"] == captured["request_id"]
    assert fields["trace_id"] == captured["trace_id"]
    assert fields["source"] == "cli"
    assert fields["user"] == "system:bootstrap"
    assert "sensitive-" not in repr(init_logger.mock_calls)
    assert get_context() == previous
    service.initialize.assert_not_awaited()
