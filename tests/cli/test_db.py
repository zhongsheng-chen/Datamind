"""数据库升级命令测试."""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from datamind.cli.main import app
from datamind.db import migration as migration_module


@pytest.mark.parametrize("failed", [False, True])
def test_db_upgrade(monkeypatch: pytest.MonkeyPatch, failed: bool) -> None:
    """独立迁移命令报告成功或失败，并返回对应退出码."""
    migration = MagicMock(
        side_effect=migration_module.MigrationError("数据库迁移失败") if failed else None,
    )
    monkeypatch.setattr(migration_module, "upgrade_database", migration)

    result = CliRunner().invoke(app, ["db", "upgrade"])

    migration.assert_called_once_with()
    assert result.exit_code == (1 if failed else 0)
    assert ("数据库迁移失败" if failed else "数据库迁移完成") in result.output
    assert "Traceback" not in result.output
