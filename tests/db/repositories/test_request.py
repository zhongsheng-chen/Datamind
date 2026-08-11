# tests/db/repositories/test_request.py

"""请求仓储测试

验证 RequestRepository 的请求查询、列表筛选、辅助列表方法、
请求记录创建，以及成功和失败状态更新。

核心功能：
  - test_get_request:
    验证按请求 ID 查询
  - test_list_requests:
    验证请求字段筛选、排序和分页
  - test_list_recent_requests:
    验证最近请求默认数量限制
  - test_list_model_requests:
    验证获取指定模型请求
  - test_create_request:
    验证创建请求并设置 received 状态
  - test_mark_success:
    验证标记请求处理成功
  - test_mark_failed:
    验证标记请求处理失败
  - test_request_latency:
    验证处理耗时不能为负数
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

from datamind.db.models.requests import Request
from datamind.db.repositories.request import RequestRepository


def create_request(
        **overrides: Any,
) -> Request:
    """创建请求记录测试对象"""
    values: dict[str, Any] = {
        "request_id": "req_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "payload": {
            "features": {
                "age": 35,
            },
        },
        "response": None,
        "source": "api",
        "status": "received",
        "error": None,
        "latency_ms": None,
        "user": "admin",
        "ip": "127.0.0.1",
    }
    values.update(
        overrides
    )

    return Request(
        **values
    )


def create_repository(
        *,
        scalar_result: Request | None = None,
        list_result: list[Request] | None = None,
) -> tuple[
    RequestRepository,
    AsyncMock,
    MagicMock,
]:
    """创建请求仓储及会话方法替身"""
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
    repository = RequestRepository(
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
async def test_get_request() -> None:
    """验证按请求 ID 查询"""
    expected = create_request()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_request(
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
        "requests.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_request_returns_none_when_not_found() -> None:
    """验证请求记录不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_request(
        "req_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_requests_without_filters() -> None:
    """验证无筛选时返回全部请求并按创建时间倒序"""
    requests = [
        create_request()
    ]
    repository, execute, _ = create_repository(
        list_result=requests
    )

    result = await repository.list_requests()

    assert result == requests

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY requests.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_requests_applies_filters_and_pagination() -> None:
    """验证请求字段筛选、排序和分页"""
    requests = [
        create_request(
            status="success",
            latency_ms=125.5,
        )
    ]
    repository, execute, _ = create_repository(
        list_result=requests
    )

    result = await repository.list_requests(
        request_id="req_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        source="http",
        status="success",
        user="admin",
        ip="127.0.0.1",
        limit=25,
        offset=10,
    )

    assert result == requests

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "requests.request_id = "
        "'req_0123456789abcdef'"
        in sql
    )
    assert (
        "requests.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert "requests.source = 'http'" in sql
    assert "requests.status = 'success'" in sql
    assert (
        'requests."user" = \'admin\''
        in sql
    )
    assert "requests.ip = '127.0.0.1'" in sql
    assert (
        "ORDER BY requests.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_requests_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_requests(
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
            "list_requests",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_requests",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_recent_requests",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_model_requests",
            {
                "model_id": "mdl_test",
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
    """验证请求列表方法拒绝负数分页参数"""
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
async def test_list_recent_requests_uses_default_limit() -> None:
    """验证最近请求默认返回 100 条"""
    requests = [
        create_request()
    ]
    repository, execute, _ = create_repository(
        list_result=requests
    )

    result = await repository.list_recent_requests()

    assert result == requests

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY requests.created_at DESC"
        in sql
    )
    assert "LIMIT 100" in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_recent_requests_accepts_custom_pagination() -> None:
    """验证最近请求支持自定义分页"""
    repository, execute, _ = create_repository()

    await repository.list_recent_requests(
        limit=20,
        offset=5,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "LIMIT 20" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_list_model_requests_uses_default_limit() -> None:
    """验证模型请求默认返回 100 条"""
    requests = [
        create_request()
    ]
    repository, execute, _ = create_repository(
        list_result=requests
    )

    result = await repository.list_model_requests(
        "mdl_0123456789abcdef"
    )

    assert result == requests

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "requests.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert "LIMIT 100" in sql


@pytest.mark.asyncio
async def test_list_model_requests_accepts_custom_pagination() -> None:
    """验证模型请求支持自定义分页"""
    repository, execute, _ = create_repository()

    await repository.list_model_requests(
        "mdl_0123456789abcdef",
        limit=20,
        offset=5,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "requests.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert "LIMIT 20" in sql
    assert "OFFSET 5" in sql


# noinspection PyUnreachableCode
def test_create_request() -> None:
    """验证创建请求并显式设置 received 状态"""
    repository, _, add = create_repository()

    request = repository.create_request(
        request_id="req_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        payload={
            "features": {
                "age": 35,
            },
        },
        source="http",
        latency_ms=12.5,
        user="admin",
        ip="127.0.0.1",
    )

    add.assert_called_once_with(
        request
    )
    assert request.request_id == (
        "req_0123456789abcdef"
    )
    assert request.model_id == (
        "mdl_0123456789abcdef"
    )
    assert request.payload == {
        "features": {
            "age": 35,
        },
    }
    assert request.response is None
    assert request.source == "http"
    assert request.status == "received"
    assert request.error is None
    assert request.latency_ms == 12.5
    assert request.user == "admin"
    assert request.ip == "127.0.0.1"


# noinspection PyUnreachableCode
def test_create_request_allows_optional_fields() -> None:
    """验证创建请求时允许省略可选字段"""
    repository, _, add = create_repository()

    request = repository.create_request(
        request_id="req_minimum",
        model_id="mdl_minimum",
    )

    add.assert_called_once_with(
        request
    )
    assert request.payload is None
    assert request.model_name is None
    assert request.response is None
    assert request.source is None
    assert request.status == "received"
    assert request.error is None
    assert request.latency_ms is None
    assert request.user is None
    assert request.ip is None


def test_create_request_allows_unresolved_model() -> None:
    """验证模型解析前可保存原始请求"""
    repository, _, add = create_repository()

    request = repository.create_request(
        request_id="req_unresolved",
        model_name="missing-model",
        payload={
            "model_name": "missing-model",
            "features": {"age": 35},
        },
    )

    add.assert_called_once_with(request)
    assert vars(request).get("model_id") is None
    assert request.model_name == "missing-model"
    assert request.status == "received"


@pytest.mark.parametrize(
    "latency_ms",
    [
        0.0,
        1.5,
    ],
)
def test_create_request_accepts_non_negative_latency(
        latency_ms: float,
) -> None:
    """验证创建请求接受非负耗时"""
    repository, _, add = create_repository()

    request = repository.create_request(
        request_id="req_latency",
        model_id="mdl_latency",
        latency_ms=latency_ms,
    )

    add.assert_called_once_with(
        request
    )
    assert request.latency_ms == latency_ms


def test_create_request_rejects_negative_latency() -> None:
    """验证创建请求拒绝负数耗时"""
    repository, _, add = create_repository()

    with pytest.raises(
            ValueError,
            match="latency_ms 不能小于 0",
    ):
        repository.create_request(
            request_id="req_invalid",
            model_id="mdl_invalid",
            latency_ms=-0.01,
        )

    add.assert_not_called()


# noinspection PyUnreachableCode
def test_mark_success() -> None:
    """验证标记请求处理成功"""
    repository, _, _ = create_repository()
    request = create_request(
        model_id=None,
        status="failed",
        error="old error",
        latency_ms=100.0,
    )

    result = repository.mark_success(
        request,
        model_id="mdl_resolved",
        response={
            "success": True,
            "score": 720,
        },
        latency_ms=125.5,
    )

    assert result is request
    assert request.status == "success"
    assert request.model_id == "mdl_resolved"
    assert request.error is None
    assert request.response == {
        "success": True,
        "score": 720,
    }
    assert request.latency_ms == 125.5


# noinspection PyUnreachableCode
def test_mark_success_preserves_latency_when_omitted() -> None:
    """验证成功时未提供耗时则保留原值"""
    repository, _, _ = create_repository()
    request = create_request(
        model_id=None,
        status="received",
        latency_ms=100.0,
    )

    repository.mark_success(
        request
    )

    assert request.status == "success"
    assert request.error is None
    assert request.latency_ms == 100.0


def test_mark_success_accepts_zero_latency() -> None:
    """验证成功状态允许零耗时"""
    repository, _, _ = create_repository()
    request = create_request(
        latency_ms=100.0
    )

    repository.mark_success(
        request,
        latency_ms=0.0,
    )

    assert request.latency_ms == 0.0


def test_mark_success_rejects_negative_latency_without_mutation() -> None:
    """验证成功状态拒绝负数耗时且不修改对象"""
    repository, _, _ = create_repository()
    request = create_request(
        status="failed",
        error="original error",
        latency_ms=100.0,
    )

    with pytest.raises(
            ValueError,
            match="latency_ms 不能小于 0",
    ):
        repository.mark_success(
            request,
            latency_ms=-0.01,
        )

    assert request.status == "failed"
    assert request.error == "original error"
    assert request.latency_ms == 100.0


def test_mark_failed() -> None:
    """验证标记请求处理失败"""
    repository, _, _ = create_repository()
    request = create_request(
        status="received",
        latency_ms=100.0,
    )

    result = repository.mark_failed(
        request,
        error="model timeout",
        model_id="mdl_resolved",
        response={
            "success": False,
            "error": "model timeout",
        },
        latency_ms=125.5,
    )

    assert result is request
    assert request.status == "failed"
    assert request.model_id == "mdl_resolved"
    assert request.error == "model timeout"
    assert request.response == {
        "success": False,
        "error": "model timeout",
    }
    assert request.latency_ms == 125.5


def test_mark_failed_preserves_latency_when_omitted() -> None:
    """验证失败时未提供耗时则保留原值"""
    repository, _, _ = create_repository()
    request = create_request(
        status="received",
        latency_ms=100.0,
    )

    repository.mark_failed(
        request,
        error="model timeout",
    )

    assert request.status == "failed"
    assert request.error == "model timeout"
    assert request.latency_ms == 100.0


def test_mark_failed_accepts_empty_error() -> None:
    """验证失败状态允许明确写入空错误信息"""
    repository, _, _ = create_repository()
    request = create_request()

    repository.mark_failed(
        request,
        error="",
        latency_ms=0.0,
    )

    assert request.status == "failed"
    assert request.error == ""
    assert request.latency_ms == 0.0


# noinspection PyUnreachableCode
def test_mark_failed_rejects_negative_latency_without_mutation() -> None:
    """验证失败状态拒绝负数耗时且不修改对象"""
    repository, _, _ = create_repository()
    request = create_request(
        status="success",
        error=None,
        latency_ms=100.0,
    )

    with pytest.raises(
            ValueError,
            match="latency_ms 不能小于 0",
    ):
        repository.mark_failed(
            request,
            error="model timeout",
            latency_ms=-0.01,
        )

    assert request.status == "success"
    assert request.error is None
    assert request.latency_ms == 100.0
