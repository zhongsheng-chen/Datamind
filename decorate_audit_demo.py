# datamind/audit/audit_decorator_demo.py

from datamind.audit.decorator import audit_action
from datamind.audit.recorder import AuditRecorder
from datamind.db.core.session import session_scope
from datamind.audit.context import audit_context


# =========================================================
# 1. 模拟 ORM model
# =========================================================
class FakeDeployment:
    def __init__(self, id, model_id, version):
        self.id = id
        self.model_id = model_id
        self.version = version


# =========================================================
# 2. 被审计函数（完全不依赖 audit_recorder 参数）
# =========================================================
@audit_action(
    action="deployment.create",
    target_type="deployment",
    target_id_getter=lambda r: r.id
)
def create_deployment(session, deployment_data):

    obj = FakeDeployment(
        id="dep-001",
        model_id=deployment_data["model_id"],
        version=deployment_data["version"],
    )

    return obj


# =========================================================
# 3. demo 入口
# =========================================================
def main():

    with session_scope() as session:

        session.audit_recorder = AuditRecorder(session)

        with audit_context(
            user_id="zhongsheng",
            ip="127.0.0.1",
            trace_id="audit-decorator-demo",
        ):

            result = create_deployment(
                session,
                deployment_data={
                    "model_id": "model-001",
                    "version": "v1"
                }
            )

            print("✔ deployment result:", result.id)


if __name__ == "__main__":
    main()