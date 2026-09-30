"""使用安装包内的 Alembic 脚本升级数据库."""

from pathlib import Path

from alembic import command
from alembic.config import Config


class MigrationError(Exception):
    """数据库迁移失败."""


def upgrade_database() -> None:
    """将数据库升级到当前安装包的最新版本.

    配置由迁移环境读取，无需工作目录中的 alembic.ini。
    """
    config = Config()
    config.set_main_option(
        "script_location",
        str(Path(__file__).parent / "migrations").replace("%", "%%"),
    )
    try:
        command.upgrade(config, "head")
    except Exception as exc:
        # 连接异常可能含凭据，不将原始异常交给 CLI 输出。
        raise MigrationError(
            "数据库迁移失败，请检查数据库配置、连接和迁移状态"
        ) from exc
