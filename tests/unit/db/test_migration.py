"""安装包内迁移资源与错误处理测试."""

from io import StringIO
from pathlib import Path
import re
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config

import datamind.db.migration as migration


def test_migration_runs_from_any_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """在没有仓库配置的目录中使用真实迁移脚本生成 PostgreSQL DDL."""
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
    assert re.search(r"INSERT\s+INTO\s+alembic_version\b", sql)


def test_migration_hides_connection_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """连接异常被转为不包含密码的迁移错误."""
    monkeypatch.setattr(
        migration.command,
        "upgrade",
        Mock(side_effect=OSError("postgresql://user:secret-password@host/db")),
    )

    with pytest.raises(migration.MigrationError) as caught:
        migration.upgrade_database()

    assert "secret-password" not in str(caught.value)
    assert "数据库迁移失败" in str(caught.value)
