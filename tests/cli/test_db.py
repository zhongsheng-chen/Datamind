"""数据库迁移命令测试.

核心功能：
  - test_db_upgrade:
    验证升级命令报告执行结果并返回对应退出码
  - test_db_downgrade:
    验证降级命令报告执行结果并返回对应退出码
  - test_db_downgrade_confirmation:
    验证降级命令仅在用户确认后执行迁移
  - test_db_downgrade_requires_revision:
    验证降级命令缺少目标版本时不执行迁移
"""

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from datamind.cli.main import app
from datamind.db import migration as migration_module


@pytest.mark.parametrize("failed", [False, True])
def test_db_upgrade(monkeypatch: pytest.MonkeyPatch, failed: bool) -> None:
    """验证升级命令报告执行结果并返回对应退出码."""
    migration = MagicMock(
        side_effect=migration_module.MigrationError("数据库迁移失败") if failed else None,
    )
    monkeypatch.setattr(migration_module, "upgrade_database", migration)

    result = CliRunner().invoke(app, ["db", "upgrade"])

    migration.assert_called_once_with()
    assert result.exit_code == (1 if failed else 0)
    assert ("数据库迁移失败" if failed else "数据库迁移完成") in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("failed", [False, True])
def test_db_downgrade(monkeypatch: pytest.MonkeyPatch, failed: bool) -> None:
    """验证降级命令报告执行结果并返回对应退出码."""
    downgrade = MagicMock(
        side_effect=migration_module.MigrationError("数据库降级失败") if failed else None,
    )
    monkeypatch.setattr(migration_module, "downgrade_database", downgrade)
    result = CliRunner().invoke(app, ["db", "downgrade", "--revision", "-1", "--yes"])

    downgrade.assert_called_once_with("-1")
    assert result.exit_code == (1 if failed else 0)
    assert ("数据库降级失败" if failed else "数据库降级完成") in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("answer, accepted", [("n", False), ("y", True)])
def test_db_downgrade_confirmation(monkeypatch, answer, accepted) -> None:
    """验证降级命令仅在用户确认后执行迁移."""
    downgrade = MagicMock()
    monkeypatch.setattr(migration_module, "downgrade_database", downgrade)
    result = CliRunner().invoke(
        app, ["db", "downgrade", "--revision", "base"], input=f"{answer}\n",
    )
    assert "可能删除表或数据" in result.output
    assert result.exit_code == (0 if accepted else 1)
    assert downgrade.call_count == int(accepted)


def test_db_downgrade_requires_revision(monkeypatch) -> None:
    """验证降级命令缺少目标版本时不执行迁移."""
    downgrade = MagicMock()
    monkeypatch.setattr(migration_module, "downgrade_database", downgrade)
    result = CliRunner().invoke(app, ["db", "downgrade", "--yes"])
    assert result.exit_code == 2
    downgrade.assert_not_called()
