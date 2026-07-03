# datamind/cli/service/list.py

"""列出服务命令

提供模型运行时服务列表查询功能。

核心功能：
  - list_services: 查看运行时服务列表

使用示例：
  python -m datamind.cli.main service list
"""

import asyncio
import json
import typer
import structlog
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import RuntimeRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="列出服务命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_services(
    deployment_id: str | None = typer.Option(
        None,
        "--deployment-id",
        help="按部署 ID 过滤"
    ),
    model_id: str | None = typer.Option(
        None,
        "--model-id",
        help="按模型 ID 过滤"
    ),
    version_id: str | None = typer.Option(
        None,
        "--version-id",
        help="按版本 ID 过滤"
    ),
    framework: str | None = typer.Option(
        None,
        "--framework",
        help="按模型框架过滤"
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        help="按运行状态过滤，例如 loading/loaded/unloaded/failed"
    ),
    worker_id: str | None = typer.Option(
        None,
        "--worker-id",
        help="按 Worker 标识过滤"
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        help="返回记录数量限制"
    ),
    offset: int = typer.Option(
        0,
        "--offset",
        help="分页偏移量"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示调试日志"
    ),
):
    """列出服务"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {}

        if deployment_id is not None:
            filters["deployment_id"] = deployment_id

        if model_id is not None:
            filters["model_id"] = model_id

        if version_id is not None:
            filters["version_id"] = version_id

        if framework is not None:
            filters["framework"] = framework

        if status is not None:
            filters["status"] = status

        if worker_id is not None:
            filters["worker_id"] = worker_id

        logger.info(
            "开始列出模型服务",
            filters=filters,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = RuntimeRepository(uow.session)

            runtimes = await repo.list_runtimes(
                limit=limit,
                offset=offset,
                **filters,
            )

        result = [
            {
                "runtime_id": item.runtime_id,
                "deployment_id": item.deployment_id,
                "model_id": item.model_id,
                "version_id": item.version_id,
                "framework": item.framework,
                "status": item.status,
                "worker_id": item.worker_id,
                "loaded_at": format_iso_utc(item.loaded_at),
                "unloaded_at": format_iso_utc(item.unloaded_at),
                "started_by": item.started_by,
                "stopped_by": item.stopped_by,
                "last_heartbeat_at": format_iso_utc(item.last_heartbeat_at),
                "error": item.error,
                "context": item.context,
                "created_at": format_iso_utc(item.created_at),
                "updated_at": format_iso_utc(item.updated_at),
            }
            for item in runtimes
        ]

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return result

        console.print(f"[dim]共找到 {len(runtimes)} 个服务记录[/dim]\n")

        if not runtimes:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("RUNTIME ID")
        table.add_column("DEPLOYMENT ID")
        table.add_column("MODEL ID")
        table.add_column("VERSION ID")
        table.add_column("FRAMEWORK")
        table.add_column("STATUS")
        table.add_column("WORKER")
        table.add_column("UPDATED AT")

        for item in runtimes:
            table.add_row(
                item.runtime_id,
                item.deployment_id,
                item.model_id,
                item.version_id,
                item.framework,
                item.status,
                item.worker_id,
                format_datetime(item.updated_at),
            )

        console.print(table)

        return result

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())