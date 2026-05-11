# datamind/cli/model/show.py

"""查看模型详情命令

提供模型详情查询功能。

核心功能：
  - show_model: 查看模型详情

使用示例：
  python -m datamind.cli.main model show scorecard
  python -m datamind.cli.main model show --model-id mdl_a1b2c3d4
  python -m datamind.cli.main model show scorecard --format json
"""

import asyncio
import json

import typer

from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.readers import MetadataReader

app = typer.Typer(help="查看模型详情命令")
console = Console()


@app.command("show")
def show_model(
    name: str = typer.Argument(None, help="模型名称（与 --model-id 二选一）"),
    model_id: str = typer.Option(None, "--model-id", help="模型ID"),
    output: str = typer.Option("table", "--format", help="输出格式：table/json"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """查看模型详情"""
    async def _run():
        if not name and not model_id:
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        async with UnitOfWork() as uow:
            reader = MetadataReader(uow.session)

            # 优先按 ID 查询
            if model_id:
                model = await reader.get_model(model_id=model_id)

            # 按名称查询
            else:
                model = await reader.get_model(name=name)

            if not model:
                console.print("[yellow]模型不存在[/yellow]")
                raise typer.Exit(1)

            if output == "json":
                result = {
                    "model_id": model.model_id,
                    "name": model.name,
                    "status": model.status,
                    "framework": model.framework,
                    "model_type": model.model_type,
                    "task_type": model.task_type,
                    "description": model.description,
                    "created_by": model.created_by,
                    "created_at": model.created_at.isoformat() if model.created_at else None,
                    "updated_by": model.updated_by,
                    "updated_at": model.updated_at.isoformat() if model.updated_at else None,
                }

                console.print_json(json.dumps(result, ensure_ascii=False, indent=2))
                return

            table = Table(
                box=box.ASCII,
                show_header=False,
                show_lines=False,
                pad_edge=False,
            )

            table.add_column(style="cyan")
            table.add_column()

            table.add_row("NAME", model.name)
            table.add_row("MODEL ID", model.model_id)
            table.add_row("STATUS", model.status)
            table.add_row("FRAMEWORK", model.framework)
            table.add_row("MODEL TYPE", model.model_type)
            table.add_row("TASK TYPE", model.task_type)
            table.add_row("DESCRIPTION", model.description or "-")
            table.add_row("CREATED BY", model.created_by or "-")
            table.add_row("CREATED AT", model.created_at.strftime("%Y-%m-%d %H:%M:%S") if model.created_at else "-")
            table.add_row("UPDATED BY", model.updated_by or "-")
            table.add_row("UPDATED AT", model.updated_at.strftime("%Y-%m-%d %H:%M:%S") if model.updated_at else "-")

            console.print(table)

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())