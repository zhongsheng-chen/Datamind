# datamind/cli/model/list.py

"""列出模型命令

提供模型的列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_models: 列出模型

使用示例：
  python -m datamind.cli.main model list
  python -m datamind.cli.main model list --status active --framework sklearn
  python -m datamind.cli.main model list --format json --limit 10
  python -m datamind.cli.main model list --include-archived --verbose
"""

import asyncio
import json
import typer

from rich.console import Console
from rich.table import Table
from rich import box

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import MetadataRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="列出模型命令")
console = Console()


@app.command("list")
def list_models(
    status: str = typer.Option(None, "--status", help="状态"),
    framework: str = typer.Option(None, "--framework", help="框架类型"),
    model_type: str = typer.Option(None, "--model-type", help="模型类型"),
    task_type: str = typer.Option(None, "--task-type", help="任务类型"),
    owner: str = typer.Option(None, "--owner", help="创建人"),
    output: str = typer.Option("table", "--format", help="输出格式：table/json"),
    limit: int = typer.Option(10, "--limit", help="返回数量"),
    offset: int = typer.Option(0, "--offset", help="分页偏移"),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="包含已归档的模型"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """列出模型"""
    async def _run():
        filters = {
            "status": status,
            "framework": framework,
            "model_type": model_type,
            "task_type": task_type,
            "created_by": owner,
        }

        filters = {k: v for k, v in filters.items() if v is not None}

        # 默认隐藏 archived
        if not include_archived and "status" not in filters:
            filters["exclude_status"] = "archived"

        async with UnitOfWork() as uow:
            repo = MetadataRepository(uow.session)

            models = await repo.list_models(
                limit=limit,
                offset=offset,
                **filters
            )

            if output == "json":
                result = []

                for m in models:
                    result.append({
                        "model_id": m.model_id,
                        "name": m.name,
                        "status": m.status,
                        "framework": m.framework,
                        "model_type": m.model_type,
                        "task_type": m.task_type,
                        "created_by": m.created_by,
                        "created_at": format_iso_utc(m.created_at),
                        "updated_by": m.updated_by,
                        "updated_at": format_iso_utc(m.updated_at),
                    })

                console.print_json(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2
                    )
                )
                return

            console.print(f"[dim]共找到 {len(models)} 个模型[/dim]\n")

            if not models:
                return

            table = Table(
                box=box.ASCII,
                header_style="bold cyan",
                show_lines=False,
                pad_edge=False,
            )

            table.add_column("NAME")
            table.add_column("MODEL ID")
            table.add_column("STATUS")
            table.add_column("FRAMEWORK")
            table.add_column("UPDATED AT")

            for m in models:
                table.add_row(
                    m.name,
                    m.model_id,
                    m.status,
                    m.framework,
                    format_datetime(m.updated_at)
                )

            console.print(table)

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())