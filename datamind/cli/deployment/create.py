# datamind/cli/deployment/create.py

"""创建部署命令

提供模型部署创建功能。

核心功能：
  - create_deployment: 创建部署

使用示例：
  python -m datamind.cli.main deployment create scorecard \
    --version 1.0.0 \
    --environment production \
    --rollout full \
    --config-file config.json
"""

import asyncio
import json

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.services import DeploymentLifecycleService

app = typer.Typer(help="创建部署命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("create")
def create_deployment(
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
        environment: str | None = typer.Option(
            None,
            "--environment",
            help="部署环境，默认使用服务配置"
        ),
        rollout: str = typer.Option(
            "full",
            "--rollout",
            help="发布方式，可选值：full / canary / shadow"
        ),
        role: str = typer.Option(
            "champion",
            "--role",
            help="部署角色"
        ),
        config_file: str | None = typer.Option(
            None,
            "--config-file",
            help="运行时配置文件(JSON)"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="部署描述"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """创建部署"""
    settings = get_settings()
    service_config = settings.service

    resolved_environment = (
        environment
        if environment is not None
        else service_config.environment
    )

    @audit(
        action="deploy.create",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run(
            actor: str,
    ):
        if not (name or model_id):
            raise typer.BadParameter(
                "必须提供 <name> 或 --model-id"
            )

        if name and model_id:
            raise typer.BadParameter(
                "<name> 与 --model-id 只能指定一个"
            )

        if version and version_id:
            raise typer.BadParameter(
                "--version 与 --version-id 只能指定一个"
            )

        if not resolved_environment:
            raise typer.BadParameter(
                "--environment 不能为空"
            )

        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始创建部署",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            environment=resolved_environment,
            rollout=rollout,
            role=role,
            config_file=config_file,
        )

        cfg = None

        if config_file:
            logger.debug(
                "读取部署配置文件",
                config_file=config_file,
            )

            try:
                with open(
                        config_file,
                        "r",
                        encoding="utf-8",
                ) as f:
                    cfg = json.load(f)

                logger.debug(
                    "部署配置文件解析成功",
                    config=cfg,
                )

            except FileNotFoundError:
                console.print(
                    "[red]配置文件不存在: "
                    f"{config_file}[/red]"
                )
                raise typer.Exit(1)

            except json.JSONDecodeError as exc:
                console.print(
                    "[red]config-file JSON 解析失败: "
                    f"{exc}[/red]"
                )
                raise typer.Exit(1)

            if not isinstance(
                    cfg,
                    dict,
            ):
                raise typer.BadParameter(
                    "--config-file 必须是 JSON 对象"
                )

        deployer = DeploymentLifecycleService()

        result = await deployer.create_deployment(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            environment=resolved_environment,
            rollout_type=rollout,
            role=role,
            config=cfg,
            description=description,
            deployed_by=actor,
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

        console.print(
            "[green]部署创建成功[/green]\n"
        )

        console.print(
            f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : "
            f"{result['deployment_id']}"
        )
        console.print(
            f"[cyan]{'MODEL ID':<16}[/cyan] : "
            f"{result['model_id']}"
        )
        console.print(
            f"[cyan]{'VERSION ID':<16}[/cyan] : "
            f"{result['version_id']}"
        )
        console.print(
            f"[cyan]{'ENVIRONMENT':<16}[/cyan] : "
            f"{result['environment']}"
        )
        console.print(
            f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : "
            f"{result['rollout_type']}"
        )
        console.print(
            f"[cyan]{'ROLE':<16}[/cyan] : "
            f"{result['role']}"
        )
        console.print(
            f"[cyan]{'STATUS':<16}[/cyan] : "
            f"{result['status']}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
