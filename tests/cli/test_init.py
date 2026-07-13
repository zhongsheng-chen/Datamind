# tests/cli/test_init.py

"""系统初始化 CLI 测试

验证交互式密码、密码文件、成功输出和简洁错误处理。

核心功能：
  - test_init_rejects_initialized_system_before_prompt:
    验证系统已初始化时不读取管理员凭据
  - test_init_prompts_for_credentials: 验证交互式初始化
  - test_init_rejects_password_confirmation_mismatch:
    验证两次密码输入必须一致
  - test_init_reads_password_file: 验证从单行文件读取密码
  - test_init_rejects_multiline_password_file: 验证拒绝多行密码文件
  - test_init_renders_clean_error: 验证初始化失败不显示 traceback
"""

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError
from typer.testing import CliRunner

import datamind.cli.init as init_module
from datamind.cli.main import app
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
) -> None:
    """替换系统初始化服务和主机信息"""
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


def create_service() -> AsyncMock:
    """创建成功的系统初始化服务替身"""
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


def test_init_prompts_for_credentials(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证交互式初始化并隐藏密码"""
    service = create_service()
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init"
        ],
        input="\nsecret\nsecret\n",
    )

    assert result.exit_code == 0
    assert "初始化完成" in result.output
    assert "Datamind 初始化完成" not in result.output
    assert "管理员用户名（默认：admin）:" in result.output
    assert result.output.count(
        "管理员用户名"
    ) == 1
    assert "[admin]" not in result.output
    assert "初始化时间" not in result.output
    assert "2026-08-02 16:30:00" not in result.output
    assert "secret" not in result.output
    assert result.output.count(
        "管理员密码:"
    ) == 2
    service.initialize.assert_awaited_once_with(
        username="admin",
        password="secret",
        ip="10.0.0.10",
        hostname="datamind-host",
    )


def test_init_rejects_password_confirmation_mismatch(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证两次密码输入必须一致"""
    service = create_service()
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init",
            "--username",
            "admin",
        ],
        input="first-secret\nsecond-secret\n",
    )

    assert result.exit_code == 1
    assert "两次输入的管理员密码不一致" in result.output
    service.initialize.assert_not_awaited()


def test_init_reads_password_file(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """验证从单行文件读取管理员密码"""
    password_file = tmp_path / "initial-admin-password"
    password_file.write_text(
        "file-secret\n",
        encoding="utf-8",
    )
    service = create_service()
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init",
            "--username",
            "admin",
            "--password-file",
            str(password_file),
        ],
    )

    assert result.exit_code == 0
    assert "file-secret" not in result.output
    service.initialize.assert_awaited_once_with(
        username="admin",
        password="file-secret",
        ip="10.0.0.10",
        hostname="datamind-host",
    )


def test_init_rejects_multiline_password_file(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """验证拒绝包含多行内容的密码文件"""
    password_file = tmp_path / "initial-admin-password"
    password_file.write_text(
        "first\nsecond\n",
        encoding="utf-8",
    )
    install_service(
        monkeypatch,
        create_service(),
    )

    result = runner.invoke(
        app,
        [
            "init",
            "--username",
            "admin",
            "--password-file",
            str(password_file),
        ],
    )

    assert result.exit_code == 1
    assert "密码文件只能包含一行" in result.output
    assert "Traceback" not in result.output


def test_init_renders_clean_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证系统已初始化时输出简洁错误"""
    service = create_service()
    service.is_initialized.return_value = True
    install_service(
        monkeypatch,
        service,
    )

    result = runner.invoke(
        app,
        [
            "init",
            "--username",
            "admin",
        ],
    )

    assert result.exit_code == 1
    assert "初始化失败：Datamind 已经完成初始化" in result.output
    assert "Traceback" not in result.output
    assert "管理员密码" not in result.output
    service.initialize.assert_not_awaited()


def test_init_renders_clean_database_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证数据库结构异常时输出简洁迁移提示"""
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
            "--username",
            "admin",
        ],
    )

    assert result.exit_code == 1
    assert (
        "初始化失败：数据库操作失败，"
        "请检查数据库配置和迁移状态"
    ) in result.output
    assert "relation systems does not exist" not in result.output
    assert "Traceback" not in result.output
