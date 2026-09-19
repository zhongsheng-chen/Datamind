"""模型运行仓储测试

验证 RuntimeRepository 的运行记录查询、列表筛选、创建、
普通字段更新，以及加载、卸载、失败和心跳状态管理。

核心功能：
  - test_get_runtime:
    验证按运行 ID 查询
  - test_get_deployment_runtime:
    验证按部署和 Worker 查询
  - test_list_runtimes:
    验证框架、状态、操作人筛选和分页
  - test_list_running_runtimes:
    验证获取已加载运行记录
  - test_mark_stale_runtimes_failed:
    验证失联活动实例自动收敛为失败
  - test_runtime_patch:
    验证更新结构和框架枚举
  - test_create_runtime:
    验证创建运行记录并设置 unloaded 状态
  - test_update_runtime:
    验证普通运行字段更新
  - test_set_applied_generation:
    验证持久化已应用控制版本号
  - test_mark_starting:
    验证标记加载中
  - test_mark_running:
    验证标记已加载
  - test_mark_stopped:
    验证标记已卸载
  - test_mark_failed:
    验证标记加载失败
  - test_heartbeat:
    验证更新运行心跳
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

import datamind.db.repositories.runtime as runtime_module
from datamind.constants import Framework
from datamind.db.models.runtimes import Runtime
from datamind.db.repositories.runtime import (
    RuntimePatch,
    RuntimeRepository,
)


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    12,
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
    7,
    25,
    8,
    0,
    tzinfo=timezone.utc,
)


def create_runtime(
        **overrides: Any,
) -> Runtime:
    """创建运行记录测试对象"""
    values: dict[str, Any] = {
        "runtime_id": "rtm_0123456789abcdef",
        "deployment_id": "dep_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "version_id": "ver_0123456789abcdef",
        "framework": "sklearn",
        "status": "stopped",
        "worker_id": "worker-1",
        "loaded_at": None,
        "unloaded_at": None,
        "started_by": "original_starter",
        "stopped_by": "original_stopper",
        "last_heartbeat_at": None,
        "applied_generation": None,
        "error": None,
        "context": {
            "environment": "production",
        },
    }
    values.update(
        overrides
    )

    return Runtime(
        **values
    )


def create_repository(
        *,
        scalar_result: Runtime | None = None,
        list_result: list[Runtime] | None = None,
) -> tuple[
    RuntimeRepository,
    AsyncMock,
    MagicMock,
]:
    """创建运行仓储及会话方法替身"""
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
    repository = RuntimeRepository(
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
async def test_get_runtime() -> None:
    """测试按运行 ID 查询"""
    expected = create_runtime()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_runtime(
        "rtm_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "runtimes.runtime_id = "
        "'rtm_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_runtime_returns_none_when_not_found() -> None:
    """测试运行记录不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_runtime(
        "rtm_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_deployment_runtime_uses_default_worker() -> None:
    """测试按部署 ID 和默认 Worker 查询"""
    expected = create_runtime(
        worker_id="default"
    )
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_deployment_runtime(
        "dep_0123456789abcdef"
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "runtimes.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.worker_id = 'default'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_deployment_runtime_uses_custom_worker() -> None:
    """测试按部署 ID 和指定 Worker 查询"""
    expected = create_runtime(
        worker_id="worker-2"
    )
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_deployment_runtime(
        "dep_0123456789abcdef",
        worker_id="worker-2",
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "runtimes.worker_id = 'worker-2'"
        in sql
    )


@pytest.mark.asyncio
async def test_list_runtimes_without_filters() -> None:
    """测试无筛选时返回全部记录并按时间倒序"""
    runtimes = [
        create_runtime()
    ]
    repository, execute, _ = create_repository(
        list_result=runtimes
    )

    result = await repository.list_runtimes()

    assert result == runtimes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY runtimes.updated_at DESC, "
        "runtimes.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_runtimes_applies_filters_and_pagination() -> None:
    """测试框架、状态、操作人筛选和分页"""
    runtimes = [
        create_runtime(
            framework="xgboost",
            status="running",
            worker_id="worker-2",
        )
    ]
    repository, execute, _ = create_repository(
        list_result=runtimes
    )

    result = await repository.list_runtimes(
        runtime_id="rtm_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        framework=Framework.XGBOOST,
        status="running",
        worker_id="worker-2",
        started_by="starter",
        stopped_by="stopper",
        limit=25,
        offset=10,
    )

    assert result == runtimes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "runtimes.runtime_id = "
        "'rtm_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.framework = 'xgboost'"
        in sql
    )
    assert "runtimes.status = 'running'" in sql
    assert (
        "runtimes.worker_id = 'worker-2'"
        in sql
    )
    assert (
        "runtimes.started_by = 'starter'"
        in sql
    )
    assert (
        "runtimes.stopped_by = 'stopper'"
        in sql
    )
    assert (
        "ORDER BY runtimes.updated_at DESC, "
        "runtimes.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_runtimes_applies_zero_pagination() -> None:
    """测试零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_runtimes(
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
async def test_list_runtimes_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """测试拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_runtimes(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_running_runtimes() -> None:
    """测试获取已加载运行记录"""
    runtimes = [
        create_runtime(
            framework="sklearn",
            status="running",
        )
    ]
    repository, execute, _ = create_repository(
        list_result=runtimes
    )

    result = await repository.list_running_runtimes(
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        framework=Framework.SKLEARN,
        worker_id="worker-1",
        limit=50,
        offset=5,
    )

    assert result == runtimes

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "runtimes.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )
    assert (
        "runtimes.framework = 'sklearn'"
        in sql
    )
    assert "runtimes.status = 'running'" in sql
    assert (
        "runtimes.worker_id = 'worker-1'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_mark_stale_runtimes_failed() -> None:
    """测试按环境和心跳期限收敛失联活动实例"""
    stale_runtime = create_runtime(
        status="running",
        worker_id="worker-stale",
    )
    repository, execute, _ = create_repository(
        list_result=[stale_runtime]
    )

    runtime_ids = await repository.mark_stale_runtimes_failed(
        environment="production",
        stale_before=CURRENT_TIME,
        exclude_worker_id="worker-current",
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    sql = str(
        awaited_call.args[0].compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "JOIN deployments" in sql
    assert "deployments.environment = 'production'" in sql
    assert "runtimes.status IN ('starting', 'running', 'stopping')" in sql
    assert "coalesce(runtimes.last_heartbeat_at, runtimes.updated_at)" in sql
    assert "runtimes.worker_id != 'worker-current'" in sql
    assert runtime_ids == ["rtm_0123456789abcdef"]
    assert stale_runtime.status == "failed"
    assert stale_runtime.error == "运行实例心跳超时，Worker 已失联"

def test_runtime_patch_fields_and_defaults() -> None:
    """测试更新结构字段和默认值"""
    patch = RuntimePatch()

    assert [
        field.name
        for field in fields(
            RuntimePatch
        )
    ] == [
        "framework",
        "worker_id",
        "applied_generation",
        "error",
        "context",
    ]
    assert patch.framework is None
    assert patch.worker_id is None
    assert patch.applied_generation is None
    assert patch.error is None
    assert patch.context is None
    assert not hasattr(
        patch,
        "status",
    )
    assert not hasattr(
        patch,
        "loaded_at",
    )
    assert not hasattr(
        patch,
        "unloaded_at",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_runtime_patch_accepts_framework_enum() -> None:
    """测试更新结构接受框架枚举"""
    patch = RuntimePatch(
        framework=Framework.XGBOOST
    )

    assert patch.framework is (
        Framework.XGBOOST
    )


@pytest.mark.asyncio
async def test_set_applied_generation() -> None:
    """测试按部署和 Worker 持久化已应用控制版本号"""
    runtime = create_runtime()
    repository, execute, _ = create_repository(
        scalar_result=runtime
    )

    result = await repository.set_applied_generation(
        deployment_id="dep_0123456789abcdef",
        worker_id="worker-1",
        generation=4,
    )

    awaited_call = execute.await_args
    assert awaited_call is not None
    statement = awaited_call.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={
                "literal_binds": True
            },
        )
    )
    assert "FROM runtimes" in sql
    assert (
        "runtimes.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert "runtimes.worker_id = 'worker-1'" in sql
    assert result is runtime
    assert runtime.applied_generation == 4


def test_create_runtime() -> None:
    """测试创建运行记录并显式设置 unloaded 状态"""
    repository, _, add = create_repository()

    runtime = repository.create_runtime(
        runtime_id="rtm_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version_id="ver_0123456789abcdef",
        framework=Framework.SKLEARN,
        worker_id="worker-1",
        loaded_at=EARLIER_TIME,
        unloaded_at=LATER_TIME,
        started_by="starter",
        stopped_by="stopper",
        last_heartbeat_at=LATER_TIME,
        applied_generation=3,
        error="previous error",
        context={
            "environment": "production",
        },
    )

    add.assert_called_once_with(
        runtime
    )
    assert runtime.runtime_id == (
        "rtm_0123456789abcdef"
    )
    assert runtime.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert runtime.model_id == (
        "mdl_0123456789abcdef"
    )
    assert runtime.version_id == (
        "ver_0123456789abcdef"
    )
    assert runtime.framework == "sklearn"
    assert runtime.status == "stopped"
    assert runtime.worker_id == "worker-1"
    assert runtime.loaded_at == EARLIER_TIME
    assert runtime.unloaded_at == LATER_TIME
    assert runtime.started_by == "starter"
    assert runtime.stopped_by == "stopper"
    assert (
        runtime.last_heartbeat_at
        == LATER_TIME
    )
    assert runtime.applied_generation == 3
    assert runtime.error == "previous error"
    assert runtime.context == {
        "environment": "production",
    }


# noinspection PyUnreachableCode
def test_create_runtime_uses_optional_defaults() -> None:
    """测试创建运行记录的可选默认值"""
    repository, _, add = create_repository()

    runtime = repository.create_runtime(
        runtime_id="rtm_minimum",
        deployment_id="dep_minimum",
        model_id="mdl_minimum",
        version_id="ver_minimum",
        framework=Framework.SKLEARN,
    )

    add.assert_called_once_with(
        runtime
    )
    assert runtime.framework == "sklearn"
    assert runtime.status == "stopped"
    assert runtime.worker_id == "default"
    assert runtime.loaded_at is None
    assert runtime.unloaded_at is None
    assert runtime.started_by is None
    assert runtime.stopped_by is None
    assert runtime.last_heartbeat_at is None
    assert runtime.applied_generation is None
    assert runtime.error is None
    assert runtime.context is None


def test_update_runtime() -> None:
    """测试更新所有非空普通运行字段"""
    repository, _, _ = create_repository()
    runtime = create_runtime()
    original_status = runtime.status
    original_loaded_at = runtime.loaded_at
    original_unloaded_at = runtime.unloaded_at

    result = repository.update_runtime(
        runtime,
        RuntimePatch(
            framework=Framework.XGBOOST,
            worker_id="worker-2",
            applied_generation=4,
            error="runtime warning",
            context={
                "environment": "staging",
            },
        ),
    )

    assert result is runtime
    assert runtime.framework == "xgboost"
    assert runtime.worker_id == "worker-2"
    assert runtime.applied_generation == 4
    assert runtime.error == "runtime warning"
    assert runtime.context == {
        "environment": "staging",
    }
    assert runtime.status == original_status
    assert runtime.loaded_at == original_loaded_at
    assert (
        runtime.unloaded_at
        == original_unloaded_at
    )


def test_update_runtime_ignores_none_fields() -> None:
    """测试值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        applied_generation=3,
        error="original error",
    )

    result = repository.update_runtime(
        runtime,
        RuntimePatch(),
    )

    assert result is runtime
    assert runtime.framework == "sklearn"
    assert runtime.worker_id == "worker-1"
    assert runtime.applied_generation == 3
    assert runtime.error == "original error"


# noinspection PyUnreachableCode
def test_mark_starting() -> None:
    """测试标记加载中并清理旧错误和卸载时间"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="failed",
        error="load failed",
        unloaded_at=LATER_TIME,
    )

    result = repository.mark_starting(
        runtime,
        started_by="operator",
        context={
            "attempt": 2,
        },
    )

    assert result is runtime
    assert runtime.status == "starting"
    assert runtime.error is None
    assert runtime.unloaded_at is None
    assert runtime.started_by == "operator"
    assert runtime.context == {
        "attempt": 2,
    }


def test_mark_starting_accepts_empty_operator() -> None:
    """测试加载中状态允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    runtime = create_runtime()

    repository.mark_starting(
        runtime,
        started_by="",
    )

    assert runtime.started_by == ""


# noinspection PyUnreachableCode
def test_mark_running_with_explicit_time() -> None:
    """测试标记已加载并同步首次心跳时间"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="starting",
        unloaded_at=LATER_TIME,
        error="old error",
    )

    result = repository.mark_running(
        runtime,
        started_by="operator",
        context={
            "load_ms": 120,
        },
        loaded_at=CURRENT_TIME,
        applied_generation=5,
    )

    assert result is runtime
    assert runtime.status == "running"
    assert runtime.loaded_at == CURRENT_TIME
    assert runtime.unloaded_at is None
    assert runtime.error is None
    assert (
        runtime.last_heartbeat_at
        == CURRENT_TIME
    )
    assert runtime.started_by == "operator"
    assert runtime.context == {
        "load_ms": 120,
    }
    assert runtime.applied_generation == 5


def test_mark_running_uses_current_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未提供时间时使用同一个当前时间"""
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
    runtime = create_runtime(
        status="starting"
    )

    monkeypatch.setitem(
        vars(runtime_module),
        "datetime",
        FrozenDateTime,
    )

    repository.mark_running(
        runtime
    )

    assert runtime.loaded_at == CURRENT_TIME
    assert (
        runtime.last_heartbeat_at
        == CURRENT_TIME
    )
def test_mark_running_accepts_empty_operator() -> None:
    """测试已加载状态允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="starting"
    )

    repository.mark_running(
        runtime,
        started_by="",
        loaded_at=CURRENT_TIME,
    )

    assert runtime.started_by == ""


def test_mark_stopped_with_explicit_time() -> None:
    """测试标记已卸载并记录控制版本"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="running",
        loaded_at=EARLIER_TIME,
    )

    result = repository.mark_stopped(
        runtime,
        stopped_by="operator",
        context={
            "reason": "maintenance",
        },
        unloaded_at=CURRENT_TIME,
        applied_generation=6,
    )

    assert result is runtime
    assert runtime.status == "stopped"
    assert runtime.loaded_at == EARLIER_TIME
    assert runtime.unloaded_at == CURRENT_TIME
    assert runtime.stopped_by == "operator"
    assert runtime.context == {
        "reason": "maintenance",
    }
    assert runtime.applied_generation == 6


def test_mark_stopped_uses_current_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未提供卸载时间时使用当前时间"""
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
    runtime = create_runtime(
        status="running"
    )

    monkeypatch.setitem(
        vars(runtime_module),
        "datetime",
        FrozenDateTime,
    )

    repository.mark_stopped(
        runtime
    )

    assert runtime.unloaded_at == CURRENT_TIME


def test_mark_stopped_accepts_empty_operator() -> None:
    """测试卸载状态允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="running"
    )

    repository.mark_stopped(
        runtime,
        stopped_by="",
        unloaded_at=CURRENT_TIME,
    )

    assert runtime.stopped_by == ""


def test_mark_failed() -> None:
    """测试标记加载失败"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="starting"
    )

    result = repository.mark_failed(
        runtime,
        error="model file missing",
        started_by="operator",
        context={
            "attempt": 3,
        },
    )

    assert result is runtime
    assert runtime.status == "failed"
    assert runtime.error == (
        "model file missing"
    )
    assert runtime.started_by == "operator"
    assert runtime.context == {
        "attempt": 3,
    }


def test_mark_failed_accepts_empty_operator() -> None:
    """测试失败状态允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="starting"
    )

    repository.mark_failed(
        runtime,
        error="failed",
        started_by="",
    )

    assert runtime.started_by == ""


def test_heartbeat_with_explicit_time() -> None:
    """测试使用指定时间更新运行心跳"""
    repository, _, _ = create_repository()
    runtime = create_runtime(
        status="running"
    )

    result = repository.heartbeat(
        runtime,
        heartbeat_at=CURRENT_TIME,
    )

    assert result is runtime
    assert (
        runtime.last_heartbeat_at
        == CURRENT_TIME
    )

def test_heartbeat_uses_current_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未提供时间时使用当前 UTC 时间"""
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
    runtime = create_runtime(
        status="running"
    )

    monkeypatch.setitem(
        vars(runtime_module),
        "datetime",
        FrozenDateTime,
    )

    repository.heartbeat(
        runtime
    )

    assert (
        runtime.last_heartbeat_at
        == CURRENT_TIME
    )
