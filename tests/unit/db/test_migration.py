"""安装包内迁移资源与错误处理测试.

核心功能：
  - test_upgrade_runs_from_any_directory:
    验证在任意工作目录中使用安装包内的迁移脚本生成升级 SQL
  - test_migration_hides_connection_secrets:
    验证升级失败时错误消息不暴露数据库凭据
  - test_downgrade_runs_from_any_directory:
    验证在任意工作目录中使用安装包内的迁移脚本生成降级 SQL
  - test_downgrade_hides_connection_secrets:
    验证降级失败时错误消息不暴露数据库凭据
"""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config

import datamind.db.migration as migration


def test_upgrade_runs_from_any_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """验证在任意工作目录中使用安装包内的迁移脚本生成升级 SQL."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL", "postgresql+asyncpg://user:p%25ss@localhost/db",
    )
    output = StringIO()
    upgrade = command.upgrade

    def offline_upgrade(config: Config, revision: str) -> None:
        config.output_buffer = output
        upgrade(config, revision, sql=True)

    monkeypatch.setattr(migration.command, "upgrade", offline_upgrade)
    migration.upgrade_database()

    sql = output.getvalue()
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE systems" in sql


def test_migration_hides_connection_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证升级失败时错误消息不暴露数据库凭据."""
    monkeypatch.setattr(
        migration.command,
        "upgrade",
        Mock(side_effect=OSError("postgresql://user:secret-password@host/db")),
    )

    with pytest.raises(migration.MigrationError) as caught:
        migration.upgrade_database()

    assert "secret-password" not in str(caught.value)
    assert "数据库迁移失败" in str(caught.value)


def test_downgrade_runs_from_any_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """验证在任意工作目录中使用安装包内的迁移脚本生成降级 SQL."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATAMIND_DATABASE_URL", "postgresql+asyncpg://user:p%25ss@localhost/db",
    )
    output = StringIO()
    downgrade = command.downgrade

    def offline_downgrade(config: Config, revision: str) -> None:
        config.output_buffer = output
        downgrade(config, f"head:{revision}", sql=True)

    monkeypatch.setattr(migration.command, "downgrade", offline_downgrade)
    migration.downgrade_database("base")

    sql = output.getvalue()
    assert "DROP TABLE users" in sql
    assert "DROP TABLE systems" in sql


def test_downgrade_hides_connection_secrets(monkeypatch) -> None:
    """验证降级失败时错误消息不暴露数据库凭据."""
    monkeypatch.setattr(
        migration.command, "downgrade",
        Mock(side_effect=OSError("postgresql://user:secret-password@host/db")),
    )
    with pytest.raises(migration.MigrationError) as caught:
        migration.downgrade_database("-1")
    assert "secret-password" not in str(caught.value)
    assert "数据库降级失败" in str(caught.value)
