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
    --config-file config.json \
    --owner admin
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services.deployer import ModelDeployer

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
    environment: str = typer.Option(
        "production",
        "--environment",
        help="部署环境"
    ),
    rollout: str = typer.Option(
        "full",
        "--rollout",
        help="发布方式 full canary shadow"
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
    owner: str = typer.Option(
        "system",
        "--owner",
        help="创建人"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="是否输出调试日志"
    ),
):
    """创建部署"""

    @audit(
        action="deploy.create",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run():
        if not (name or model_id):
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        if name and model_id:
            raise typer.BadParameter("<name> 与 --model-id 只能指定一个")

        if version and version_id:
            raise typer.BadParameter("--version 与 --version-id 只能指定一个")

        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始创建部署",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            environment=environment,
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
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                logger.debug(
                    "部署配置文件解析成功",
                    config=cfg,
                )

            except FileNotFoundError:
                console.print(f"[red]配置文件不存在: {config_file}[/red]")
                raise typer.Exit(1)

            except json.JSONDecodeError as e:
                console.print(f"[red]config-file JSON 解析失败: {e}[/red]")
                raise typer.Exit(1)

        deployer = ModelDeployer()

        result = await deployer.create_deployment(
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            environment=environment,
            rollout_type=rollout,
            role=role,
            config=cfg,
            description=description,
            deployed_by=owner,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2
                )
            )
            return result

        console.print("[green]部署创建成功[/green]\n")

        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'VERSION ID':<16}[/cyan] : {result['version_id']}")
        console.print(f"[cyan]{'ENVIRONMENT':<16}[/cyan] : {result['environment']}")
        console.print(f"[cyan]{'ROLLOUT TYPE':<16}[/cyan] : {result['rollout_type']}")
        console.print(f"[cyan]{'ROLE':<16}[/cyan] : {result['role']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
            user=owner,
            source="cli",
            verbose=verbose,
            enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())