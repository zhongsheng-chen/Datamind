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
        logger.info(
            "Datamind 已完成初始化，无需重复执行",
            status="skipped",
            **log_context,
        )
        console.info(
            "Datamind 已完成初始化，无需重复执行。"
        )
    except (
        InitializationError,
        ValueError,
        OSError,
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
    except SQLAlchemyError:
        logger.error(
            "Datamind 初始化失败：数据库操作失败",
            status="failed",
            error_type="SQLAlchemyError",
            **log_context,
        )
        console.error(
            "初始化失败：数据库操作失败，"
            "请检查连接配置及迁移状态。"
        )
        raise typer.Exit(
            code=1
        ) from None


__all__ = [
    "initialize",
]
