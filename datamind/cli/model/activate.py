# datamind/cli/model/activate.py

"""激活模型命令

提供模型和模型版本激活功能。

核心功能：
  - activate_model: 激活模型或模型版本

使用示例：
  python -m datamind.cli.main model activate scorecard \
    --version 1.0.0 \
    --operator admin
"""

import asyncio
import json
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services.lifecycle import ModelLifecycle

app = typer.Typer(help="激活模型命令")
console = Console()


@app.command("activate")
def activate_model(
    name: str | None = typer.Argument(
        None,
        help="模型名称"
    ),
    model_id: str | None = typer.Option(
        None,
        "--model-id",
        help="模型 ID"
    ),
    version: str | None = typer.Option(
        None,
        "--version",
        help="模型版本号"
    ),
    version_id: str | None = typer.Option(
        None,
        "--version-id",
        help="版本 ID"
    ),
    operator: str = typer.Option(
        "system",
        "--operator",
        help="操作人"
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
    """激活模型或模型版本"""

    @audit(
        action="model.activate",
        target_type="model",
        target_id_func=lambda p, r: r["model_id"],
    )
    async def _run():
        if not (name or model_id):
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        if name and model_id:
            raise typer.BadParameter("<name> 与 --model-id 只能指定一个")

        if version and version_id:
            raise typer.BadParameter("--version 与 --version-id 只能指定一个")

        lifecycle = ModelLifecycle()

        result = await lifecycle.activate(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            updated_by=operator,
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

        console.print("[green]模型激活成功[/green]\n")

        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name']}")
        console.print(f"[cyan]{'MODEL STATUS':<16}[/cyan] : {result['model_status']}")

        if result.get("version_id"):
            console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {result['version_id']}")
            console.print(f"[cyan]{'VERSION':<16}[/cyan] : {result['version']}")
            console.print(f"[cyan]{'VERSION STATUS':<16}[/cyan] : {result['version_status']}")

        return result

    async def runner():
        async with cli_context(
                user=operator,
                source="cli",
                verbose=verbose,
                enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())