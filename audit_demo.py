# datamind/audit/audit_demo.py

from datamind.db.core.session import session_scope

from datamind.context import set_context, get_context, clear_context
from datamind.audit.recorder import AuditRecorder


def main():

    # =========================================================
    # 1. 初始化 audit context（模拟请求进入）
    # =========================================================
    set_context(
        user_id="zhongsheng",
        ip="127.0.0.1",
        trace_id="trace-demo-001",
    )

    print("📌 audit context:", get_context())

    # =========================================================
    # 2. 打开一个 DB session（这里只是为了写 audit）
    # =========================================================
    with session_scope() as session:

        recorder = AuditRecorder(session)

        # =====================================================
        # 3. 模拟一个 create 操作
        # =====================================================
        before = None
        after = {
            "model_id": "demo_model",
            "status": "active"
        }

        audit1 = recorder.record(
            action="create_model",
            target_type="metadata",
            target_id="model-001",
            before=before,
            after=after,
            context={
                "source": "audit_demo",
                "reason": "initial create"
            },
        )

        print("✔ audit1 written:", audit1)

        # =====================================================
        # 4. 模拟 update 操作
        # =====================================================
        before = {"status": "active"}
        after = {"status": "inactive"}

        audit2 = recorder.record(
            action="update_model",
            target_type="metadata",
            target_id="model-001",
            before=before,
            after=after,
            context={
                "field": "status",
                "change": "active -> inactive"
            },
        )

        print("✔ audit2 written:", audit2)

        # =====================================================
        # 5. 模拟 deployment 操作
        # =====================================================
        audit3 = recorder.record(
            action="deploy_model",
            target_type="deployment",
            target_id="deploy-001",
            after={
                "model_id": "demo_model",
                "version": "v2",
                "traffic_ratio": 1.0
            },
            context={
                "env": "prod"
            },
        )

        print("✔ audit3 written:", audit3)

    # =========================================================
    # 6. 清理 context（模拟请求结束）
    # =========================================================
    clear_context()

    print("✅ audit demo completed")


if __name__ == "__main__":
    main()