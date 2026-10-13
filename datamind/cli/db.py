"""数据库管理命令.

使用安装包内的 Alembic 迁移脚本执行数据库升级与降级。

核心功能：
  - upgrade: 将数据库升级到最新迁移版本
  - downgrade: 将数据库降级到指定迁移版本，默认要求确认

使用示例：
  python -m datamind.cli.main db upgrade
  python -m datamind.cli.main db downgrade --revision -1
  python -m datamind.cli.main db downgrade --revision base --yes
"""

import typer

from datamind.cli.output import CLIConsole
from datamind.db import migration


app = typer.Typer(help="数据库管理")
console = CLIConsole()


@app.command("upgrade")
def upgrade() -> None:
    """将数据库升级到最新迁移版本."""
    try:
        migration.upgrade_database()
    except migration.MigrationError as exc:
        console.error(str(exc))
        raise typer.Exit(code=1) from None

    console.info("数据库迁移完成")


@app.command("downgrade")
def downgrade(
    revision: str = typer.Option(
        ..., "--revision", "-r", help="降级目标版本",
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过降级确认"),
) -> None:
    """将数据库降级到指定迁移版本.

    指定迁移版本号可降级到对应版本，使用 -1 回退一步，使用 base 撤销全部迁移。

    注意：
        降级可能删除表或数据，执行前应完成备份。
    """
    if not yes:
        typer.confirm(
            f"数据库降级到 {revision} 可能删除表或数据，确认已备份并继续？",
            abort=True,
        )
    try:
        migration.downgrade_database(revision)
    except migration.MigrationError as exc:
        console.error(str(exc))
        raise typer.Exit(code=1) from None

    console.info("数据库降级完成")
