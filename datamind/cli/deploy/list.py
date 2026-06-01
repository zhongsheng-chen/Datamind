import typer
import asyncio

from datamind.db.core import UnitOfWork
from datamind.db.repositories import DeploymentRepository

app = typer.Typer()


@app.command()
def list(
    model_id: str | None = typer.Option(None, "--model-id"),
    name: str | None = typer.Argument(None),
    environment: str | None = typer.Option(None, "--environment"),
    rollout: str | None = typer.Option(None, "--rollout"),
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(20, "--limit"),
    offset: int = typer.Option(0, "--offset"),
    format: str = typer.Option("table", "--format"),
    verbose: bool = False,
) -> None:
    """列出部署"""

    async def _run():
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployments = await repo.list_deployments(
                model_id=model_id,
                environment=environment,
                rollout_type=rollout,
                status=status,
                limit=limit,
                offset=offset,
            )

            typer.echo(deployments)

    asyncio.run(_run())