"""实验分配仓储测试

验证 AssignmentRepository 的固定分配查询、列表筛选、
辅助列表方法，以及实验分配记录的创建和字段校验。

核心功能：
  - test_get_assignment:
    验证按分配 ID 查询
  - test_get_subject_assignment:
    验证获取主体在实验中的固定分配
  - test_list_assignments:
    验证分配策略、主体字段、排序和分页
  - test_list_experiment_assignments:
    验证获取实验分配记录
  - test_list_variant_assignments:
    验证获取实验分组分配记录
  - test_list_subject_assignments:
    验证获取主体参与的实验分配记录
  - test_create_assignment:
    验证创建实验分配记录
  - test_get_or_create_assignment:
    验证原子获取或创建固定分配
  - test_create_assignment_weight:
    验证分配权重范围
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

import datamind.db.repositories.assignment as assignment_module
from datamind.db.models.assignments import Assignment
from datamind.db.repositories.assignment import AssignmentRepository
from datamind.models.enums import AssignmentStrategy


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    13,
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


def create_assignment(
        **overrides: Any,
) -> Assignment:
    """创建实验分配测试对象"""
    values: dict[str, Any] = {
        "assignment_id": "asn_0123456789abcdef",
        "experiment_id": "exp_0123456789abcdef",
        "variant_id": "var_0123456789abcdef",
        "subject_key": "customer_10001",
        "subject_type": "customer",
        "strategy": str(
            AssignmentStrategy.HASH
        ),
        "bucket": "bucket_0123",
        "weight": 0.5,
        "context": {
            "group": "treatment",
        },
        "assigned_at": EARLIER_TIME,
    }
    values.update(
        overrides
    )

    return Assignment(
        **values
    )


def create_repository(
        *,
        scalar_result: Assignment | None = None,
        list_result: list[Assignment] | None = None,
) -> tuple[
    AssignmentRepository,
    AsyncMock,
    MagicMock,
]:
    """创建实验分配仓储及会话方法替身"""
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
    repository = AssignmentRepository(
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
async def test_get_assignment() -> None:
    """验证按分配 ID 查询"""
    expected = create_assignment()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_assignment(
        "asn_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.assignment_id = "
        "'asn_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_assignment_returns_none_when_not_found() -> None:
    """验证分配记录不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_assignment(
        "asn_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_subject_assignment() -> None:
    """验证获取主体在实验中的固定分配"""
    expected = create_assignment()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_subject_assignment(
        experiment_id="exp_0123456789abcdef",
        subject_key="customer_10001",
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "assignments.subject_key = "
        "'customer_10001'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_subject_assignment_returns_none() -> None:
    """验证主体没有固定分配时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_subject_assignment(
        experiment_id="exp_missing",
        subject_key="customer_missing",
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_assignments_without_filters() -> None:
    """验证无筛选时返回全部记录并按时间倒序"""
    assignments = [
        create_assignment()
    ]
    repository, execute, _ = create_repository(
        list_result=assignments
    )

    result = await repository.list_assignments()

    assert result == assignments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY assignments.assigned_at DESC, "
        "assignments.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_assignments_applies_filters_and_pagination() -> None:
    """验证策略、主体字段、普通字段筛选和分页"""
    assignments = [
        create_assignment(
            strategy=str(
                AssignmentStrategy.MANUAL
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=assignments
    )

    result = await repository.list_assignments(
        assignment_id="asn_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        strategy=AssignmentStrategy.MANUAL,
        bucket="bucket_0123",
        limit=25,
        offset=10,
    )

    assert result == assignments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.assignment_id = "
        "'asn_0123456789abcdef'"
        in sql
    )
    assert (
        "assignments.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "assignments.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )
    assert (
        "assignments.subject_key = "
        "'customer_10001'"
        in sql
    )
    assert (
        "assignments.subject_type = 'customer'"
        in sql
    )
    assert (
        "assignments.strategy = 'manual'"
        in sql
    )
    assert (
        "assignments.bucket = 'bucket_0123'"
        in sql
    )
    assert (
        "ORDER BY assignments.assigned_at DESC, "
        "assignments.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_assignments_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_assignments(
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
            "list_assignments",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_assignments",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_experiment_assignments",
            {
                "experiment_id": "exp_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_variant_assignments",
            {
                "variant_id": "var_test",
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_subject_assignments",
            {
                "subject_key": "customer_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
    ],
)
async def test_list_methods_reject_negative_pagination(
        method_name: str,
        arguments: dict[str, Any],
        expected_message: str,
) -> None:
    """验证分配列表方法拒绝负数分页参数"""
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
async def test_list_experiment_assignments() -> None:
    """验证获取实验分配记录"""
    assignments = [
        create_assignment()
    ]
    repository, execute, _ = create_repository(
        list_result=assignments
    )

    result = await repository.list_experiment_assignments(
        "exp_0123456789abcdef",
        limit=50,
        offset=5,
    )

    assert result == assignments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_list_variant_assignments() -> None:
    """验证获取实验分组分配记录"""
    assignments = [
        create_assignment()
    ]
    repository, execute, _ = create_repository(
        list_result=assignments
    )

    result = await repository.list_variant_assignments(
        "var_0123456789abcdef",
        limit=50,
        offset=5,
    )

    assert result == assignments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_list_subject_assignments() -> None:
    """验证获取主体参与的实验分配记录"""
    assignments = [
        create_assignment()
    ]
    repository, execute, _ = create_repository(
        list_result=assignments
    )

    result = await repository.list_subject_assignments(
        "customer_10001",
        limit=50,
        offset=5,
    )

    assert result == assignments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "assignments.subject_key = "
        "'customer_10001'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_create_assignment() -> None:
    """验证创建完整实验分配记录"""
    repository, _, add = create_repository()

    assignment = repository.create_assignment(
        assignment_id="asn_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        variant_id="var_0123456789abcdef",
        subject_key="customer_10001",
        subject_type="customer",
        strategy=AssignmentStrategy.MANUAL,
        bucket="bucket_0123",
        weight=0.5,
        context={
            "group": "treatment",
        },
        assigned_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        assignment
    )
    assert assignment.assignment_id == (
        "asn_0123456789abcdef"
    )
    assert assignment.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert assignment.variant_id == (
        "var_0123456789abcdef"
    )
    assert assignment.subject_key == (
        "customer_10001"
    )
    assert assignment.subject_type == "customer"
    assert assignment.strategy == "manual"
    assert assignment.bucket == "bucket_0123"
    assert assignment.weight == 0.5
    assert assignment.context == {
        "group": "treatment",
    }
    assert assignment.assigned_at == EARLIER_TIME


# noinspection PyUnreachableCode
def test_create_assignment_uses_optional_defaults(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证创建分配记录的默认策略和当前时间"""
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
        vars(assignment_module),
        "datetime",
        FrozenDateTime,
    )

    assignment = repository.create_assignment(
        assignment_id="asn_minimum",
        experiment_id="exp_minimum",
        variant_id="var_minimum",
        subject_key="customer_minimum",
    )

    add.assert_called_once_with(
        assignment
    )
    assert assignment.subject_type is None
    assert assignment.strategy == "hash"
    assert assignment.bucket is None
    assert assignment.weight is None
    assert assignment.context is None
    assert assignment.assigned_at == CURRENT_TIME


@pytest.mark.parametrize(
    "weight",
    [
        0.0,
        1.0,
    ],
)
def test_create_assignment_accepts_boundary_weight(
        weight: float,
) -> None:
    """验证分配权重边界值有效"""
    repository, _, add = create_repository()

    assignment = repository.create_assignment(
        assignment_id="asn_boundary",
        experiment_id="exp_boundary",
        variant_id="var_boundary",
        subject_key="customer_boundary",
        weight=weight,
        assigned_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        assignment
    )
    assert assignment.weight == weight


# noinspection PyUnreachableCode
def test_create_assignment_accepts_none_weight() -> None:
    """验证分配权重允许为空"""
    repository, _, add = create_repository()

    assignment = repository.create_assignment(
        assignment_id="asn_none_weight",
        experiment_id="exp_none_weight",
        variant_id="var_none_weight",
        subject_key="customer_none_weight",
        weight=None,
        assigned_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        assignment
    )
    assert assignment.weight is None


@pytest.mark.parametrize(
    "weight",
    [
        -0.01,
        1.01,
    ],
)
def test_create_assignment_rejects_invalid_weight(
        weight: float,
) -> None:
    """验证创建时拒绝非法分配权重"""
    repository, _, add = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "实验分配 weight 必须在 0 到 1 之间"
            ),
    ):
        repository.create_assignment(
            assignment_id="asn_invalid",
            experiment_id="exp_invalid",
            variant_id="var_invalid",
            subject_key="customer_invalid",
            weight=weight,
        )

    add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_assignment_returns_created_record() -> None:
    """验证原子写入成功时返回新固定分配"""
    expected = create_assignment()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    assignment, created = await repository.get_or_create_assignment(
        assignment_id=expected.assignment_id,
        experiment_id=expected.experiment_id,
        variant_id=expected.variant_id,
        subject_key=expected.subject_key,
        strategy=AssignmentStrategy.HASH,
        weight=expected.weight,
        assigned_at=EARLIER_TIME,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None

    stmt = awaited_call.args[0]
    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
        )
    )

    assert assignment is expected
    assert created is True
    assert "ON CONFLICT (experiment_id, subject_key) DO NOTHING" in sql


@pytest.mark.asyncio
async def test_get_or_create_assignment_returns_concurrent_record() -> None:
    """验证并发冲突时返回数据库中的已有固定分配"""
    existing = create_assignment(
        assignment_id="asn_existing",
        variant_id="var_existing",
    )
    insert_result = MagicMock()
    insert_result.scalar_one_or_none.return_value = None
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = existing
    session_mock = MagicMock(spec=AsyncSession)
    session_mock.execute = AsyncMock(
        side_effect=[insert_result, select_result]
    )
    repository = AssignmentRepository(
        cast(AsyncSession, session_mock)
    )

    assignment, created = await repository.get_or_create_assignment(
        assignment_id="asn_candidate",
        experiment_id=existing.experiment_id,
        variant_id="var_candidate",
        subject_key=existing.subject_key,
        assigned_at=EARLIER_TIME,
    )

    assert assignment is existing
    assert created is False
    assert session_mock.execute.await_count == 2
