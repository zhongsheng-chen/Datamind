from datamind.db.core.uow import UnitOfWork
from datamind.db.core.context import set_context


def main():

    # =========================================================
    # 1. 设置全局请求上下文（audit / trace 会用）
    # =========================================================
    set_context(
        user_id="zhongsheng",
        ip="127.0.0.1",
        trace_id="trace-001",
    )

    # =========================================================
    # 2. 进入 UnitOfWork（唯一事务边界）
    # =========================================================
    with UnitOfWork() as uow:

        # -----------------------------------------------------
        # 3. 创建 request（数据平面进入）
        # -----------------------------------------------------
        request = uow.request().write(
            request_id="req-001",
            user_id="user-123",
            model_id="demo_model",
            payload={
                "age": 30,
                "income": 10000
            },
            source="api",
            ip="127.0.0.1",
        )

        uow.audit().write(
            action="request_created",
            target_type="request",
            target_id=request.request_id,
            after={
                "model_id": request.model_id,
                "payload": request.payload,
            },
        )

        # -----------------------------------------------------
        # 4. routing → assignment（控制平面决策）
        # -----------------------------------------------------
        assignment = uow.assignment().write(
            request_id="req-001",
            user_id="user-123",
            model_id="demo_model",
            version="v2",
            source="routing",
            strategy="consistent",
            context={
                "bucket": 128,
                "strategy": "hash"
            },
        )

        uow.audit().write(
            action="route_assigned",
            target_type="assignment",
            target_id=str(assignment.id),
            after={
                "version": assignment.version,
                "strategy": assignment.strategy,
            },
        )

        # -----------------------------------------------------
        # 5. deployment 操作
        # -----------------------------------------------------
        deployment = uow.deployment().write(
            model_id="demo_model",
            version="v2",
            status="active",
            traffic_ratio=1.0,
            deployed_by="admin",
            description="production rollout",
        )

        uow.audit().write(
            action="deployment_created",
            target_type="deployment",
            target_id=str(deployment.id),
            after={
                "model_id": deployment.model_id,
                "version": deployment.version,
                "status": deployment.status,
            },
        )

        # -----------------------------------------------------
        # 6. experiment 示例（可选）
        # -----------------------------------------------------
        experiment = uow.experiment().write(
            experiment_id="exp-001",
            model_id="demo_model",
            name="A/B Test v2",
            status="running",
            config={
                "variants": ["v1", "v2"],
                "traffic_split": [0.5, 0.5]
            },
        )

        uow.audit().write(
            action="experiment_created",
            target_type="experiment",
            target_id=experiment.experiment_id,
            after=experiment.config,
        )

    # =========================================================
    # 7. UoW 自动 commit（这里结束才落库）
    # =========================================================

    print("✅ uow demo completed successfully")


if __name__ == "__main__":
    main()