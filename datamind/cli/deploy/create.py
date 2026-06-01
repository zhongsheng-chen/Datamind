# datamind/cli/deploy/create.py

"""创建部署"""

import asyncio
import typer

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import DeploymentRepository
from datamind.services.deployer import ModelDeployer

app = typer.Typer()


@app.command()
def create(
    model_id: str | None = typer.Option(None, "--model-id"),
    name: str | None = typer.Argument(None),
    version_id: str | None = typer.Option(None, "--version-id"),
    version: str | None = typer.Option(None, "--version"),
    environment: str = typer.Option("production", "--environment"),
    rollout_type: str = typer.Option("full", "--rollout"),
    role: str = typer.Option("champion", "--role"),
    config: str | None = typer.Option(None, "--config"),
    description: str | None = typer.Option(None, "--description"),
    deployed_by: str | None = typer.Option(None, "--owner"),
) -> None:
    """创建部署"""

    async def _run():
        deployer = ModelDeployer()

        import json
        cfg = json.loads(config) if config else None

        result = await deployer.create_deployment(
            model_id=model_id,
            name=name,
            version_id=version_id,
            version=version,
            environment=environment,
            rollout_type=rollout_type,
            role=role,
            config=cfg,
            description=description,
            deployed_by=deployed_by,
        )

        typer.echo(result)

    asyncio.run(_run())