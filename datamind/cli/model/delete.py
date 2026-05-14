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

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import MetadataRepository
from datamind.db.models import Metadata, Version

from sqlalchemy import delete as sa_delete, update

app = typer.Typer(help="删除模型命令")


@app.command("delete")
def delete_model(
    name: str = typer.Argument(None, help="模型名称（与 --model-id 二选一）"),
    model_id: str = typer.Option(None, "--model-id", help="模型ID"),
    version: str = typer.Option(None, "--version", help="版本号（可选）"),
    purge: bool = typer.Option(False, "--purge", help="是否执行硬删除"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """删除模型"""

    async def _run():

        if not name and not model_id:
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        if not yes:
            if not typer.confirm("确认执行删除操作？"):
                raise typer.Exit(0)

        async with UnitOfWork() as uow:
            repo = MetadataRepository(uow.session)

            # 优先按 ID 查询
            if model_id:
                model = await repo.get_model(model_id=model_id)

            # 按名称查询
            else:
                model = await repo.get_model(name=name)

            if not model:
                typer.echo("模型不存在")
                raise typer.Exit(1)

            if version:

                if purge:
                    await uow.session.execute(
                        sa_delete(Version).where(
                            Version.model_id == model.model_id,
                            Version.version == version,
                        )
                    )
                else:
                    await uow.session.execute(
                        update(Version)
                        .where(
                            Version.model_id == model.model_id,
                            Version.version == version,
                        )
                        .values(status="archived")
                    )

                typer.echo(f"版本 {version} 删除完成")
                return

            if purge:

                await uow.session.execute(
                    sa_delete(Version).where(
                        Version.model_id == model.model_id
                    )
                )

                await uow.session.execute(
                    sa_delete(Metadata).where(
                        Metadata.model_id == model.model_id
                    )
                )

                typer.echo(f"模型 {model.name} 已硬删除")
                return

            await uow.session.execute(
                update(Metadata)
                .where(Metadata.model_id == model.model_id)
                .values(status="archived")
            )

            typer.echo(f"模型 {model.name} 已归档")

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())