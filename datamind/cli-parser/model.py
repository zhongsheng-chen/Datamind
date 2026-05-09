# datamind/cli/model.py

"""模型 CLI"""

import asyncio

from datamind.context.scope import context_scope
from datamind.models.register import ModelRegister


def model_command(args):
    if args.action == "register":
        asyncio.run(_register_model())
    elif args.action == "list":
        asyncio.run(_list_model())
    elif args.action == "delete":
        asyncio.run(_delete_model())


# =========================
# register command
# =========================
async def _register_model():
    register = ModelRegister()

    with context_scope(
        user="cli",
        ip="127.0.0.1",
        trace_id="cli-trace",
        request_id="cli-req",
        source="cli",
    ):
        result = await register.register(
            name="scorecard",
            version="4.1.10",
            framework="sklearn",
            model_type="logistic_regression",
            task_type="scoring",
            model_path="datamind/demo/scorecard.pkl",
            description="CLI注册模型",
            created_by="cli",
            force=True,
        )

        print("模型注册成功：")
        print(result)


# =========================
# list command（占位）
# =========================
async def _list_model():
    print("TODO: list models")


# =========================
# delete command（占位）
# =========================
async def _delete_model():
    print("TODO: delete model")