"""部署仓储测试

验证 DeploymentRepository 的部署查询、列表筛选、创建、
普通字段更新，以及部署启用和停用时的有效期管理。

核心功能：
  - test_get_deployment:
    验证按部署 ID 查询
  - test_list_deployments:
    验证常量筛选、状态筛选、排序和分页
  - test_list_active_deployments:
    验证活跃部署列表
  - test_deployment_patch:
    验证更新结构和常量枚举
  - test_create_deployment:
    验证创建部署并设置 inactive 状态
  - test_update_deployment:
    验证普通部署字段更新
  - test_activate_deployment:
    验证启用部署并维护生效时间
  - test_deactivate_deployment:
    验证停用部署并维护结束时间
"""

from dataclasses import fields
from datetime import (
    datetime,
    timezone,
    tzinfo,
)
from typing import (
    Any,
    Self,
    cast,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

import datamind.db.repositories.deployment as deployment_module
from datamind.constants import (
    Environment,
    Framework,
)
from datamind.db.models.deployments import Deployment
from datamind.db.repositories.deployment import (
    DeploymentPatch,
    DeploymentRepository,
)
from datamind.models.enums import DeploymentStatus


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    11,
    30,
    tzinfo=timezone.utc,
)

EARLIER_TIME = datetime(
    2026,
    7,
    20,
    8,
    0,
    tzinfo=timezone.utc,
)

LATER_TIME = datetime(
    2026,
    8,
    20,
    8,
    0,
    tzinfo=timezone.utc,
)


def create_deployment(
        **overrides: Any,
) -> Deployment:
    """创建部署测试对象"""
    values: dict[str, Any] = {
        "deployment_id": "dep_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "version_id": "ver_0123456789abcdef",
        "framework": "sklearn",
        "environment": "production",
        "status": str(
            DeploymentStatus.INACTIVE
        ),
        "rollout_type": "full",
        "role": "champion",
        "effective_from": None,
        "effective_to": None,
        "threshold": 0.5,
        "description": "信用评分模型部署",
        "deployed_by": "deployer",
        "updated_by": "original_operator",
    }
    values.update(
        overrides
    )

    return Deployment(
        **values
    )


def create_repository(
        *,
        scalar_result: Deployment | None = None,
        list_result: list[Deployment] | None = None,
) -> tuple[
    DeploymentRepository,
    AsyncMock,
    MagicMock,
]:
    """创建部署仓储及会话方法替身"""
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        scalar_result
    )

    scalar_collection = MagicMock()
    scalar_collection.all.return_value = (
        list_result
        if list_result is not None
        else []
    )
    result.scalars.return_value = (
        scalar_collection
    )

    execute = AsyncMock(
        return_value=result
    )
    add = MagicMock()

    session_mock = MagicMock(
        spec=AsyncSession
    )
    session_mock.execute = execute
    session_mock.add = add

    session = cast(
        AsyncSession,
        cast(
            object,
            session_mock,
        ),
    )
    repository = DeploymentRepository(
        session
    )

    return (
        repository,
        execute,
        add,
    )


def get_executed_statement(
        execute: AsyncMock,
) -> Select[Any]:
    """获取异步会话执行的查询语句"""
    awaited_call = execute.await_args

    assert awaited_call is not None

    return cast(
        Select[Any],
        awaited_call.args[
            0
        ],
    )


def compile_statement(
        statement: Select[Any],
) -> str:
    """将查询语句编译为 PostgreSQL SQL"""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )


@pytest.mark.asyncio
async def test_get_deployment() -> None:
    """测试按部署 ID 查询"""
    expected = create_deployment()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_deployment(
        "dep_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "deployments.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_deployment_returns_none_when_not_found() -> None:
    """测试部署不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_deployment(
        "dep_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_deployments_without_filters() -> None:
    """测试无筛选时返回全部部署并按创建时间倒序"""
    deployments = [
        create_deployment()
    ]
    repository, execute, _ = create_repository(
        list_result=deployments
    )

    result = await repository.list_deployments()

    assert result == deployments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY deployments.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_deployments_applies_filters_and_pagination() -> None:
    """测试常量、状态、普通字段筛选和分页"""
    deployments = [
        create_deployment(
            framework="xgboost",
            environment="staging",
            status=str(
                DeploymentStatus.ACTIVE
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=deployments
    )

    result = await repository.list_deployments(
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        framework=Framework.XGBOOST,
        environment=Environment.STAGING,
        rollout_type="canary",
        role="challenger",
        status=DeploymentStatus.ACTIVE,
        deployed_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == deployments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "deployments.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "deployments.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )
    assert (
        "deployments.framework = 'xgboost'"
        in sql
    )
    assert (
        "deployments.environment = 'staging'"
        in sql
    )
    assert (
        "deployments.rollout_type = 'canary'"
        in sql
    )
    assert (
        "deployments.role = 'challenger'"
        in sql
    )
    assert (
        "deployments.status = 'active'"
        in sql
    )
    assert (
        "deployments.deployed_by = 'model_admin'"
        in sql
    )
    assert (
        "ORDER BY deployments.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_deployments_applies_zero_pagination() -> None:
    """测试零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_deployments(
        limit=0,
        offset=0,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "LIMIT 0" in sql
    assert "OFFSET 0" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "arguments",
        "expected_message",
    ),
    [
        (
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            {
                "limit": -1,
                "offset": -1,
            },
            "limit 不能小于 0",
        ),
    ],
)
async def test_list_deployments_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """测试拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_deployments(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_deployments() -> None:
    """测试活跃部署列表"""
    deployments = [
        create_deployment(
            status=str(
                DeploymentStatus.ACTIVE
            )
        )
    ]
    repository, execute, _ = create_repository(
        list_result=deployments
    )

    result = await repository.list_active_deployments(
        "mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        environment=Environment.PRODUCTION,
        limit=50,
        offset=5,
    )

    assert result == deployments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "deployments.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "deployments.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )
    assert (
        "deployments.environment = 'production'"
        in sql
    )
    assert (
        "deployments.status = 'active'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_deployment_patch_fields_and_defaults() -> None:
    """测试更新结构字段和默认值"""
    patch = DeploymentPatch()

    assert [
        field.name
        for field in fields(
            DeploymentPatch
        )
    ] == [
        "framework",
        "environment",
        "rollout_type",
        "role",
        "effective_from",
        "effective_to",
        "threshold",
        "description",
    ]
    assert patch.framework is None
    assert patch.environment is None
    assert patch.rollout_type is None
    assert patch.role is None
    assert patch.effective_from is None
    assert patch.effective_to is None
    assert patch.threshold is None
    assert patch.description is None
    assert not hasattr(
        patch,
        "status",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_deployment_patch_accepts_constant_enums() -> None:
    """测试更新结构接受框架和环境枚举"""
    patch = DeploymentPatch(
        framework=Framework.XGBOOST,
        environment=Environment.STAGING,
    )

    assert patch.framework is (
        Framework.XGBOOST
    )
    assert patch.environment is (
        Environment.STAGING
    )


def test_create_deployment() -> None:
    """测试创建部署并显式设置 inactive 状态"""
    repository, _, add = create_repository()

    deployment = repository.create_deployment(
        deployment_id="dep_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        framework=Framework.SKLEARN,
        environment=Environment.PRODUCTION,
        rollout_type="canary",
        role="challenger",
        effective_from=EARLIER_TIME,
        effective_to=LATER_TIME,
        threshold=0.6,
        description="灰度部署",
        deployed_by="deployer",
    )

    add.assert_called_once_with(
        deployment
    )
    assert deployment.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert deployment.model_id == (
        "mdl_0123456789abcdef"
    )
    assert deployment.version_id == (
        "ver_0123456789abcdef"
    )
    assert deployment.framework == "sklearn"
    assert deployment.environment == (
        "production"
    )
    assert deployment.status == str(
        DeploymentStatus.INACTIVE
    )
    assert deployment.rollout_type == "canary"
    assert deployment.role == "challenger"
    assert (
        deployment.effective_from
        == EARLIER_TIME
    )
    assert (
        deployment.effective_to
        == LATER_TIME
    )
    assert deployment.threshold == 0.6
    assert deployment.description == (
        "灰度部署"
    )
    assert deployment.deployed_by == "deployer"


# noinspection PyUnreachableCode
def test_create_deployment_uses_optional_defaults() -> None:
    """测试创建部署的可选默认值"""
    repository, _, add = create_repository()

    deployment = repository.create_deployment(
        deployment_id="dep_minimum",
        model_id="mdl_minimum",
        version_id="ver_minimum",
        framework=Framework.SKLEARN,
        environment=Environment.TESTING,
    )

    add.assert_called_once_with(
        deployment
    )
    assert deployment.status == str(
        DeploymentStatus.INACTIVE
    )
    assert deployment.rollout_type == "full"
    assert deployment.role == "champion"
    assert deployment.effective_from is None
    assert deployment.effective_to is None
    assert deployment.threshold is None
    assert deployment.description is None
    assert deployment.deployed_by is None


def test_update_deployment() -> None:
    """测试更新所有非空普通部署字段"""
    repository, _, _ = create_repository()
    deployment = create_deployment()
    original_status = deployment.status

    result = repository.update_deployment(
        deployment,
        DeploymentPatch(
            framework=Framework.XGBOOST,
            environment=Environment.STAGING,
            rollout_type="canary",
            role="challenger",
            effective_from=EARLIER_TIME,
            effective_to=LATER_TIME,
            threshold=0.7,
            description="更新后的部署说明",
        ),
        updated_by="operator",
    )

    assert result is deployment
    assert deployment.framework == "xgboost"
    assert deployment.environment == "staging"
    assert deployment.rollout_type == "canary"
    assert deployment.role == "challenger"
    assert (
        deployment.effective_from
        == EARLIER_TIME
    )
    assert (
        deployment.effective_to
        == LATER_TIME
    )
    assert deployment.threshold == 0.7
    assert deployment.description == (
        "更新后的部署说明"
    )
    assert deployment.updated_by == "operator"
    assert deployment.status == original_status


def test_update_deployment_ignores_none_fields() -> None:
    """测试值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    deployment = create_deployment(
        description="原部署说明",
        effective_to=LATER_TIME,
    )

    result = repository.update_deployment(
        deployment,
        DeploymentPatch(),
    )

    assert result is deployment
    assert deployment.framework == "sklearn"
    assert deployment.environment == (
        "production"
    )
    assert deployment.description == (
        "原部署说明"
    )
    assert deployment.effective_to == LATER_TIME


def test_update_deployment_accepts_empty_strings() -> None:
    """测试空字符串作为明确更新值写入对象"""
    repository, _, _ = create_repository()
    deployment = create_deployment()

    repository.update_deployment(
        deployment,
        DeploymentPatch(
            rollout_type="",
            role="",
            description="",
        ),
        updated_by="",
    )

    assert deployment.rollout_type == ""
    assert deployment.role == ""
    assert deployment.description == ""
    assert deployment.updated_by == ""


# noinspection PyUnreachableCode
def test_activate_deployment_sets_effective_from(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次启用设置开始时间并清除结束时间"""
    class FrozenDateTime(
        datetime
    ):
        @classmethod
        def now(
                cls,
                tz: tzinfo | None = None,
        ) -> Self:
            assert tz is timezone.utc

            return cls.fromtimestamp(
                CURRENT_TIME.timestamp(),
                tz,
            )

    repository, _, _ = create_repository()
    deployment = create_deployment(
        status=str(
            DeploymentStatus.INACTIVE
        ),
        effective_from=None,
        effective_to=LATER_TIME,
    )

    monkeypatch.setitem(
        vars(deployment_module),
        "datetime",
        FrozenDateTime,
    )

    result = repository.activate_deployment(
        deployment,
        updated_by="operator",
    )

    assert result is deployment
    assert deployment.status == str(
        DeploymentStatus.ACTIVE
    )
    assert (
        deployment.effective_from
        == CURRENT_TIME
    )
    assert deployment.effective_to is None
    assert deployment.updated_by == "operator"


# noinspection PyUnreachableCode
def test_activate_deployment_preserves_effective_from() -> None:
    """测试重复启用保留原开始时间"""
    repository, _, _ = create_repository()
    deployment = create_deployment(
        status=str(
            DeploymentStatus.ACTIVE
        ),
        effective_from=EARLIER_TIME,
        effective_to=LATER_TIME,
        updated_by="original_operator",
    )

    result = repository.activate_deployment(
        deployment
    )

    assert result is deployment
    assert deployment.status == str(
        DeploymentStatus.ACTIVE
    )
    assert (
        deployment.effective_from
        == EARLIER_TIME
    )
    assert deployment.effective_to is None
    assert deployment.updated_by == (
        "original_operator"
    )


def test_activate_deployment_accepts_empty_operator() -> None:
    """测试启用时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    deployment = create_deployment()

    repository.activate_deployment(
        deployment,
        updated_by="",
    )

    assert deployment.updated_by == ""


def test_deactivate_deployment_sets_effective_to(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次停用记录结束时间"""
    class FrozenDateTime(
        datetime
    ):
        @classmethod
        def now(
                cls,
                tz: tzinfo | None = None,
        ) -> Self:
            assert tz is timezone.utc

            return cls.fromtimestamp(
                CURRENT_TIME.timestamp(),
                tz,
            )

    repository, _, _ = create_repository()
    deployment = create_deployment(
        status=str(
            DeploymentStatus.ACTIVE
        ),
        effective_from=EARLIER_TIME,
        effective_to=None,
    )

    monkeypatch.setitem(
        vars(deployment_module),
        "datetime",
        FrozenDateTime,
    )

    result = repository.deactivate_deployment(
        deployment,
        updated_by="operator",
    )

    assert result is deployment
    assert deployment.status == str(
        DeploymentStatus.INACTIVE
    )
    assert (
        deployment.effective_from
        == EARLIER_TIME
    )
    assert (
        deployment.effective_to
        == CURRENT_TIME
    )
    assert deployment.updated_by == "operator"


def test_deactivate_deployment_preserves_effective_to() -> None:
    """测试重复停用保留原结束时间"""
    repository, _, _ = create_repository()
    deployment = create_deployment(
        status=str(
            DeploymentStatus.INACTIVE
        ),
        effective_to=LATER_TIME,
        updated_by="original_operator",
    )

    result = repository.deactivate_deployment(
        deployment
    )

    assert result is deployment
    assert deployment.status == str(
        DeploymentStatus.INACTIVE
    )
    assert deployment.effective_to == LATER_TIME
    assert deployment.updated_by == (
        "original_operator"
    )


def test_deactivate_deployment_accepts_empty_operator() -> None:
    """测试停用时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    deployment = create_deployment(
        status=str(
            DeploymentStatus.ACTIVE
        )
    )

    repository.deactivate_deployment(
        deployment,
        updated_by="",
    )

    assert deployment.updated_by == ""
