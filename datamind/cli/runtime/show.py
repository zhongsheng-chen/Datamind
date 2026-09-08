"""查看运行状态命令

提供指定部署的运行状态查询功能。

核心功能：
  - show_runtime: 查看部署运行状态

使用示例：
  python -m datamind.cli.main runtime show dep_0123456789abcdef
"""

import asyncio
import json
from typing import Any

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.models.errors import DeploymentError
from datamind.services import RuntimeControlService
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="查看运行状态命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_runtime(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """查看部署运行状态"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始查询部署运行状态",
            deployment_id=deployment_id,
        )

        controller = RuntimeControlService()

        raw_result = await controller.get_status(
            deployment_id=deployment_id,
        )

        deployment: dict[str, Any] = {
            **raw_result["deployment"],
        }

        for field in (
                "effective_from",
                "effective_to",
                "created_at",
                "updated_at",
        ):
            if field in deployment:
                deployment[field] = format_iso_utc(
                    parse_datetime(
                        deployment[field]
                    )
                )

        control: dict[str, Any] | None = raw_result[
            "control"
        ]

        if control is not None:
            control = {
                **control,
                "created_at": format_iso_utc(
                    parse_datetime(
                        control["created_at"]
                    )
                ),
                "updated_at": format_iso_utc(
                    parse_datetime(
                        control["updated_at"]
                    )
                ),
            }

        runtimes: list[dict[str, Any]] = [
            {
                **runtime,
                "loaded_at": format_iso_utc(
                    parse_datetime(
                        runtime["loaded_at"]
                    )
                ),
                "unloaded_at": format_iso_utc(
                    parse_datetime(
                        runtime["unloaded_at"]
                    )
                ),
                "last_heartbeat_at": format_iso_utc(
                    parse_datetime(
                        runtime["last_heartbeat_at"]
                    )
                ),
            }
            for runtime in raw_result["runtimes"]
        ]

        result: dict[str, Any] = {
            "deployment": deployment,
            "control": control,
            "runtimes": runtimes,
        }

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            return result

        console.info("运行状态详情\n")

        console.print(
            f"{'DEPLOYMENT ID':<18} : "
            f"{deployment['deployment_id']}"
        )
        console.print(
            f"{'MODEL ID':<18} : "
            f"{deployment['model_id']}"
        )
        console.print(
            f"{'VERSION ID':<18} : "
            f"{deployment['version_id']}"
        )
        console.print(
            f"{'FRAMEWORK':<18} : "
            f"{deployment['framework']}"
        )
        console.print(
            f"{'ENVIRONMENT':<18} : "
            f"{deployment['environment']}"
        )
        console.print(
            f"{'ROLLOUT TYPE':<18} : "
            f"{deployment['rollout_type']}"
        )
        console.print(
            f"{'ROLE':<18} : "
            f"{deployment['role']}"
        )
        console.print(
            f"{'STATUS':<18} : "
            f"{deployment['status']}"
        )

        console.print()

        if control is None:
            console.warning("暂无运行控制记录\n")

        else:
            console.print(
                f"{'CONTROL ID':<18} : "
                f"{control['control_id']}"
            )
            console.print(
                f"{'DESIRED STATUS':<18} : "
                f"{control['desired_status']}"
            )
            console.print(
                f"{'GENERATION':<18} : "
                f"{control['generation']}"
            )
            console.print(
                f"{'CREATED BY':<18} : "
                f"{control['created_by'] or '-'}"
            )
            console.print(
                f"{'CREATED AT':<18} : "
                f"{format_datetime(parse_datetime(control['created_at']))}"
            )
            console.print(
                f"{'UPDATED BY':<18} : "
                f"{control['updated_by'] or '-'}"
            )
            console.print(
                f"{'UPDATED AT':<18} : "
                f"{format_datetime(parse_datetime(control['updated_at']))}"
            )

            console.print()

        console.print(
            f"[dim]共找到 {len(runtimes)} 个 Worker 运行记录[/dim]\n"
        )

        if not runtimes:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("RUNTIME ID")
        table.add_column("WORKER ID")
        table.add_column("STATUS")
        table.add_column("LOADED AT")
        table.add_column("UNLOADED AT")
        table.add_column("HEARTBEAT")
        table.add_column("ERROR")

        for runtime in runtimes:
            table.add_row(
                str(runtime["runtime_id"]),
                str(runtime["worker_id"]),
                str(runtime["status"]),
                format_datetime(
                    parse_datetime(
                        runtime["loaded_at"]
                    )
                ),
                format_datetime(
                    parse_datetime(
                        runtime["unloaded_at"]
                    )
                ),
                format_datetime(
                    parse_datetime(
                        runtime["last_heartbeat_at"]
                    )
                ),
                str(runtime["error"] or "-"),
            )

        console.print(table)

        return result

    async def runner():
        async with cli_context(
                required_permission="runtime.read",
        ):
            try:
                await _run()
            except DeploymentError as error:
                logger.warning(
                    "部署运行状态查询失败",
                    deployment_id=deployment_id,
                    error=str(error),
                )
                console.error(
                    f"运行状态查询失败：{error}",
                    output_format=output,
                    error_type=type(error).__name__,
                )
                raise typer.Exit(code=1) from None

    asyncio.run(runner())
