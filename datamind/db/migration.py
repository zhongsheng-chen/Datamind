"""数据库迁移.

使用安装包内的 Alembic 迁移脚本执行数据库升级与降级。

核心功能：
  - upgrade_database: 将数据库升级到最新迁移版本
  - downgrade_database: 将数据库降级到指定迁移版本

使用示例：
  upgrade_database()
  downgrade_database("-1")
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


class MigrationError(Exception):
    """数据库迁移失败."""


def _migration_config() -> Config:
    """创建数据库迁移配置."""
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).parent / "migrations").replace("%", "%%"),
    )
    return config


def upgrade_database() -> None:
    """将数据库升级到最新迁移版本."""
    config = _migration_config()
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        # 连接异常可能含凭据，不将原始异常交给 CLI 输出。
        raise MigrationError(
            "数据库迁移失败，请检查数据库配置、连接和迁移状态"
        ) from exc


def downgrade_database(revision: str) -> None:
    """将数据库降级到指定迁移版本."""
    config = _migration_config()
    try:
        command.downgrade(config, revision)
    except Exception as exc:
        # 连接异常可能含凭据，不将原始异常交给 CLI 输出。
        raise MigrationError(
            "数据库降级失败，请检查数据库配置、连接和目标迁移版本"
        ) from exc
