import typer
import asyncio

from datamind.db.core import UnitOfWork
from datamind.db.repositories import DeploymentRepository

app = typer.Typer()


@app.command()
def show(
    deployment_id: str,
    verbose: bool = False,
) -> None:
    """查看部署详情"""

    async def _run():
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(deployment_id)

            if not deployment:
                typer.echo(f"部署不存在: {deployment_id}")
                return

            typer.echo(deployment)

    asyncio.run(_run())