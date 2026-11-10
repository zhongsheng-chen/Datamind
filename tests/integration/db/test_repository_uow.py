"""Datamind Repository 与 UnitOfWork 的 PostgreSQL 集成测试.

验证业务仓储通过真实 PostgreSQL 完成提交、跨会话读取、回滚、唯一约束，
并确认 ORM 事件与业务记录在同一事务中持久化至 Outbox。

核心功能：
  - test_repository_graph_commits_and_is_visible_to_a_new_session:
    验证主要业务记录与 Outbox 跨会话可见
  - test_unit_of_work_rolls_back_after_exception:
    验证业务异常触发完整事务回滚
  - test_repository_commit_enforces_unique_constraint:
    验证 Repository 写入受 PostgreSQL 唯一约束保护
  - test_default_deployment_switch_is_persisted_and_environment_scoped:
    验证默认切换跨事务持久化、保留新旧部署启用状态且不影响其他环境
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from datamind.constants import Environment, Framework, ModelType, TaskType
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AttemptRepository,
    DeploymentRepository,
    ExecutionRepository,
    MetadataRepository,
    OutboxRepository,
    RoutingRepository,
    VersionRepository,
)
from datamind.models.enums import ExecutionStatus, ExecutionType
from datamind.services.deployment import DeploymentLifecycleService


pytestmark = pytest.mark.integration


def resource_ids() -> dict[str, str]:
    """生成单个测试使用的稳定前缀业务标识."""
    suffix = uuid.uuid4().hex
    return {
        "model": f"mdl_{suffix}",
        "version": f"ver_{suffix}",
        "artifact": f"art_{suffix}",
        "deployment": f"dep_{suffix}",
        "routing": f"rte_{suffix}",
        "decision": f"dec_{suffix}",
        "execution": f"exe_{suffix}",
        "batch": f"bat_{suffix}",
        "task": f"tsk_{suffix}",
    }


@pytest.mark.asyncio
async def test_repository_graph_commits_and_is_visible_to_a_new_session(
    datamind_database: AsyncEngine,
) -> None:
    """测试主要 Repository 写入提交后可由新 UnitOfWork 查询."""
    del datamind_database
    identifiers = resource_ids()
    model_name = f"integration-{identifiers['model']}"

    async with UnitOfWork() as uow:
        MetadataRepository(uow.session).create_model(
            model_id=identifiers["model"],
            name=model_name,
            model_type=ModelType.LOGISTIC_REGRESSION,
            task_type=TaskType.CLASSIFICATION,
            framework=Framework.SKLEARN,
        )
        VersionRepository(uow.session).create_version(
            version_id=identifiers["version"],
            model_id=identifiers["model"],
            version="1.0.0",
            framework=Framework.SKLEARN,
            bento_tag=f"{model_name}:latest",
            model_path="s3://integration/model.pkl",
            model_key="integration/model.pkl",
            current_artifact_id=identifiers["artifact"],
            artifact_sha256="a" * 64,
            artifact_digest="b" * 64,
        )
        DeploymentRepository(uow.session).create_deployment(
            deployment_id=identifiers["deployment"],
            model_id=identifiers["model"],
            version_id=identifiers["version"],
            framework=Framework.SKLEARN,
            environment=Environment.TESTING,
        )
        RoutingRepository(uow.session).create_routing(
            routing_id=identifiers["routing"],
            name=f"route-{identifiers['routing']}",
            deployment_id=identifiers["deployment"],
            environment=Environment.TESTING,
            traffic_ratio=1.0,
            enabled=True,
        )
        ExecutionRepository(uow.session).create_execution(
            execution_id=identifiers["execution"],
            decision_id=identifiers["decision"],
            execution_type=ExecutionType.PRIMARY,
            status=ExecutionStatus.QUEUED,
            model_id=identifiers["model"],
            version_id=identifiers["version"],
            deployment_id=identifiers["deployment"],
            routing_id=identifiers["routing"],
        )
        AttemptRepository(uow.session).create_attempt(
            batch_id=identifiers["batch"],
            task_id=identifiers["task"],
            attempt_number=1,
        )

    async with UnitOfWork() as uow:
        model = await MetadataRepository(uow.session).get_model(
            model_id=identifiers["model"]
        )
        version = await VersionRepository(uow.session).get_version(
            identifiers["version"]
        )
        deployment = await DeploymentRepository(uow.session).get_deployment(
            identifiers["deployment"]
        )
        routing = await RoutingRepository(uow.session).get_routing(
            identifiers["routing"]
        )
        execution = await ExecutionRepository(uow.session).get_execution(
            identifiers["execution"]
        )
        attempt = await AttemptRepository(uow.session).get_latest_attempt(
            identifiers["batch"]
        )
        events = await OutboxRepository(uow.session).list_events(after_event_id=0)

    assert model is not None
    assert version is not None
    assert deployment is not None
    assert routing is not None
    assert execution is not None
    assert attempt is not None
    assert attempt.attempt_number == 1
    assert {
        (event.topic, event.resource_id, event.action) for event in events
    }.issuperset(
        {
            ("models", identifiers["model"], "insert"),
            ("versions", identifiers["version"], "insert"),
            ("deployments", identifiers["deployment"], "insert"),
            ("routings", identifiers["routing"], "insert"),
            ("executions", identifiers["execution"], "insert"),
        }
    )


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_after_exception(
    datamind_database: AsyncEngine,
) -> None:
    """测试异常退出 UnitOfWork 后业务记录与 Outbox 均不落库."""
    del datamind_database
    identifiers = resource_ids()

    with pytest.raises(RuntimeError, match="force rollback"):
        async with UnitOfWork() as uow:
            MetadataRepository(uow.session).create_model(
                model_id=identifiers["model"],
                name=f"rollback-{identifiers['model']}",
                model_type=ModelType.LOGISTIC_REGRESSION,
                task_type=TaskType.CLASSIFICATION,
                framework=Framework.SKLEARN,
            )
            raise RuntimeError("force rollback")

    async with UnitOfWork() as uow:
        model = await MetadataRepository(uow.session).get_model(
            model_id=identifiers["model"]
        )
        events = await OutboxRepository(uow.session).list_events(after_event_id=0)

    assert model is None
    assert all(event.resource_id != identifiers["model"] for event in events)


@pytest.mark.asyncio
async def test_repository_commit_enforces_unique_constraint(
    datamind_database: AsyncEngine,
) -> None:
    """测试重复模型名称在 UnitOfWork 提交阶段触发唯一约束."""
    del datamind_database
    identifiers = resource_ids()
    duplicate_name = f"duplicate-{identifiers['model']}"

    with pytest.raises(IntegrityError):
        async with UnitOfWork() as uow:
            repository = MetadataRepository(uow.session)
            for index in range(2):
                repository.create_model(
                    model_id=f"{identifiers['model']}-{index}",
                    name=duplicate_name,
                    model_type=ModelType.LOGISTIC_REGRESSION,
                    task_type=TaskType.CLASSIFICATION,
                    framework=Framework.SKLEARN,
                )

    async with UnitOfWork() as uow:
        model = await MetadataRepository(uow.session).get_model(name=duplicate_name)

    assert model is None


@pytest.mark.asyncio
async def test_default_deployment_switch_is_persisted_and_environment_scoped(
    datamind_database: AsyncEngine,
) -> None:
    """测试服务切换默认部署后新事务读取到正确标记、启用状态及环境隔离."""
    del datamind_database
    identifiers = resource_ids()
    model_name = f"default-switch-{identifiers['model']}"
    old_id = f"{identifiers['deployment']}_old"
    new_id = f"{identifiers['deployment']}_new"
    other_id = f"{identifiers['deployment']}_other"

    async with UnitOfWork() as uow:
        MetadataRepository(uow.session).create_model(
            model_id=identifiers["model"],
            name=model_name,
            model_type=ModelType.LOGISTIC_REGRESSION,
            task_type=TaskType.CLASSIFICATION,
            framework=Framework.SKLEARN,
        )
        VersionRepository(uow.session).create_version(
            version_id=identifiers["version"],
            model_id=identifiers["model"],
            version="1.0.0",
            framework=Framework.SKLEARN,
            bento_tag=f"{model_name}:latest",
            model_path="s3://integration/model.pkl",
            model_key="integration/model.pkl",
            current_artifact_id=identifiers["artifact"],
            artifact_sha256="a" * 64,
            artifact_digest="b" * 64,
        )
        repository = DeploymentRepository(uow.session)

        for deployment_id, environment, is_default in (
            (old_id, Environment.PRODUCTION, True),
            (new_id, Environment.PRODUCTION, False),
            (other_id, Environment.STAGING, True),
        ):
            deployment = repository.create_deployment(
                deployment_id=deployment_id,
                model_id=identifiers["model"],
                version_id=identifiers["version"],
                framework=Framework.SKLEARN,
                environment=environment,
                role="champion",
                rollout_type="full",
            )
            repository.activate_deployment(deployment)
            deployment.is_default = is_default

    result = await DeploymentLifecycleService().set_default_deployment(
        deployment_id=new_id,
        updated_by="integration-test",
    )

    assert result["deployment_id"] == new_id
    assert result["previous_deployment_id"] == old_id
    assert result["is_default"] is True

    async with UnitOfWork() as uow:
        repository = DeploymentRepository(uow.session)
        old = await repository.get_deployment(old_id)
        new = await repository.get_deployment(new_id)
        other = await repository.get_deployment(other_id)

        assert old is not None
        assert new is not None
        assert other is not None
        assert old.is_default is False
        assert new.is_default is True
        assert old.status == new.status == "active"
        assert old.role == new.role == "champion"
        assert old.environment == new.environment == Environment.PRODUCTION.value
        assert other.is_default is True
        assert other.status == "active"
        assert other.environment == Environment.STAGING.value
