import typer
import asyncio

from datamind.services.deployer import ModelDeployer

app = typer.Typer()


@app.command()
def disable(
    deployment_id: str,
) -> None:
    """禁用部署"""

    async def _run():
        deployer = ModelDeployer()

        result = await deployer.disable_deployment(
            deployment_id=deployment_id,
        )

        typer.echo(result)

    asyncio.run(_run())