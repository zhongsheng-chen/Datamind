"""模型运行控制仓储测试

验证 ControlRepository 的控制记录查询、列表筛选、创建，
以及 loaded、unloaded 和 reload 操作的 generation 管理。

核心功能：
  - test_get_control:
    验证按控制 ID 查询
  - test_get_deployment_control:
    验证按部署 ID 查询
  - test_list_controls:
    验证环境、状态、审计字段筛选和分页
  - test_list_loaded_controls:
    验证获取期望加载的控制记录
  - test_create_control:
    验证创建控制记录并设置初始状态
  - test_set_loaded:
    验证加载状态和 generation 变化
  - test_set_unloaded:
    验证卸载状态和 generation 变化
  - test_request_reload:
    验证重新加载请求和状态限制
"""

from typing import (
    Any,
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

from datamind.constants import Environment
from datamind.db.models.controls import Control
from datamind.db.repositories.control import ControlRepository
from datamind.models.enums import RuntimeControlStatus


def create_control(
        **overrides: Any,
) -> Control:
    """创建运行控制测试对象"""
    values: dict[str, Any] = {
        "control_id": "ctl_0123456789abcdef",
        "deployment_id": "dep_0123456789abcdef",
        "environment": "production",
        "desired_status": str(
            RuntimeControlStatus.UNLOADED
        ),
        "generation": 1,
        "created_by": "creator",
        "updated_by": "original_operator",
    }
    values.update(
        overrides
    )

    return Control(
        **values
    )


def create_repository(
        *,
        scalar_result: Control | None = None,
        list_result: list[Control] | None = None,
) -> tuple[
    ControlRepository,
    AsyncMock,
    MagicMock,
]:
    """创建运行控制仓储及会话方法替身"""
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
    repository = ControlRepository(
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
async def test_get_control() -> None:
    """验证按控制 ID 查询"""
    expected = create_control()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_control(
        "ctl_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "controls.control_id = "
        "'ctl_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_control_returns_none_when_not_found() -> None:
    """验证控制记录不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_control(
        "ctl_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_deployment_control() -> None:
    """验证按部署 ID 查询控制记录"""
    expected = create_control()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_deployment_control(
        "dep_0123456789abcdef"
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "controls.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_deployment_control_returns_none() -> None:
    """验证部署没有控制记录时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_deployment_control(
        "dep_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_controls_without_filters() -> None:
    """验证无筛选时返回全部记录并按时间倒序"""
    controls = [
        create_control()
    ]
    repository, execute, _ = create_repository(
        list_result=controls
    )

    result = await repository.list_controls()

    assert result == controls

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY controls.updated_at DESC, "
        "controls.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_controls_applies_filters_and_pagination() -> None:
    """验证环境、状态、审计字段筛选和分页"""
    controls = [
        create_control(
            environment="staging",
            desired_status=str(
                RuntimeControlStatus.LOADED
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=controls
    )

    result = await repository.list_controls(
        control_id="ctl_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        environment=Environment.STAGING,
        desired_status=RuntimeControlStatus.LOADED,
        created_by="creator",
        updated_by="operator",
        limit=25,
        offset=10,
    )

    assert result == controls

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "controls.control_id = "
        "'ctl_0123456789abcdef'"
        in sql
    )
    assert (
        "controls.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "controls.environment = 'staging'"
        in sql
    )
    assert (
        "controls.desired_status = 'loaded'"
        in sql
    )
    assert (
        "controls.created_by = 'creator'"
        in sql
    )
    assert (
        "controls.updated_by = 'operator'"
        in sql
    )
    assert (
        "ORDER BY controls.updated_at DESC, "
        "controls.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_controls_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_controls(
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
async def test_list_controls_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """验证拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_controls(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_loaded_controls() -> None:
    """验证获取指定环境中期望加载的控制记录"""
    controls = [
        create_control(
            environment="production",
            desired_status=str(
                RuntimeControlStatus.LOADED
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=controls
    )

    result = await repository.list_loaded_controls(
        environment=Environment.PRODUCTION,
        limit=50,
        offset=5,
    )

    assert result == controls

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "controls.environment = 'production'"
        in sql
    )
    assert (
        "controls.desired_status = 'loaded'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_create_control() -> None:
    """验证创建控制记录并设置初始状态"""
    repository, _, add = create_repository()

    control = repository.create_control(
        control_id="ctl_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        environment=Environment.PRODUCTION,
        created_by="creator",
    )

    add.assert_called_once_with(
        control
    )
    assert control.control_id == (
        "ctl_0123456789abcdef"
    )
    assert control.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert control.environment == "production"
    assert control.desired_status == str(
        RuntimeControlStatus.UNLOADED
    )
    assert control.generation == 1
    assert control.created_by == "creator"
    assert control.updated_by == "creator"


# noinspection PyUnreachableCode
def test_create_control_allows_missing_creator() -> None:
    """验证创建控制记录时允许省略创建人"""
    repository, _, add = create_repository()

    control = repository.create_control(
        control_id="ctl_minimum",
        deployment_id="dep_minimum",
        environment=Environment.TESTING,
    )

    add.assert_called_once_with(
        control
    )
    assert control.environment == "testing"
    assert control.desired_status == str(
        RuntimeControlStatus.UNLOADED
    )
    assert control.generation == 1
    assert control.created_by is None
    assert control.updated_by is None


def test_set_loaded() -> None:
    """验证从 unloaded 设置为 loaded"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.UNLOADED
        ),
        generation=3,
    )

    result = repository.set_loaded(
        control,
        updated_by="operator",
    )

    assert result is control
    assert control.desired_status == str(
        RuntimeControlStatus.LOADED
    )
    assert control.generation == 4
    assert control.updated_by == "operator"


def test_set_loaded_without_operator() -> None:
    """验证加载时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    control = create_control(
        generation=3,
        updated_by="original_operator",
    )

    repository.set_loaded(
        control
    )

    assert control.desired_status == str(
        RuntimeControlStatus.LOADED
    )
    assert control.generation == 4
    assert control.updated_by == (
        "original_operator"
    )


def test_set_loaded_accepts_empty_operator() -> None:
    """验证加载时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    control = create_control()

    repository.set_loaded(
        control,
        updated_by="",
    )

    assert control.updated_by == ""


def test_set_loaded_is_idempotent() -> None:
    """验证重复设置 loaded 保持幂等"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        ),
        generation=5,
        updated_by="original_operator",
    )

    result = repository.set_loaded(
        control,
        updated_by="new_operator",
    )

    assert result is control
    assert control.desired_status == str(
        RuntimeControlStatus.LOADED
    )
    assert control.generation == 5
    assert control.updated_by == (
        "original_operator"
    )


def test_set_unloaded() -> None:
    """验证从 loaded 设置为 unloaded"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        ),
        generation=6,
    )

    result = repository.set_unloaded(
        control,
        updated_by="operator",
    )

    assert result is control
    assert control.desired_status == str(
        RuntimeControlStatus.UNLOADED
    )
    assert control.generation == 7
    assert control.updated_by == "operator"


def test_set_unloaded_without_operator() -> None:
    """验证卸载时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        ),
        generation=6,
        updated_by="original_operator",
    )

    repository.set_unloaded(
        control
    )

    assert control.desired_status == str(
        RuntimeControlStatus.UNLOADED
    )
    assert control.generation == 7
    assert control.updated_by == (
        "original_operator"
    )


def test_set_unloaded_accepts_empty_operator() -> None:
    """验证卸载时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        )
    )

    repository.set_unloaded(
        control,
        updated_by="",
    )

    assert control.updated_by == ""


def test_set_unloaded_is_idempotent() -> None:
    """验证重复设置 unloaded 保持幂等"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.UNLOADED
        ),
        generation=8,
        updated_by="original_operator",
    )

    result = repository.set_unloaded(
        control,
        updated_by="new_operator",
    )

    assert result is control
    assert control.desired_status == str(
        RuntimeControlStatus.UNLOADED
    )
    assert control.generation == 8
    assert control.updated_by == (
        "original_operator"
    )


def test_request_reload() -> None:
    """验证 loaded 状态可以请求重新加载"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        ),
        generation=9,
    )

    result = repository.request_reload(
        control,
        updated_by="operator",
    )

    assert result is control
    assert control.desired_status == str(
        RuntimeControlStatus.LOADED
    )
    assert control.generation == 10
    assert control.updated_by == "operator"


def test_request_reload_without_operator() -> None:
    """验证重新加载时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        ),
        generation=9,
        updated_by="original_operator",
    )

    repository.request_reload(
        control
    )

    assert control.generation == 10
    assert control.updated_by == (
        "original_operator"
    )


def test_request_reload_accepts_empty_operator() -> None:
    """验证重新加载时允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=str(
            RuntimeControlStatus.LOADED
        )
    )

    repository.request_reload(
        control,
        updated_by="",
    )

    assert control.updated_by == ""


@pytest.mark.parametrize(
    "desired_status",
    [
        str(
            RuntimeControlStatus.UNLOADED
        ),
        "unknown",
    ],
)
def test_request_reload_rejects_non_loaded_status(
        desired_status: str,
) -> None:
    """验证非 loaded 状态不能请求重新加载"""
    repository, _, _ = create_repository()
    control = create_control(
        desired_status=desired_status,
        generation=11,
        updated_by="original_operator",
    )

    with pytest.raises(
            ValueError,
            match=(
                "只有期望状态为 loaded 的部署"
                "才能执行 reload"
            ),
    ):
        repository.request_reload(
            control,
            updated_by="operator",
        )

    assert control.desired_status == desired_status
    assert control.generation == 11
    assert control.updated_by == (
        "original_operator"
    )
