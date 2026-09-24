"""审计日志仓储测试.

验证 AuditRepository 的审计日志查询、显式筛选、排序、分页、
辅助列表方法，以及不可变审计记录的创建和字段校验。

核心功能：
  - test_list_audits:
    验证审计字段筛选、排序和分页
  - test_list_entity_history:
    验证实体变更历史按时间升序排列
  - test_list_failed_operations:
    验证获取失败操作记录
  - test_list_user_actions:
    验证获取用户操作记录
  - test_get_by_audit_id:
    验证按唯一审计 ID 获取记录
  - test_create_audit:
    验证创建审计日志
  - test_create_audit_enum_values:
    验证来源和状态枚举写入
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

import datamind.db.repositories.audit as audit_module
from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.db.models.audit import Audit
from datamind.db.repositories.audit import AuditRepository


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    16,
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


def create_audit(
        **overrides: Any,
) -> Audit:
    """创建审计日志测试对象."""
    values: dict[str, Any] = {
        "audit_id": "aud_0123456789abcdef",
        "action": "model.register",
        "resource": "model",
        "operation": "register",
        "target_type": "model",
        "target_id": "mdl_0123456789abcdef",
        "source": "cli",
        "trace_id": (
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        "request_id": "req_0123456789abcdef",
        "user": "admin",
        "ip": "192.168.1.100",
        "hostname": "client",
        "status": "success",
        "error": None,
        "before": None,
        "after": {
            "name": "scorecard",
        },
        "context": {
            "operator": "admin",
        },
        "occurred_at": EARLIER_TIME,
    }
    values.update(
        overrides
    )

    return Audit(
        **values
    )


def create_repository(
        *,
        list_result: list[Audit] | None = None,
) -> tuple[
    AuditRepository,
    AsyncMock,
    MagicMock,
]:
    """创建审计仓储及会话方法替身."""
    result = MagicMock()

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
    repository = AuditRepository(
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
    """获取异步会话执行的查询语句."""
    awaited_call = execute.await_args

    assert awaited_call is not None

    return cast(
        Select[Any],
        awaited_call.args[
            0
        ],
    )


@pytest.mark.asyncio
async def test_get_by_audit_id() -> None:
    """测试按唯一审计 ID 查询单条记录."""
    audit = create_audit()
    repository, execute, _add = create_repository()
    result = execute.return_value
    result.scalar_one_or_none.return_value = audit

    actual = await repository.get_by_audit_id(audit.audit_id)

    assert actual is audit
    statement = get_executed_statement(execute)
    sql = compile_statement(statement)
    assert "audit.audit_id =" in sql


def compile_statement(
        statement: Select[Any],
) -> str:
    """将查询语句编译为 PostgreSQL SQL."""
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True,
            },
        )
    )


@pytest.mark.asyncio
async def test_list_audits_without_filters() -> None:
    """测试无筛选时返回全部日志并按时间倒序."""
    audits = [
        create_audit()
    ]
    repository, execute, _ = create_repository(
        list_result=audits
    )

    result = await repository.list_audits()

    assert result == audits

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY audit.occurred_at DESC, "
        "audit.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_audits_applies_filters_and_pagination() -> None:
    """测试全部审计字段筛选、排序和分页."""
    audits = [
        create_audit(
            status="failed",
            error="permission denied",
        )
    ]
    repository, execute, _ = create_repository(
        list_result=audits
    )

    result = await repository.list_audits(
        audit_id="aud_0123456789abcdef",
        action="model.register",
        resource="model",
        operation="register",
        target_type="model",
        target_id="mdl_0123456789abcdef",
        source=AuditSource.CLI,
        trace_id=(
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        request_id="req_0123456789abcdef",
        user="admin",
        ip="192.168.1.100",
        hostname="client",
        status=AuditStatus.FAILED,
        limit=25,
        offset=10,
        order_desc=True,
    )

    assert result == audits

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "audit.audit_id = "
        "'aud_0123456789abcdef'"
        in sql
    )
    assert (
        "audit.action = 'model.register'"
        in sql
    )
    assert "audit.resource = 'model'" in sql
    assert (
        "audit.operation = 'register'"
        in sql
    )
    assert (
        "audit.target_type = 'model'"
        in sql
    )
    assert (
        "audit.target_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert "audit.source = 'cli'" in sql
    assert (
        "audit.trace_id = "
        "'0123456789abcdef0123456789abcdef'"
        in sql
    )
    assert (
        "audit.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )
    assert (
        'audit."user" = \'admin\''
        in sql
    )
    assert (
        "audit.ip = '192.168.1.100'"
        in sql
    )
    assert (
        "audit.hostname = 'client'"
        in sql
    )
    assert "audit.status = 'failed'" in sql
    assert (
        "ORDER BY audit.occurred_at DESC, "
        "audit.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_audits_orders_ascending() -> None:
    """测试审计日志支持按时间升序排列."""
    repository, execute, _ = create_repository()

    await repository.list_audits(
        order_desc=False
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY audit.occurred_at ASC, "
        "audit.created_at ASC"
        in sql
    )


@pytest.mark.asyncio
async def test_list_audits_applies_zero_pagination() -> None:
    """测试零值分页参数仍会应用."""
    repository, execute, _ = create_repository()

    await repository.list_audits(
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
            "list_audits",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_audits",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_failed_operations",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_user_actions",
            {
                "user": "admin",
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
    """测试审计列表方法拒绝负数分页参数."""
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
async def test_list_entity_history() -> None:
    """测试实体变更历史使用目标筛选和升序排列."""
    audits = [
        create_audit()
    ]
    repository, execute, _ = create_repository(
        list_result=audits
    )

    result = await repository.list_entity_history(
        "model",
        "mdl_0123456789abcdef",
    )

    assert result == audits

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "audit.target_type = 'model'"
        in sql
    )
    assert (
        "audit.target_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "ORDER BY audit.occurred_at ASC, "
        "audit.created_at ASC"
        in sql
    )
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_failed_operations_uses_default_limit() -> None:
    """测试失败操作默认返回 100 条."""
    audits = [
        create_audit(
            status="failed"
        )
    ]
    repository, execute, _ = create_repository(
        list_result=audits
    )

    result = await repository.list_failed_operations()

    assert result == audits

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "audit.status = 'failed'" in sql
    assert (
        "ORDER BY audit.occurred_at DESC, "
        "audit.created_at DESC"
        in sql
    )
    assert "LIMIT 100" in sql


@pytest.mark.asyncio
async def test_list_failed_operations_accepts_custom_pagination() -> None:
    """测试失败操作支持自定义分页."""
    repository, execute, _ = create_repository()

    await repository.list_failed_operations(
        limit=20,
        offset=5,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "audit.status = 'failed'" in sql
    assert "LIMIT 20" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_list_user_actions_uses_default_limit() -> None:
    """测试用户操作默认返回 100 条."""
    audits = [
        create_audit()
    ]
    repository, execute, _ = create_repository(
        list_result=audits
    )

    result = await repository.list_user_actions(
        "admin"
    )

    assert result == audits

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        'audit."user" = \'admin\''
        in sql
    )
    assert (
        "ORDER BY audit.occurred_at DESC, "
        "audit.created_at DESC"
        in sql
    )
    assert "LIMIT 100" in sql


@pytest.mark.asyncio
async def test_list_user_actions_accepts_custom_pagination() -> None:
    """测试用户操作支持自定义分页."""
    repository, execute, _ = create_repository()

    await repository.list_user_actions(
        "admin",
        limit=20,
        offset=5,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        'audit."user" = \'admin\''
        in sql
    )
    assert "LIMIT 20" in sql
    assert "OFFSET 5" in sql


def test_create_audit() -> None:
    """测试创建完整审计日志."""
    repository, _, add = create_repository()

    audit = repository.create_audit(
        audit_id="aud_0123456789abcdef",
        action="model.register",
        resource="model",
        operation="register",
        target_type="model",
        target_id="mdl_0123456789abcdef",
        source=AuditSource.CLI,
        trace_id=(
            "0123456789abcdef"
            "0123456789abcdef"
        ),
        request_id="req_0123456789abcdef",
        user="admin",
        ip="192.168.1.100",
        hostname="client",
        status=AuditStatus.FAILED,
        error="permission denied",
        before={
            "status": "inactive",
        },
        after={
            "status": "active",
        },
        context={
            "operator": "admin",
        },
        occurred_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        audit
    )
    assert audit.audit_id == (
        "aud_0123456789abcdef"
    )
    assert audit.action == "model.register"
    assert audit.resource == "model"
    assert audit.operation == "register"
    assert audit.target_type == "model"
    assert audit.target_id == (
        "mdl_0123456789abcdef"
    )
    assert audit.source == "cli"
    assert audit.trace_id == (
        "0123456789abcdef"
        "0123456789abcdef"
    )
    assert audit.request_id == (
        "req_0123456789abcdef"
    )
    assert audit.user == "admin"
    assert audit.ip == "192.168.1.100"
    assert audit.hostname == "client"
    assert audit.status == "failed"
    assert audit.error == "permission denied"
    assert audit.before == {
        "status": "inactive",
    }
    assert audit.after == {
        "status": "active",
    }
    assert audit.context == {
        "operator": "admin",
    }
    assert audit.occurred_at == EARLIER_TIME


# noinspection PyUnreachableCode
def test_create_audit_uses_optional_defaults(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建审计日志的默认状态和当前时间."""
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
        vars(audit_module),
        "datetime",
        FrozenDateTime,
    )

    audit = repository.create_audit(
        audit_id="aud_minimum",
        action="system.start",
        resource="system",
        operation="start",
        target_type="service",
        target_id="datamind",
        source=AuditSource.SYSTEM,
    )

    add.assert_called_once_with(
        audit
    )
    assert audit.source == "system"
    assert audit.trace_id is None
    assert audit.request_id is None
    assert audit.user is None
    assert audit.ip is None
    assert audit.hostname is None
    assert audit.status == "success"
    assert audit.error is None
    assert audit.before is None
    assert audit.after is None
    assert audit.context is None
    assert audit.occurred_at == CURRENT_TIME


@pytest.mark.parametrize(
    "source",
    list(
        AuditSource
    ),
)
def test_create_audit_accepts_valid_sources(
        source: AuditSource,
) -> None:
    """测试创建审计日志接受全部合法来源."""
    repository, _, add = create_repository()

    audit = repository.create_audit(
        audit_id=f"aud_{source}",
        action="system.test",
        resource="system",
        operation="test",
        target_type="service",
        target_id="datamind",
        source=source,
        occurred_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        audit
    )
    assert audit.source == str(
        source
    )


@pytest.mark.parametrize(
    "status",
    list(
        AuditStatus
    ),
)
def test_create_audit_accepts_valid_statuses(
        status: AuditStatus,
) -> None:
    """测试创建审计日志接受全部合法状态."""
    repository, _, add = create_repository()

    audit = repository.create_audit(
        audit_id=f"aud_{status}",
        action="system.test",
        resource="system",
        operation="test",
        target_type="service",
        target_id="datamind",
        source=AuditSource.SYSTEM,
        status=status,
        occurred_at=EARLIER_TIME,
    )

    add.assert_called_once_with(
        audit
    )
    assert audit.status == str(
        status
    )
