# datamind/cli/model.py

"""模型管理 CLI

提供模型的注册和查询功能。

核心功能：
  - register: 注册模型
  - list: 列出模型

使用示例：
  # 注册模型
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

from datamind.audit import audit
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

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=lambda p, r: r["model_id"],
    )
    async def _run():
        register = ModelRegister()

        return await register.register(
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

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=True):
            return await _run()

    result = asyncio.run(runner())

    console.print("\n[green]模型注册成功[/green]\n")
    console.print(f"[cyan]{'MODEL ID':<12}[/cyan] : {result['model_id']}")
    console.print(f"[cyan]{'VERSION':<12}[/cyan] : {result['version']}")
    console.print(f"[cyan]{'BENTO TAG':<12}[/cyan] : {result['bento_tag']}")
    console.print(f"[cyan]{'MODEL PATH':<12}[/cyan] : {result['model_path']}")


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

            # 默认排序
            models = sorted(
                models,
                key=lambda x: x.updated_at or x.created_at,
                reverse=True
            )

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
            table.add_column("TASK TYPE")
            table.add_column("CREATED AT")
            table.add_column("UPDATED AT")

            for m in models:
                table.add_row(
                    m.model_id,
                    m.name,
                    m.status,
                    m.framework,
                    m.task_type,
                    m.created_at.strftime("%Y-%m-%d %H:%M:%S") if m.created_at else "-",
                    m.updated_at.strftime("%Y-%m-%d %H:%M:%S") if m.updated_at else "-",
                )

            console.print(table)

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            return await _run()

    asyncio.run(runner())

# @app.command("delete")
# def delete_model(
#     model_id: str = typer.Option(..., "--model-id", help="模型ID"),
#     version: str = typer.Option(None, "--version", help="版本号（可选）"),
#     force: bool = typer.Option(False, "--force", help="强制删除"),
#     verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
# ):
#     """删除模型（带审计）"""
#
#     # =========================
#     # audit（删除操作）
#     # =========================
#     @audit(
#         action="model.delete",
#         target_type="model",
#         target_id_func=lambda p, r: p["model_id"],
#     )
#     async def _run():
#         from datamind.models.deleter import ModelDeleter
#
#         deleter = ModelDeleter()
#
#         return await deleter.delete(
#             model_id=model_id,
#             version=version,
#             force=force,
#         )
#
#     # =========================
#     # CLI runtime
#     # =========================
#     async def runner():
#         async with cli_context(verbose=verbose, enable_audit=True):
#             return await _run()
#
#     result = asyncio.run(runner())
#
#     # =========================
#     # 输出
#     # =========================
#     console.print("\n[red]模型删除成功[/red]\n")
#     console.print(f"[cyan]{'MODEL ID':<12}[/cyan] : {result['model_id']}")
#     console.print(f"[cyan]{'STATUS':<12}[/cyan] : {result.get('status', 'deleted')}")
#
#     if version:
#         console.print(f"[cyan]{'VERSION':<12}[/cyan] : {version}")
# ####
# @app.command("delete")
# def delete_model(
#     model_id: str = typer.Option(..., "--model-id", help="模型ID"),
#     version: str = typer.Option(None, "--version", help="版本（不填则删除全部）"),
#     verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
# ):
#     """删除模型（hard delete）"""
#
#     from datamind.models.deleter import ModelDeleter
#
#     async def _run():
#         deleter = ModelDeleter()
#         return await deleter.delete_model(model_id, version=version)
#
#     async def runner():
#         async with cli_context(verbose=verbose):
#             return await _run()
#
#     result = asyncio.run(runner())
#
#     if result.get("deleted"):
#         console.print("[green]模型删除成功[/green]")
#     else:
#         console.print("[yellow]删除失败或不存在[/yellow]")