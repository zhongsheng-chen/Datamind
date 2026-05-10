# datamind/cli/model.py

"""模型管理 CLI

提供模型的注册和查询功能。

核心功能：
  - register: 注册模型
  - list: 列出模型

使用示例：
  python -m datamind.cli.main model register \
      --name scorecard \
      --version 1.0.0 \
      --framework sklearn \
      --model-type logistic_regression \
      --task-type scoring \
      --model-path datamind/demo/scorecard.pkl \
      --description "信用评分卡模型" \
      --created-by admin
"""

import asyncio
import typer

from rich.console import Console
from rich.table import Table
from rich import box

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.readers import MetadataReader
from datamind.models.register import ModelRegister

app = typer.Typer(help="模型管理")

console = Console()


@app.command("register")
def register_model(
    name: str = typer.Option(..., "--name", help="模型名称"),
    version: str = typer.Option(..., "--version", help="模型版本"),
    framework: str = typer.Option(..., "--framework", help="模型框架"),
    model_type: str = typer.Option(..., "--model-type", help="模型类型"),
    task_type: str = typer.Option(..., "--task-type", help="任务类型"),
    model_path: str = typer.Option(..., "--model-path", help="模型文件路径"),
    description: str = typer.Option(None, "--description", help="模型描述"),
    created_by: str = typer.Option("system", "--created-by", help="创建人"),
    force: bool = typer.Option(False, "--force", help="强制覆盖已有版本"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """注册模型"""
    async def _run():
        register = ModelRegister()

        result = await register.register(
            name=name,
            version=version,
            framework=framework,
            model_type=model_type,
            task_type=task_type,
            model_path=model_path,
            description=description,
            created_by=created_by,
            force=force,
        )

        console.print("[green]模型注册成功[/green]\n")

        console.print(f"[cyan]{'MODEL ID':<12}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION':<12}[/cyan] : {result['version']}")
        console.print(f"[cyan]{'BENTO TAG':<12}[/cyan] : {result['bento_tag']}")
        console.print(f"[cyan]{'LOCATION':<12}[/cyan] : {result['storage_location']}")

    with cli_context(verbose=verbose):
        asyncio.run(_run())


@app.command("list")
def list_models(
    name: str = typer.Option(None, "--name", help="模型名称"),
    status: str = typer.Option(None, "--status", help="模型状态"),
    framework: str = typer.Option(None, "--framework", help="模型框架"),
    model_type: str = typer.Option(None, "--model-type", help="模型类型"),
    task_type: str = typer.Option(None, "--task-type", help="任务类型"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """列出模型"""
    async def _run():
        filters = {
            "name": name,
            "status": status,
            "framework": framework,
            "model_type": model_type,
            "task_type": task_type,
        }

        filters = {k: v for k, v in filters.items() if v is not None}

        async with UnitOfWork() as uow:
            reader = MetadataReader(uow.session)

            models = await reader.list_models(**filters)

            if not models:
                console.print("[yellow]暂无匹配模型[/yellow]")
                return

            console.print(f"[dim]共找到 {len(models)} 个模型[/dim]\n")

            table = Table(
                box=box.ASCII,
                header_style="bold cyan",
                show_lines=False,
                pad_edge=False,
            )

            table.add_column("MODEL ID")
            table.add_column("NAME")
            table.add_column("STATUS")
            table.add_column("FRAMEWORK")

            for model in models:
                table.add_row(
                    model.model_id,
                    model.name,
                    model.status,
                    model.framework,
                )

            console.print(table)

    with cli_context(verbose=verbose):
        asyncio.run(_run())