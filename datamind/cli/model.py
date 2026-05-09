# datamind/cli/model.py

"""模型管理 CLI"""

import asyncio
import typer

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.readers import MetadataReader
from datamind.models.register import ModelRegister

app = typer.Typer(
    help="模型管理"
)


@app.command("register")
def register_model(
    name: str = typer.Option(..., "--name", help="模型名称"),
    version: str = typer.Option(..., "--version", help="模型版本"),
    framework: str = typer.Option(..., "--framework", help="模型框架"),
    model_type: str = typer.Option(..., "--model-type", help="模型类型"),
    task_type: str = typer.Option(..., "--task-type", help="任务类型"),
    model_path: str = typer.Option(..., "--model-path", help="模型文件路径"),
    description: str = typer.Option(
        None,
        "--description",
        help="模型描述",
    ),
    created_by: str = typer.Option(
        "system",
        "--created-by",
        help="创建人",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="强制覆盖已有版本",
    ),
):
    """注册模型"""

    async def _run():
        register = ModelRegister()

        result = await register.register(
            name=name,
            version=version,
            framework=framework,
            model_type=model_type,
            task_type=task_type,
            model_path=model_path,
            description=description,
            created_by=created_by,
            force=force,
        )

        print("模型注册成功：")
        print(f"模型ID: {result['model_id']}")
        print(f"版本号: {result['version']}")
        print(f"存储路径: {result['storage_key']}")
        print(f"Bento标签: {result['bento_tag']}")

    with cli_context():
        asyncio.run(_run())

@app.command("list")
def list_models(
    name: str = typer.Option(
        None,
        "--name",
        help="模型名称",
    ),
    status: str = typer.Option(
        None,
        "--status",
        help="模型状态",
    ),
    framework: str = typer.Option(
        None,
        "--framework",
        help="模型框架",
    ),
    model_type: str = typer.Option(
        None,
        "--model-type",
        help="模型类型",
    ),
    task_type: str = typer.Option(
        None,
        "--task-type",
        help="任务类型",
    ),
):
    """查询模型列表"""

    async def _run():
        filters = {
            "name": name,
            "status": status,
            "framework": framework,
            "model_type": model_type,
            "task_type": task_type,
        }

        filters = {
            key: value
            for key, value in filters.items()
            if value is not None
        }

        async with UnitOfWork() as uow:
            reader = MetadataReader(uow.session)

            models = await reader.list_models(
                **filters,
            )

            if not models:
                print("暂无模型")
                return

            print(
                f"{'MODEL ID':<20}"
                f"{'NAME':<20}"
                f"{'STATUS':<15}"
                f"{'FRAMEWORK':<15}"
            )

            for model in models:
                print(
                    f"{model.model_id:<20}"
                    f"{model.name:<20}"
                    f"{model.status:<15}"
                    f"{model.framework:<15}"
                )

    with cli_context():
        asyncio.run(_run())