# datamind/cli/init.py

"""系统初始化命令

提供首次部署时的一次性系统初始化功能。

核心功能：
  - initialize: 创建首个系统管理员

使用示例：
  python -m datamind.cli.main init
"""

import asyncio

import typer
from sqlalchemy.exc import SQLAlchemyError

from datamind.cli.output import CLIConsole
from datamind.config import get_settings
from datamind.services.errors import InitializationError
from datamind.services.initialization import InitializationService
from datamind.utils import (
    get_host_ip,
    get_hostname,
)


console = CLIConsole()


def initialize() -> None:
    """一次性系统初始化"""
    async def runner() -> None:
        service = InitializationService()

        if await service.is_initialized():
            raise InitializationError(
                "Datamind 已经完成初始化"
            )

        config = get_settings().initialization
        password = (
            config.admin_password.get_secret_value()
        )

        if not password:
            raise InitializationError(
                "未配置管理员密码，请设置 "
                "DATAMIND_INIT_ADMIN_PASSWORD"
            )

        await service.initialize(
            username=config.admin_username,
            password=password,
            ip=get_host_ip(),
            hostname=get_hostname(),
        )

        console.info("初始化完成")

    try:
        asyncio.run(
            runner()
        )
    except (
        InitializationError,
        ValueError,
        OSError,
    ) as exc:
        console.error(
            f"初始化失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
    except SQLAlchemyError:
        console.error(
            "初始化失败：数据库操作失败，"
            "请检查数据库配置和迁移状态"
        )
        raise typer.Exit(
            code=1
        ) from None


__all__ = [
    "initialize",
]
