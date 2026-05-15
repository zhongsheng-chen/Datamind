# datamind/cli/model/delete.py

"""删除模型命令

提供模型删除功能，支持软删除（归档）和硬删除（purge）。

核心功能：
  - delete_model: 删除模型

使用示例：
  python -m datamind.cli.main model delete scorecard
  python -m datamind.cli.main model delete scorecard --version 1.0.0
  python -m datamind.cli.main model delete scorecard --version 1.0.0 --purge
  python -m datamind.cli.main model delete --model-id mdl_a1b2c3d4
  python -m datamind.cli.main model delete scorecard --yes
"""

import asyncio
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.deleter import ModelDeleter

app = typer.Typer(help="删除模型命令")
console = Console()


@app.command("delete")
def delete_model(
    name: str = typer.Argument(None, help="模型名称（与 --model-id 二选一）"),
    model_id: str = typer.Option(None, "--model-id", help="模型 ID"),
    version: str = typer.Option(None, "--version", help="版本号（可选）"),
    version_id: str = typer.Option(None, "--version-id", help="版本 ID（可选）"),
    purge: bool = typer.Option(False, "--purge", help="是否执行硬删除"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """删除模型"""

    @audit(
        action="model.delete",
        target_type="model",
        target_id_func=lambda p, r: (
                r.get("version_id")
                if r.get("action") == "delete_version"
                else r.get("model_id")
        ),
    )
    async def _run():
        if not name and not model_id:
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        if not yes:
            if not typer.confirm("确认执行删除操作？"):
                raise typer.Exit(0)

        deleter = ModelDeleter()

        result = await deleter.delete(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            purge=purge,
        )

        if version:
            console.print(f"版本 {result['version']} 删除完成")
        else:
            console.print(f"模型 {result['name']} 删除完成")

        return result

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=True):
            await _run()

    asyncio.run(runner())