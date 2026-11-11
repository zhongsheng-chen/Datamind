"""系统初始化命令.

初始化系统，创建首个管理员并授予系统管理员角色。

核心功能：
  - initialize: 创建首个系统管理员

使用示例：
  python -m datamind.cli.main init
"""

import asyncio

import structlog
import typer
from asyncpg import PostgresError
from sqlalchemy.exc import SQLAlchemyError

from datamind.cli.output import CLIConsole
from datamind.config import get_initialization_config
from datamind.audit.enums import AuditSource
from datamind.constants.identity import SYSTEM_BOOTSTRAP_ACTOR
from datamind.context import generate_trace_id
from datamind.context.scope import context_scope
from datamind.services.errors import (
    AlreadyInitializedError,
    InitializationError,
)
from datamind.services.initialization import InitializationService
from datamind.utils import (
    generate_random_id,
    get_host_ip,
    get_hostname,
)


console = CLIConsole()
logger = structlog.get_logger(__name__)


def initialize() -> None:
    """初始化系统，已初始化时跳过."""
    log_context = {
        "trace_id": generate_trace_id(),
        "request_id": generate_random_id(prefix="req"),
        "source": AuditSource.CLI,
        "user": SYSTEM_BOOTSTRAP_ACTOR,
        "action": "system.initialize",
        "target_type": "system",
        "target_id": "datamind",
    }

    async def runner() -> None:
        service = InitializationService()

        if await service.is_initialized():
            raise AlreadyInitializedError(
                "Datamind 已经完成初始化"
            )

        config = get_initialization_config()
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
        with context_scope(**log_context):
            asyncio.run(
                runner()
            )
    except AlreadyInitializedError:
        console.info(
            "Datamind 已完成初始化，无需重复执行。"
        )
    except (
        InitializationError,
        ValueError,
    ) as exc:
        logger.error(
            "Datamind 初始化失败",
            status="failed",
            error_type=type(exc).__name__,
            **log_context,
        )
        console.error(
            f"初始化失败：{exc}"
        )
        raise typer.Exit(
            code=1
        ) from None
    except (
        SQLAlchemyError,
        PostgresError,
        OSError,
    ) as exc:
        original: BaseException = exc
        seen: set[int] = set()
        sqlstate = None

        while id(original) not in seen:
            seen.add(id(original))
            state = getattr(original, "sqlstate", None)

            if isinstance(state, str):
                sqlstate = state

            nested = (
                getattr(original, "orig", None)
                or original.__cause__
            )

            if not isinstance(nested, BaseException):
                break

            original = nested

        if (
                sqlstate is not None
                and sqlstate.startswith("28")
        ):
            message = "数据库认证失败，请检查数据库用户名、密码及访问权限。"
        elif (
                isinstance(exc, OSError)
                or isinstance(original, OSError)
                or (
                    sqlstate is not None
                    and sqlstate.startswith("08")
                )
        ):
            message = "数据库连接失败，请检查数据库服务及连接地址。"
        elif sqlstate == "3D000":
            message = "数据库不存在，请检查数据库名称并先创建数据库。"
        elif sqlstate in {"42P01", "42703", "3F000"}:
            message = "数据库结构不完整，请先执行 datamind db upgrade。"
        else:
            message = "数据库操作失败，请检查连接配置及迁移状态。"

        logger.error(
            "Datamind 初始化失败：数据库操作失败",
            status="failed",
            error_type=type(exc).__name__,
            database_error_type=type(original).__name__,
            **(
                {"sqlstate": sqlstate}
                if sqlstate is not None
                else {}
            ),
            **log_context,
        )
        console.error(
            f"初始化失败：{message}"
        )
        raise typer.Exit(
            code=1
        ) from None


__all__ = [
    "initialize",
]
