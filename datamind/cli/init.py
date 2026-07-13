# datamind/cli/init.py

"""系统初始化命令

提供首次部署时的一次性系统初始化功能。

核心功能：
  - initialize: 创建首个系统管理员

使用示例：
  python -m datamind.cli.main init
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from sqlalchemy.exc import SQLAlchemyError

from datamind.services.errors import InitializationError
from datamind.services.initialization import InitializationService
from datamind.utils import (
    get_host_ip,
    get_hostname,
)


console = Console()


def initialize(
        username: str | None = typer.Option(
            None,
            "--username",
            help="首个管理员用户名",
        ),
        password_file: Path | None = typer.Option(
            None,
            "--password-file",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
            help="从文件读取管理员密码",
        ),
) -> None:
    """一次性系统初始化"""
    async def runner() -> None:
        service = InitializationService()

        if await service.is_initialized():
            raise InitializationError(
                "Datamind 已经完成初始化"
            )

        resolved_username = (
            username
            or typer.prompt(
                "管理员用户名（默认：admin）",
                default="admin",
                show_default=False,
            )
        )
        password = (
            _read_password_file(
                password_file
            )
            if password_file is not None
            else typer.prompt(
                "管理员密码",
                hide_input=True,
            )
        )

        if password_file is None:
            confirmation = typer.prompt(
                "确认管理员密码",
                hide_input=True,
            )

            if password != confirmation:
                raise ValueError(
                    "两次输入的管理员密码不一致"
                )

        await service.initialize(
            username=resolved_username,
            password=password,
            ip=get_host_ip(),
            hostname=get_hostname(),
        )

        console.print(
            "[green]初始化完成[/green]"
        )

    try:
        asyncio.run(
            runner()
        )
    except (
        InitializationError,
        ValueError,
        OSError,
    ) as exc:
        console.print(
            f"[red]初始化失败：{exc}[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None
    except SQLAlchemyError:
        console.print(
            "[red]初始化失败：数据库操作失败，"
            "请检查数据库配置和迁移状态[/red]"
        )
        raise typer.Exit(
            code=1
        ) from None


def _read_password_file(
        path: Path,
) -> str:
    """读取单行密码文件"""
    password = path.read_text(
        encoding="utf-8"
    )

    if password.endswith(
            "\n"
    ):
        password = password[:-1]

    if password.endswith(
            "\r"
    ):
        password = password[:-1]

    if "\n" in password or "\r" in password:
        raise ValueError(
            "密码文件只能包含一行"
        )

    return password


__all__ = [
    "initialize",
]
