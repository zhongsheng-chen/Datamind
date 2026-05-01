"""audit 装饰器示例（完整版本）"""

import asyncio

from datamind.config import get_settings
from datamind.logging import setup_logging
from datamind.audit import audit, start_audit_worker, stop_audit_worker
from datamind.context.scope import context_scope
from datamind.audit.dispatcher import get_queue


# ================================
# 示例1：模型注册（HTTP 请求）
# ================================
@audit(
    action="model.register",
    target_type="model",
    target_id_from="model_id",
)
async def register(model_id: str, name: str):
    return {
        "model_id": model_id,
        "name": name,
    }


# ================================
# 示例2：模型下线（HTTP 请求）
# ================================
@audit(
    action="model.retire",
    target_type="model",
    target_id_from="model_id",
)
async def retire(model_id: str, version: str, reason: str):
    return {
        "model_id": model_id,
        "version": version,
        "status": "retired",
        "reason": reason,
    }


# ================================
# 示例3：部署创建（system 内部调用）
# ================================
@audit(
    action="deployment.create",
    target_type="deployment",
    target_id_func=lambda p: f"{p['model_id']}-{p['version']}",
)
async def deploy(model_id: str, version: str):
    return {
        "deployment_id": f"{model_id}-{version}",
        "status": "active",
    }


# ================================
# 示例4：模型更新（带 before / after）
# ================================
@audit(
    action="model.update",
    target_type="model",
    target_id_from="model_id",
    before_func=lambda p: {
        "model_id": p["model_id"],
        "name": "scorecard-v1",
        "status": "draft",
    },
    after_func=lambda p, result: result,
)
async def update(model_id: str, name: str):
    return {
        "model_id": model_id,
        "name": name,
        "status": "active",
    }


# ================================
# 示例5：异常审计（失败场景）
# ================================
@audit(
    action="model.delete",
    target_type="model",
    target_id_from="model_id",
)
async def delete(model_id: str):
    raise RuntimeError("模型不存在")


# ================================
# 示例6：并发请求（压力测试）
# ================================
async def concurrent_test():
    print("\n====== 开始并发测试 ======\n")

    await asyncio.gather(
        register("mdl_002", "ranker"),
        retire("mdl_002", "1.0.0", "版本过旧"),
        deploy("mdl_002", "1.0.0"),
        update("mdl_002", "ranker-v2"),
    )

    print("\n====== 并发测试完成 ======\n")


# ================================
# 主函数
# ================================
async def main():
    setup_logging(get_settings().logging)

    # 启动审计 worker
    await start_audit_worker()
    print("审计 Worker 已启动\n")

    try:
        # ================================
        # 示例 A：HTTP 请求上下文（source=http）
        # ================================
        with context_scope(
            user="admin",
            ip="127.0.0.1",
            trace_id="trace-001",
            request_id="req-001",
            source="http",
        ):
            print("====== HTTP 请求场景（source=http）======")

            result1 = await register("mdl_001", "scorecard")
            print("模型注册成功：", result1)

            result2 = await retire(
                model_id="mdl_001",
                version="1.0.0",
                reason="模型过期",
            )
            print("模型下线成功：", result2)

            result3 = await update(
                model_id="mdl_001",
                name="scorecard-v2",
            )
            print("模型更新成功：", result3)

        # ================================
        # 示例 B：内部调用上下文（source=system）
        # ================================
        with context_scope(
            user="admin",
            ip="127.0.0.1",
            trace_id="trace-002",
            request_id="req-002",
            source="system",
        ):
            print("\n====== 内部调用上下文（source=system）======")

            result4 = await deploy(
                model_id="mdl_001",
                version="1.0.0",
            )
            print("部署成功：", result4)

            try:
                await delete("mdl_404")
            except RuntimeError as e:
                print("捕获预期异常：", e)

        # ================================
        # 示例 C：无上下文
        # ================================
        print("\n====== 无上下文 ======")

        await deploy(
            model_id="mdl_001",
            version="1.0.0-new",
        )

        print("\nsystem 调用完成")

        # ================================
        # 示例 D：并发测试
        # ================================
        # await concurrent_test()

        # ================================
        # 等待队列消费完成
        # ================================
        await get_queue().join()
        print("所有审计事件已处理完成\n")

    finally:
        # 停止 worker
        await stop_audit_worker()
        print("审计 Worker 已停止")


if __name__ == "__main__":
    asyncio.run(main())