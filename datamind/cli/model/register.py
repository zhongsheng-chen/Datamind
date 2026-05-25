# datamind/cli/model/register.py

"""注册模型命令

提供模型注册功能。

核心功能：
  - register_model: 注册模型

使用示例：
  python -m datamind.cli.main model register scorecard \
    --version 1.0.0 \
    --model-path ./models/scorecard.pkl \
    --framework sklearn \
    --model-type logistic_regression \
    --task-type scoring \
    --owner admin
"""

import asyncio
import json
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.register import ModelRegister

app = typer.Typer(help="注册模型命令")
console = Console()


@app.command("register")
def register_model(
    name: str = typer.Argument(..., help="模型名称"),
    version: str = typer.Option(..., "--version", help="模型版本"),
    model_path: str = typer.Option(..., "--model-path", help="模型文件路径"),
    framework: str = typer.Option(..., "--framework", help="模型框架"),
    model_type: str = typer.Option(..., "--model-type", help="模型类型"),
    task_type: str = typer.Option(..., "--task-type", help="任务类型"),
    description: str = typer.Option(None, "--description", help="模型描述"),
    owner: str = typer.Option(None, "--owner", help="创建人"),
    force: bool = typer.Option(False, "--force", help="强制覆盖已有版本"),
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
    """注册模型"""

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=lambda p, r: r["model_id"],
    )
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
            created_by=owner,
            force=force,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.print("[green]模型注册成功[/green]\n")

        console.print(f"[cyan]{'MODEL ID':<12}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<12}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'NAME':<12}[/cyan] : {result['name']}")
        console.print(f"[cyan]{'VERSION':<12}[/cyan] : {result['version']}")
        console.print(f"[cyan]{'BENTO TAG':<12}[/cyan] : {result['bento_tag']}")
        console.print(f"[cyan]{'MODEL PATH':<12}[/cyan] : {result['model_path']}")

        return result

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=True):
            await _run()

    asyncio.run(runner())