"""模型执行仓储测试.

验证 ExecutionRepository 的执行查询、列表筛选、创建和状态迁移。

核心功能：
  - test_get_execution:
    验证按执行 ID 查询
  - test_list_executions:
    验证执行筛选、排序和分页
  - test_create_execution:
    验证创建主执行和影子执行
  - test_execution_status_transitions:
    验证执行状态迁移和结果写入
  - test_reset_for_retry:
    验证未成功的影子执行恢复为等待状态
  - test_reset_for_retry_validation:
    验证影子执行重试条件
  - test_execution_validation:
    验证执行参数和状态迁移约束
"""

from datetime import (
    datetime,
    timezone,
)
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

from datamind.db.models.executions import Execution
from datamind.db.repositories.execution import ExecutionRepository
from datamind.models.enums import (
    ExecutionStatus,
    ExecutionType,
)


CURRENT_TIME = datetime(
    2026,
    8,
    11,
    9,
    0,
    tzinfo=timezone.utc,
)


def create_execution(
        **overrides: Any,
) -> Execution:
    """创建模型执行测试对象."""
    values: dict[str, Any] = {
        "execution_id": "exe_0123456789abcdef",
        "decision_id": "dcs_0123456789abcdef",
        "execution_type": "shadow",
        "status": "queued",
        "model_id": "mdl_0123456789abcdef",
        "version_id": "ver_0123456789abcdef",
        "deployment_id": "dep_0123456789abcdef",
    }
    values.update(
        overrides
    )
    return Execution(
        **values
    )


def create_repository(
        *,
        scalar_result: Execution | None = None,
        list_result: list[Execution] | None = None,
) -> tuple[ExecutionRepository, AsyncMock, MagicMock]:
    """创建模型执行仓储及会话方法替身."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar_result
    scalar_collection = MagicMock()
    scalar_collection.all.return_value = (
        list_result
        if list_result is not None
        else []
    )
    result.scalars.return_value = scalar_collection
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
    return (
        ExecutionRepository(session),
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
        awaited_call.args[0],
    )


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
async def test_get_execution() -> None:
    """测试按执行 ID 查询."""
    expected = create_execution()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )
    result = await repository.get_execution(
        expected.execution_id
    )
    assert result is expected
    sql = compile_statement(
        get_executed_statement(execute)
    )
    assert "executions.execution_id = 'exe_0123456789abcdef'" in sql


@pytest.mark.asyncio
async def test_list_executions() -> None:
    """测试执行筛选、排序和分页."""
    expected = [
        create_execution()
    ]
    repository, execute, _ = create_repository(
        list_result=expected
    )
    result = await repository.list_executions(
        decision_id="dcs_0123456789abcdef",
        deployment_id="dep_0123456789abcdef",
        execution_type=ExecutionType.SHADOW,
        status=ExecutionStatus.QUEUED,
        limit=20,
        offset=10,
    )
    assert result == expected
    sql = compile_statement(
        get_executed_statement(execute)
    )
    assert "executions.decision_id = 'dcs_0123456789abcdef'" in sql
    assert "executions.deployment_id = 'dep_0123456789abcdef'" in sql
    assert "executions.execution_type = 'shadow'" in sql
    assert "executions.status = 'queued'" in sql
    assert "ORDER BY executions.created_at ASC, executions.id ASC" in sql
    assert "LIMIT 20 OFFSET 10" in sql


def test_create_execution() -> None:
    """测试创建主执行和自动补充结束时间."""
    repository, _, add = create_repository()
    execution = repository.create_execution(
        execution_id="exe_primary",
        decision_id="dcs_test",
        execution_type=ExecutionType.PRIMARY,
        status=ExecutionStatus.SUCCESS,
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        prediction={
            "score": 720,
        },
        score=720.0,
        latency_ms=8.5,
        started_at=CURRENT_TIME,
    )
    add.assert_called_once_with(
        execution
    )
    assert execution.execution_type == "primary"
    assert execution.status == "success"
    assert execution.finished_at is not None


def test_execution_status_transitions() -> None:
    """测试执行状态迁移和结果写入."""
    repository, _, _ = create_repository()
    execution = create_execution()
    repository.mark_running(
        execution,
        started_at=CURRENT_TIME,
    )
    assert execution.status == "running"
    assert execution.started_at == CURRENT_TIME
    repository.mark_success(
        execution,
        prediction={
            "score": 710,
        },
        score=710.0,
        latency_ms=12.5,
        finished_at=CURRENT_TIME,
    )
    assert execution.status == "success"
    assert execution.prediction == {
        "score": 710,
    }
    assert execution.finished_at == CURRENT_TIME


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CANCELLED,
    ],
)
def test_mark_failed_supports_terminal_statuses(
        status: ExecutionStatus,
) -> None:
    """测试未成功执行可以进入各类终态."""
    repository, _, _ = create_repository()
    execution = create_execution()
    repository.mark_failed(
        execution,
        status=status,
        error="execution failed",
        finished_at=CURRENT_TIME,
    )
    assert execution.status == str(status)
    assert execution.error == "execution failed"


@pytest.mark.parametrize(
    "status",
    [
        ExecutionStatus.FAILED,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.CANCELLED,
    ],
)
def test_reset_for_retry(
        status: ExecutionStatus,
) -> None:
    """测试未成功的影子执行恢复为等待状态."""
    repository, _, _ = create_repository()
    execution = create_execution(
        status=str(status),
        prediction={"score": 680},
        probability=0.4,
        score=680.0,
        latency_ms=12.5,
        error_type="RuntimeError",
        error="execution failed",
        started_at=CURRENT_TIME,
        finished_at=CURRENT_TIME,
    )

    result = repository.reset_for_retry(execution)

    assert result is execution
    assert execution.status == "queued"
    for field in (
        "prediction",
        "probability",
        "score",
        "latency_ms",
        "error_type",
        "error",
        "started_at",
        "finished_at",
    ):
        assert getattr(execution, field) is None, field


@pytest.mark.parametrize(
    ("execution", "error"),
    [
        (
            create_execution(
                execution_type="primary",
                status="failed",
            ),
            "只有影子模型执行可以重试",
        ),
        (
            create_execution(status="running"),
            "只有未成功的影子模型执行可以重试",
        ),
        (
            create_execution(status="success"),
            "只有未成功的影子模型执行可以重试",
        ),
    ],
)
def test_reset_for_retry_validation(
        execution: Execution,
        error: str,
) -> None:
    """测试影子执行重试条件."""
    repository, _, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=error,
    ):
        repository.reset_for_retry(execution)


def test_execution_validation() -> None:
    """测试执行参数和状态迁移约束."""
    repository, _, _ = create_repository()
    with pytest.raises(
            ValueError,
            match="probability",
    ):
        repository.create_execution(
            execution_id="exe_test",
            decision_id="dcs_test",
            execution_type=ExecutionType.PRIMARY,
            status=ExecutionStatus.SUCCESS,
            model_id="mdl_test",
            version_id="ver_test",
            deployment_id="dep_test",
            probability=1.1,
        )
    with pytest.raises(
            ValueError,
            match="queued 状态",
    ):
        repository.mark_running(
            create_execution(
                status="success"
            )
        )
