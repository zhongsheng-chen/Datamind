# datamind/cli/service/reload.py

"""重新加载服务命令

提供部署模型重新加载请求功能。

核心功能：
  - reload_service: 请求重新加载部署模型

使用示例：
  python -m datamind.cli.main service reload dep_0123456789abcdef
"""

import asyncio
import json
from typing import Any

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services import RuntimeControlService
from datamind.utils.datetime import format_iso_utc, parse_datetime

app = typer.Typer(help="重新加载服务命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("reload")
def reload_service(
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
    """请求重新加载部署模型"""

    @audit(
        action="service.reload",
        target_type="deployment",
        target_id_from="target_deployment_id",
    )
    async def _run(
            *,
            target_deployment_id: str,
            actor: str,
    ):
        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始提交模型重新加载请求",
            deployment_id=target_deployment_id,
        )

        controller = RuntimeControlService()

        raw_result = await controller.reload(
            deployment_id=target_deployment_id,
            operator=actor,
        )

        control: dict[str, Any] = {
            **raw_result["control"],
        }

        for field in (
                "created_at",
                "updated_at",
        ):
            if field in control:
                control[field] = format_iso_utc(
                    parse_datetime(
                        control[field]
                    )
                )

        result: dict[str, Any] = {
            **raw_result,
            "control": control,
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

        console.print(
            "[green]模型重新加载请求提交成功[/green]\n"
        )

        console.print(
            f"[cyan]{'CONTROL ID':<18}[/cyan] : "
            f"{control['control_id']}"
        )
        console.print(
            f"[cyan]{'DEPLOYMENT ID':<18}[/cyan] : "
            f"{control['deployment_id']}"
        )
        console.print(
            f"[cyan]{'DESIRED STATUS':<18}[/cyan] : "
            f"{control['desired_status']}"
        )
        console.print(
            f"[cyan]{'GENERATION':<18}[/cyan] : "
            f"{control['generation']}"
        )
        console.print(
            f"[cyan]{'ACCEPTED':<18}[/cyan] : "
            f"{result['accepted']}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="runtime.manage",
        ) as context:
            await _run(
                target_deployment_id=deployment_id,
                actor=context.user,
            )

    asyncio.run(runner())
