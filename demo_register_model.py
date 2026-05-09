# examples/register_model.py

"""模型注册示例"""

import asyncio

from datamind.context.scope import context_scope
from datamind.models.register import ModelRegister


async def main():
    """主函数"""
    register = ModelRegister()

    result = await register.register(
        name="scorecard",
        version="4.1.10",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="scoring",
        model_path="datamind/demo/scorecard.pkl",
        description="信用评分卡模型",
        params={
            "solver": "lbfgs",
            "max_iter": 1000,
        },
        metrics={
            "auc": 0.89,
            "ks": 0.42,
        },
        created_by="admin",
        force=True,
    )

    print("模型注册成功：")
    print(f"模型ID: {result['model_id']}")
    print(f"版本号: {result['version']}")
    print(f"存储路径: {result['storage_key']}")
    print(f"Bento标签: {result['bento_tag']}")


if __name__ == "__main__":
    with context_scope(
            user="admin",
            ip="127.0.0.1",
            trace_id="trace-001",
            request_id="req-001",
            source="http",
    ):
      asyncio.run(main())