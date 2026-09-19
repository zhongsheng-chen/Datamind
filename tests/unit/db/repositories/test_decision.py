"""请求决策仓储测试

验证 DecisionRepository 的决策查询、列表筛选、辅助列表方法，
以及决策记录创建和权重校验。

核心功能：
  - test_get_decision:
    验证按请求 ID 查询决策结果
  - test_list_decisions:
    验证决策来源、主体字段、排序和分页
  - test_list_model_decisions:
    验证获取模型决策记录
  - test_list_deployment_decisions:
    验证获取部署决策记录
  - test_list_experiment_decisions:
    验证获取实验决策记录
  - test_list_variant_decisions:
    验证获取实验分组决策记录
  - test_create_decision:
    验证创建决策记录
  - test_create_decision_validation:
    验证权重范围
"""

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

import datamind.db.repositories.decision as decision_module
from datamind.db.models.decisions import Decision
from datamind.db.repositories.decision import DecisionRepository
from datamind.models.enums import DecisionStrategy


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    14,
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


def create_decision(
        **overrides: Any,
) -> Decision:
    """创建请求决策测试对象"""
    values: dict[str, Any] = {
        "decision_id": "dcs_0123456789abcdef",
        "request_id": "req_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "version_id": "ver_0123456789abcdef",
        "deployment_id": "dep_0123456789abcdef",
        "experiment_id": "exp_0123456789abcdef",
        "variant_id": "var_0123456789abcdef",
        "assignment_id": "asn_0123456789abcdef",
        "subject_key": "customer_10001",
        "subject_type": "customer",
        "source": str(
            DecisionStrategy.EXPERIMENT
        ),
        "strategy": "hash",
        "bucket": "bucket_0089",
        "group": "treatment",
        "weight": 0.5,
        "decision": "approve",
        "context": {
            "environment": "production",
        },
        "decided_at": EARLIER_TIME,
    }
    values.update(
        overrides
    )

    return Decision(
        **values
    )


def create_repository(
        *,
        scalar_result: Decision | None = None,
        list_result: list[Decision] | None = None,
) -> tuple[
    DecisionRepository,
    AsyncMock,
    MagicMock,
]:
    """创建请求决策仓储及会话方法替身"""
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
    repository = DecisionRepository(
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
async def test_get_decision() -> None:
    """测试按请求 ID 查询决策结果"""
    expected = create_decision()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_decision(
        "req_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "decisions.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )
    assert "ORDER BY decisions.decided_at DESC" in sql
    assert "LIMIT 1" in sql


@pytest.mark.asyncio
async def test_get_decision_returns_none_when_not_found() -> None:
    """测试请求没有决策结果时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_decision(
        "req_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_decisions_without_filters() -> None:
    """测试无筛选时返回全部决策并按时间倒序"""
    decisions = [
        create_decision()
    ]
    repository, execute, _ = create_repository(
        list_result=decisions
    )

    result = await repository.list_decisions()

    assert result == decisions

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY decisions.decided_at DESC, "
        "decisions.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_decisions_applies_filters_and_pagination() -> None:
    """测试决策来源、主体字段、普通字段筛选和分页"""
    decisions = [
        create_decision(
            source=str(
                DecisionStrategy.ROUTING
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=decisions
    )

    result = await repository.list_decisions(
        decision_id="dcs_0123456789abcdef",
        request_id="req_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        assignment_id="asn_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        source=DecisionStrategy.ROUTING,
        strategy="fallback",
        bucket="bucket_0089",
        group="champion",
        decision="approve",
        limit=25,
        offset=10,
    )

    assert result == decisions

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "decisions.decision_id = "
        "'dcs_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.assignment_id = "
        "'asn_0123456789abcdef'"
        in sql
    )
    assert (
        "decisions.subject_key = "
        "'customer_10001'"
        in sql
    )
    assert (
        "decisions.subject_type = 'customer'"
        in sql
    )
    assert (
        "decisions.source = 'routing'"
        in sql
    )
    assert (
        "decisions.strategy = 'fallback'"
        in sql
    )
    assert (
        "decisions.bucket = 'bucket_0089'"
        in sql
    )
    assert (
        'decisions."group" = \'champion\''
        in sql
    )
    assert (
        "decisions.decision = 'approve'"
        in sql
    )
    assert (
        "ORDER BY decisions.decided_at DESC, "
        "decisions.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_decisions_applies_zero_pagination() -> None:
    """测试零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_decisions(
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
        "method_name",
        "arguments",
        "expected_message",
    ),
    [
        (
            "list_decisions",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_decisions",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_model_decisions",
            {
                "model_id": "mdl_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_deployment_decisions",
            {
                "deployment_id": "dep_test",
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_experiment_decisions",
            {
                "experiment_id": "exp_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_variant_decisions",
            {
                "variant_id": "var_test",
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
    ],
)
async def test_list_methods_reject_negative_pagination(
        method_name: str,
        arguments: dict[str, Any],
        expected_message: str,
) -> None:
    """测试决策列表方法拒绝负数分页参数"""
    repository, execute, _ = create_repository()
    method = getattr(
        repository,
        method_name,
    )

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await method(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "method_name",
        "argument_name",
        "argument_value",
        "expected_condition",
    ),
    [
        (
            "list_model_decisions",
            "model_id",
            "mdl_0123456789abcdef",
            (
                "decisions.model_id = "
                "'mdl_0123456789abcdef'"
            ),
        ),
        (
            "list_deployment_decisions",
            "deployment_id",
            "dep_0123456789abcdef",
            (
                "decisions.deployment_id = "
                "'dep_0123456789abcdef'"
            ),
        ),
        (
            "list_experiment_decisions",
            "experiment_id",
            "exp_0123456789abcdef",
            (
                "decisions.experiment_id = "
                "'exp_0123456789abcdef'"
            ),
        ),
        (
            "list_variant_decisions",
            "variant_id",
            "var_0123456789abcdef",
            (
                "decisions.variant_id = "
                "'var_0123456789abcdef'"
            ),
        ),
    ],
)
async def test_specialized_list_methods(
        method_name: str,
        argument_name: str,
        argument_value: str,
        expected_condition: str,
) -> None:
    """测试辅助列表方法应用对应筛选条件"""
    decisions = [
        create_decision()
    ]
    repository, execute, _ = create_repository(
        list_result=decisions
    )
    method = getattr(
        repository,
        method_name,
    )

    result = await method(
        **{
            argument_name: argument_value,
        },
        limit=50,
        offset=5,
    )

    assert result == decisions

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert expected_condition in sql
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_create_decision() -> None:
    """测试创建完整决策记录"""
    repository, _, add = create_repository()

    decision = repository.create_decision(
        decision_id="dcs_0123456789abcdef",
        request_id="req_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        assignment_id="asn_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        source=DecisionStrategy.EXPERIMENT,
        strategy="hash",
        bucket="bucket_0089",
        group="treatment",
        weight=0.5,
        decision="approve",
        context={
            "environment": "production",
        },
        decided_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        decision
    )
    assert decision.decision_id == (
        "dcs_0123456789abcdef"
    )
    assert decision.request_id == (
        "req_0123456789abcdef"
    )
    assert decision.model_id == (
        "mdl_0123456789abcdef"
    )
    assert decision.version_id == (
        "ver_0123456789abcdef"
    )
    assert decision.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert decision.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert decision.variant_id == (
        "var_0123456789abcdef"
    )
    assert decision.assignment_id == (
        "asn_0123456789abcdef"
    )
    assert decision.subject_key == (
        "customer_10001"
    )
    assert decision.subject_type == "customer"
    assert decision.source == "experiment"
    assert decision.strategy == "hash"
    assert decision.bucket == "bucket_0089"
    assert decision.group == "treatment"
    assert decision.weight == 0.5
    assert decision.decision == "approve"
    assert decision.context == {
        "environment": "production",
    }
    assert decision.decided_at == EARLIER_TIME


# noinspection PyUnreachableCode
def test_create_decision_uses_optional_defaults(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建决策时允许省略可选字段并使用当前时间"""
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

    repository, _, add = create_repository()

    monkeypatch.setitem(
        vars(decision_module),
        "datetime",
        FrozenDateTime,
    )

    decision = repository.create_decision(
        decision_id="dcs_minimum",
        request_id="req_minimum",
        model_id="mdl_minimum",
        version_id="ver_minimum",
        source=DecisionStrategy.DEPLOYMENT,
    )

    add.assert_called_once_with(
        decision
    )
    assert decision.source == "deployment"
    assert decision.deployment_id is None
    assert decision.experiment_id is None
    assert decision.variant_id is None
    assert decision.assignment_id is None
    assert decision.subject_key is None
    assert decision.subject_type is None
    assert decision.strategy is None
    assert decision.bucket is None
    assert decision.group is None
    assert decision.weight is None
    assert decision.decision is None
    assert decision.context is None
    assert decision.decided_at == CURRENT_TIME


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        (
            "weight",
            0.0,
        ),
        (
            "weight",
            1.0,
        ),
    ],
)
def test_create_decision_accepts_boundary_values(
        field_name: str,
        value: float,
) -> None:
    """测试数值字段边界值有效"""
    repository, _, add = create_repository()

    arguments: dict[str, Any] = {
        "decision_id": "dcs_boundary",
        "request_id": "req_boundary",
        "model_id": "mdl_boundary",
        "version_id": "ver_boundary",
        "source": DecisionStrategy.MANUAL,
        "decided_at": EARLIER_TIME,
        field_name: value,
    }

    decision = repository.create_decision(
        **arguments
    )

    add.assert_called_once_with(
        decision
    )
    assert getattr(
        decision,
        field_name,
    ) == value


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
        "expected_message",
    ),
    [
        (
            "weight",
            -0.01,
            "weight 必须在 0 到 1 之间",
        ),
        (
            "weight",
            1.01,
            "weight 必须在 0 到 1 之间",
        ),
    ],
)
def test_create_decision_rejects_invalid_values(
        field_name: str,
        value: float,
        expected_message: str,
) -> None:
    """测试创建决策时拒绝非法数值"""
    repository, _, add = create_repository()

    arguments: dict[str, Any] = {
        "decision_id": "dcs_invalid",
        "request_id": "req_invalid",
        "model_id": "mdl_invalid",
        "version_id": "ver_invalid",
        "source": DecisionStrategy.MANUAL,
        field_name: value,
    }

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        repository.create_decision(
            **arguments
        )

    add.assert_not_called()
