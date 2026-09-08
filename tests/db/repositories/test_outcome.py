"""实验结果仓储测试

验证 OutcomeRepository 的结果查询、列表筛选、辅助列表方法、
结果记录创建、普通字段更新，以及逾期天数和金额校验。

核心功能：
  - test_get_outcome:
    验证按结果 ID 查询
  - test_list_outcomes:
    验证关联字段、布尔字段、排序和分页
  - test_list_experiment_outcomes:
    验证获取实验结果列表
  - test_list_variant_outcomes:
    验证获取实验分组结果列表
  - test_list_subject_outcomes:
    验证获取主体结果列表
  - test_list_request_outcomes:
    验证获取请求结果列表
  - test_outcome_patch:
    验证实验结果更新结构
  - test_create_outcome:
    验证创建实验结果
  - test_update_outcome:
    验证普通实验结果字段更新
  - test_outcome_validation:
    验证逾期天数和金额不能为负数
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

import datamind.db.repositories.outcome as outcome_module
from datamind.db.models.outcomes import Outcome
from datamind.db.repositories.outcome import (
    OutcomePatch,
    OutcomeRepository,
)


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    15,
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


def create_outcome(
        **overrides: Any,
) -> Outcome:
    """创建实验结果测试对象"""
    values: dict[str, Any] = {
        "outcome_id": "out_0123456789abcdef",
        "experiment_id": "exp_0123456789abcdef",
        "variant_id": "var_0123456789abcdef",
        "assignment_id": "asn_0123456789abcdef",
        "decision_id": "dcs_0123456789abcdef",
        "request_id": "req_0123456789abcdef",
        "subject_key": "customer_10001",
        "subject_type": "customer",
        "approved": True,
        "converted": True,
        "defaulted": False,
        "overdue_days": 0,
        "amount": 10000.0,
        "label": "good",
        "context": {
            "source": "loan_core",
        },
        "outcome_time": EARLIER_TIME,
    }
    values.update(
        overrides
    )

    return Outcome(
        **values
    )


def create_repository(
        *,
        scalar_result: Outcome | None = None,
        list_result: list[Outcome] | None = None,
) -> tuple[
    OutcomeRepository,
    AsyncMock,
    MagicMock,
]:
    """创建实验结果仓储及会话方法替身"""
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
    repository = OutcomeRepository(
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
async def test_get_outcome() -> None:
    """验证按结果 ID 查询"""
    expected = create_outcome()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_outcome(
        "out_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "outcomes.outcome_id = "
        "'out_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_outcome_returns_none_when_not_found() -> None:
    """验证实验结果不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_outcome(
        "out_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_outcomes_without_filters() -> None:
    """验证无筛选时返回全部结果并按时间倒序"""
    outcomes = [
        create_outcome()
    ]
    repository, execute, _ = create_repository(
        list_result=outcomes
    )

    result = await repository.list_outcomes()

    assert result == outcomes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY outcomes.outcome_time DESC, "
        "outcomes.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_outcomes_applies_filters_and_pagination() -> None:
    """验证关联字段、布尔字段、标签筛选和分页"""
    outcomes = [
        create_outcome(
            approved=False,
            converted=False,
            defaulted=True,
            label="bad",
        )
    ]
    repository, execute, _ = create_repository(
        list_result=outcomes
    )

    result = await repository.list_outcomes(
        outcome_id="out_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        assignment_id="asn_0123456789abcdef",
        decision_id="dcs_0123456789abcdef",
        request_id="req_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        approved=False,
        converted=False,
        defaulted=True,
        label="bad",
        limit=25,
        offset=10,
    )

    assert result == outcomes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "outcomes.outcome_id = "
        "'out_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.assignment_id = "
        "'asn_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.decision_id = "
        "'dcs_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )
    assert (
        "outcomes.subject_key = "
        "'customer_10001'"
        in sql
    )
    assert (
        "outcomes.subject_type = 'customer'"
        in sql
    )
    assert "outcomes.approved = false" in sql
    assert "outcomes.converted = false" in sql
    assert "outcomes.defaulted = true" in sql
    assert "outcomes.label = 'bad'" in sql
    assert (
        "ORDER BY outcomes.outcome_time DESC, "
        "outcomes.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_outcomes_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_outcomes(
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
            "list_outcomes",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_outcomes",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_experiment_outcomes",
            {
                "experiment_id": "exp_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_variant_outcomes",
            {
                "variant_id": "var_test",
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_subject_outcomes",
            {
                "subject_key": "customer_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_request_outcomes",
            {
                "request_id": "req_test",
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
    """验证实验结果列表方法拒绝负数分页参数"""
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
            "list_experiment_outcomes",
            "experiment_id",
            "exp_0123456789abcdef",
            (
                "outcomes.experiment_id = "
                "'exp_0123456789abcdef'"
            ),
        ),
        (
            "list_variant_outcomes",
            "variant_id",
            "var_0123456789abcdef",
            (
                "outcomes.variant_id = "
                "'var_0123456789abcdef'"
            ),
        ),
        (
            "list_subject_outcomes",
            "subject_key",
            "customer_10001",
            (
                "outcomes.subject_key = "
                "'customer_10001'"
            ),
        ),
        (
            "list_request_outcomes",
            "request_id",
            "req_0123456789abcdef",
            (
                "outcomes.request_id = "
                "'req_0123456789abcdef'"
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
    """验证辅助列表方法应用对应筛选条件"""
    outcomes = [
        create_outcome()
    ]
    repository, execute, _ = create_repository(
        list_result=outcomes
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

    assert result == outcomes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert expected_condition in sql
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_outcome_patch_fields_and_defaults() -> None:
    """验证实验结果更新结构字段和默认值"""
    patch = OutcomePatch()

    assert [
        field.name
        for field in fields(
            OutcomePatch
        )
    ] == [
        "experiment_id",
        "variant_id",
        "assignment_id",
        "decision_id",
        "request_id",
        "subject_key",
        "subject_type",
        "approved",
        "converted",
        "defaulted",
        "overdue_days",
        "amount",
        "label",
        "context",
        "outcome_time",
    ]
    assert patch.experiment_id is None
    assert patch.variant_id is None
    assert patch.assignment_id is None
    assert patch.decision_id is None
    assert patch.request_id is None
    assert patch.subject_key is None
    assert patch.subject_type is None
    assert patch.approved is None
    assert patch.converted is None
    assert patch.defaulted is None
    assert patch.overdue_days is None
    assert patch.amount is None
    assert patch.label is None
    assert patch.context is None
    assert patch.outcome_time is None
    assert not hasattr(
        patch,
        "__dict__",
    )


# noinspection PyUnreachableCode
def test_create_outcome() -> None:
    """验证创建完整实验结果"""
    repository, _, add = create_repository()

    outcome = repository.create_outcome(
        outcome_id="out_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        assignment_id="asn_0123456789abcdef",
        decision_id="dcs_0123456789abcdef",
        request_id="req_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        approved=True,
        converted=True,
        defaulted=False,
        overdue_days=0,
        amount=10000.0,
        label="good",
        context={
            "source": "loan_core",
        },
        outcome_time=EARLIER_TIME,
    )

    add.assert_called_once_with(
        outcome
    )
    assert outcome.outcome_id == (
        "out_0123456789abcdef"
    )
    assert outcome.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert outcome.variant_id == (
        "var_0123456789abcdef"
    )
    assert outcome.assignment_id == (
        "asn_0123456789abcdef"
    )
    assert outcome.decision_id == (
        "dcs_0123456789abcdef"
    )
    assert outcome.request_id == (
        "req_0123456789abcdef"
    )
    assert outcome.subject_key == (
        "customer_10001"
    )
    assert outcome.subject_type == "customer"
    assert outcome.approved is True
    assert outcome.converted is True
    assert outcome.defaulted is False
    assert outcome.overdue_days == 0
    assert outcome.amount == 10000.0
    assert outcome.label == "good"
    assert outcome.context == {
        "source": "loan_core",
    }
    assert outcome.outcome_time == EARLIER_TIME


# noinspection PyUnreachableCode
def test_create_outcome_uses_optional_defaults(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证创建结果时允许省略可选字段并使用当前时间"""
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
        vars(outcome_module),
        "datetime",
        FrozenDateTime,
    )

    outcome = repository.create_outcome(
        outcome_id="out_minimum",
        subject_key="customer_minimum",
    )

    add.assert_called_once_with(
        outcome
    )
    assert outcome.experiment_id is None
    assert outcome.variant_id is None
    assert outcome.assignment_id is None
    assert outcome.decision_id is None
    assert outcome.request_id is None
    assert outcome.subject_type is None
    assert outcome.approved is None
    assert outcome.converted is None
    assert outcome.defaulted is None
    assert outcome.overdue_days is None
    assert outcome.amount is None
    assert outcome.label is None
    assert outcome.context is None
    assert outcome.outcome_time == CURRENT_TIME


@pytest.mark.parametrize(
    (
        "field_name",
        "value",
    ),
    [
        (
            "overdue_days",
            0,
        ),
        (
            "amount",
            0.0,
        ),
    ],
)
def test_create_outcome_accepts_boundary_values(
        field_name: str,
        value: int | float,
) -> None:
    """验证逾期天数和金额的零值有效"""
    repository, _, add = create_repository()

    arguments: dict[str, Any] = {
        "outcome_id": "out_boundary",
        "subject_key": "customer_boundary",
        "outcome_time": EARLIER_TIME,
        field_name: value,
    }

    outcome = repository.create_outcome(
        **arguments
    )

    add.assert_called_once_with(
        outcome
    )
    assert getattr(
        outcome,
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
            "overdue_days",
            -1,
            "overdue_days 不能小于 0",
        ),
        (
            "amount",
            -0.01,
            "amount 不能小于 0",
        ),
    ],
)
def test_create_outcome_rejects_invalid_values(
        field_name: str,
        value: int | float,
        expected_message: str,
) -> None:
    """验证创建结果时拒绝非法数值"""
    repository, _, add = create_repository()

    arguments: dict[str, Any] = {
        "outcome_id": "out_invalid",
        "subject_key": "customer_invalid",
        field_name: value,
    }

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        repository.create_outcome(
            **arguments
        )

    add.assert_not_called()


# noinspection PyUnreachableCode
def test_update_outcome() -> None:
    """验证更新所有非空实验结果字段"""
    repository, _, _ = create_repository()
    outcome = create_outcome()

    result = repository.update_outcome(
        outcome,
        OutcomePatch(
            experiment_id="exp_new",
            variant_id="var_new",
            assignment_id="asn_new",
            decision_id="dcs_new",
            request_id="req_new",
            subject_key="customer_new",
            subject_type="application",
            approved=False,
            converted=False,
            defaulted=True,
            overdue_days=35,
            amount=8000.0,
            label="bad",
            context={
                "observation_window_days": 90,
            },
            outcome_time=LATER_TIME,
        ),
    )

    assert result is outcome
    assert outcome.experiment_id == "exp_new"
    assert outcome.variant_id == "var_new"
    assert outcome.assignment_id == "asn_new"
    assert outcome.decision_id == "dcs_new"
    assert outcome.request_id == "req_new"
    assert outcome.subject_key == "customer_new"
    assert outcome.subject_type == "application"
    assert outcome.approved is False
    assert outcome.converted is False
    assert outcome.defaulted is True
    assert outcome.overdue_days == 35
    assert outcome.amount == 8000.0
    assert outcome.label == "bad"
    assert outcome.context == {
        "observation_window_days": 90,
    }
    assert outcome.outcome_time == LATER_TIME


# noinspection PyUnreachableCode
def test_update_outcome_ignores_none_fields() -> None:
    """验证值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    outcome = create_outcome()

    result = repository.update_outcome(
        outcome,
        OutcomePatch(),
    )

    assert result is outcome
    assert outcome.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert outcome.subject_key == (
        "customer_10001"
    )
    assert outcome.approved is True
    assert outcome.defaulted is False
    assert outcome.overdue_days == 0
    assert outcome.amount == 10000.0
    assert outcome.label == "good"


# noinspection PyUnreachableCode
def test_update_outcome_accepts_false_zero_and_empty_string() -> None:
    """验证 False、零值和空字符串会作为明确更新值写入"""
    repository, _, _ = create_repository()
    outcome = create_outcome(
        approved=True,
        converted=True,
        defaulted=True,
        overdue_days=35,
        amount=10000.0,
        label="bad",
    )

    repository.update_outcome(
        outcome,
        OutcomePatch(
            approved=False,
            converted=False,
            defaulted=False,
            overdue_days=0,
            amount=0.0,
            label="",
        ),
    )

    assert outcome.approved is False
    assert outcome.converted is False
    assert outcome.defaulted is False
    assert outcome.overdue_days == 0
    assert outcome.amount == 0.0
    assert outcome.label == ""


@pytest.mark.parametrize(
    (
        "patch",
        "expected_message",
    ),
    [
        (
            OutcomePatch(
                overdue_days=-1,
                amount=5000.0,
                label="new",
            ),
            "overdue_days 不能小于 0",
        ),
        (
            OutcomePatch(
                overdue_days=10,
                amount=-0.01,
                label="new",
            ),
            "amount 不能小于 0",
        ),
    ],
)
def test_update_outcome_rejects_invalid_values_without_mutation(
        patch: OutcomePatch,
        expected_message: str,
) -> None:
    """验证更新时拒绝非法数值且不修改对象"""
    repository, _, _ = create_repository()
    outcome = create_outcome()
    original_overdue_days = (
        outcome.overdue_days
    )
    original_amount = outcome.amount
    original_label = outcome.label

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        repository.update_outcome(
            outcome,
            patch,
        )

    assert (
        outcome.overdue_days
        == original_overdue_days
    )
    assert outcome.amount == original_amount
    assert outcome.label == original_label
