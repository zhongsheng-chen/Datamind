import typer
import asyncio

from datamind.services.deployer import ModelDeployer

app = typer.Typer()


@app.command()
def enable(
    deployment_id: str,
    verbose: bool = False,
) -> None:
    """启用部署"""

    async def _run():
        deployer = ModelDeployer()

        result = await deployer.enable_deployment(
            deployment_id=deployment_id,
        )

        typer.echo(result)

    asyncio.run(_run())