"""audit 装饰器示例"""

from datamind.audit import audit
from datamind.context.scope import context_scope


# ================================
# 示例1：模型注册
# ================================

@audit(
    action="model.register",
    target_type="model",
    target_id_from="model_id",
)
def register(model_id: str, name: str):
    return {
        "model_id": model_id,
        "name": name,
    }


# ================================
# 示例2：模型下线
# ================================

@audit(
    action="model.retire",
    target_type="model",
    target_id_from="model_id",
)
def retire(model_id: str, version: str, reason: str):
    return {
        "model_id": model_id,
        "version": version,
        "status": "retired",
        "reason": reason,
    }


# ================================
# 示例3：自定义 target_id
# ================================

@audit(
    action="deployment.create",
    target_type="deployment",
    target_id_func=lambda p: f"{p['model_id']}-{p['version']}",
)
def deploy(model_id: str, version: str):
    return {
        "deployment_id": f"{model_id}-{version}",
        "status": "active",
    }


# ================================
# 示例4：异常审计
# ================================

@audit(
    action="model.delete",
    target_type="model",
    target_id_from="model_id",
)
def delete(model_id: str):
    raise RuntimeError("模型不存在")


def main():
    # 自动注入上下文
    with context_scope(
        user="admin",
        ip="127.0.0.1",
        trace_id="trace-001",
        request_id="req-001",
    ):
        register("mdl_001", "scorecard")

        retire(
            model_id="mdl_001",
            version="1.0.0",
            reason="模型过期",
        )

        deploy(
            model_id="mdl_001",
            version="1.0.0",
        )

        try:
            delete("mdl_404")
        except RuntimeError:
            pass

    # ================================
    # 示例5：无 context_scope 审计
    # ================================

    deploy(
        model_id="mdl_001",
        version="1.0.0-new",
    )


if __name__ == "__main__":
    main()