"""实验仓储测试.

验证 ExperimentRepository 的实验查询、列表筛选、创建、
普通字段更新，以及由 ModelGuard 控制的实验生命周期迁移。

核心功能：
  - test_get_experiment:
    验证按实验 ID 查询
  - test_get_running_experiment:
    验证查询指定模型和环境下的运行中实验
  - test_list_experiments:
    验证环境、状态、排序和分页
  - test_list_running_experiments:
    验证运行中实验和生效时间窗口
  - test_experiment_patch:
    验证更新结构和环境枚举
  - test_create_experiment:
    验证创建实验并设置 draft 状态
  - test_update_experiment:
    验证普通实验字段更新
  - test_start_experiment:
    验证启动实验时设置生效时间
  - test_experiment_lifecycle:
    验证实验生命周期状态迁移
"""

from dataclasses import fields
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

import datamind.db.repositories.experiment as experiment_module
from datamind.constants import Environment
from datamind.db.models.experiments import Experiment
from datamind.db.repositories.experiment import (
    ExperimentPatch,
    ExperimentRepository,
)
from datamind.models.enums import ExperimentStatus
from datamind.models.guard import ModelGuard


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    12,
    0,
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


def create_experiment(
        **overrides: Any,
) -> Experiment:
    """创建实验测试对象."""
    values: dict[str, Any] = {
        "experiment_id": "exp_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "environment": "development",
        "name": "scorecard_ab_test",
        "description": "信用评分模型实验",
        "status": str(
            ExperimentStatus.DRAFT
        ),
        "config": {
            "strategy": "hash",
            "traffic_ratio": 0.3,
            "bucket_key": "customer_id",
        },
        "effective_from": EARLIER_TIME,
        "effective_to": LATER_TIME,
        "created_by": "creator",
        "updated_by": "original_operator",
    }
    values.update(
        overrides
    )

    return Experiment(
        **values
    )


def create_repository(
        *,
        scalar_result: Experiment | None = None,
        first_result: Experiment | None = None,
        list_result: list[Experiment] | None = None,
) -> tuple[
    ExperimentRepository,
    AsyncMock,
    MagicMock,
]:
    """创建实验仓储及会话方法替身."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = (
        scalar_result
    )

    scalar_collection = MagicMock()
    scalar_collection.first.return_value = (
        first_result
    )
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
    repository = ExperimentRepository(
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
async def test_get_experiment() -> None:
    """测试按实验 ID 查询."""
    expected = create_experiment()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_experiment(
        "exp_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "experiments.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_experiment_returns_none_when_not_found() -> None:
    """测试实验不存在时返回 None."""
    repository, execute, _ = create_repository()

    result = await repository.get_experiment(
        "exp_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_running_experiment() -> None:
    """测试查询指定模型和环境下的运行中实验."""
    expected = create_experiment(
        status=str(
            ExperimentStatus.RUNNING
        ),
        environment="production",
    )
    repository, execute, _ = create_repository(
        first_result=expected
    )

    result = await repository.get_running_experiment(
        model_id="mdl_0123456789abcdef",
        environment=Environment.PRODUCTION,
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "experiments.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "experiments.environment = 'production'"
        in sql
    )
    assert (
        "experiments.status = 'running'"
        in sql
    )
    assert (
        "ORDER BY experiments.created_at DESC"
        in sql
    )
    assert (
        "experiments.experiment_id !="
        not in sql
    )
    where_clause = sql.split(
        "WHERE ",
        maxsplit=1,
    )[1]

    assert (
        "experiments.effective_from IS NULL"
        not in where_clause
    )
    assert (
        "experiments.effective_from <="
        not in where_clause
    )
    assert (
        "experiments.effective_to IS NULL"
        not in where_clause
    )
    assert (
        "experiments.effective_to >"
        not in where_clause
    )


@pytest.mark.asyncio
async def test_get_running_experiment_applies_exclusion_and_window() -> None:
    """测试运行中实验查询应用排除条件和生效时间窗口."""
    repository, execute, _ = create_repository()

    result = await repository.get_running_experiment(
        model_id="mdl_0123456789abcdef",
        environment=Environment.STAGING,
        exclude_experiment_id=(
            "exp_0123456789abcdef"
        ),
        now=CURRENT_TIME,
    )

    assert result is None

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "experiments.environment = 'staging'"
        in sql
    )
    assert (
        "experiments.experiment_id != "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "experiments.effective_from IS NULL"
        in sql
    )
    assert (
        "experiments.effective_from <="
        in sql
    )
    assert (
        "experiments.effective_to IS NULL"
        in sql
    )
    assert (
        "experiments.effective_to >"
        in sql
    )


@pytest.mark.asyncio
async def test_list_experiments_without_filters() -> None:
    """测试无筛选时返回全部实验并按创建时间倒序."""
    experiments = [
        create_experiment()
    ]
    repository, execute, _ = create_repository(
        list_result=experiments
    )

    result = await repository.list_experiments()

    assert result == experiments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY experiments.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_experiments_applies_filters_and_pagination() -> None:
    """测试环境、状态、普通字段筛选和分页."""
    experiments = [
        create_experiment(
            environment="production",
            status=str(
                ExperimentStatus.RUNNING
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=experiments
    )

    result = await repository.list_experiments(
        experiment_id="exp_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        environment=Environment.PRODUCTION,
        name="scorecard_ab_test",
        status=ExperimentStatus.RUNNING,
        created_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == experiments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "experiments.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert (
        "experiments.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "experiments.environment = 'production'"
        in sql
    )
    assert (
        "experiments.name = 'scorecard_ab_test'"
        in sql
    )
    assert (
        "experiments.status = 'running'"
        in sql
    )
    assert (
        "experiments.created_by = 'model_admin'"
        in sql
    )
    assert (
        "ORDER BY experiments.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_experiments_applies_zero_pagination() -> None:
    """测试零值分页参数仍会应用."""
    repository, execute, _ = create_repository()

    await repository.list_experiments(
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
async def test_list_running_experiments() -> None:
    """测试运行中实验列表和生效时间窗口."""
    experiments = [
        create_experiment(
            environment="testing",
            status=str(
                ExperimentStatus.RUNNING
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=experiments
    )

    result = await repository.list_running_experiments(
        "mdl_0123456789abcdef",
        environment=Environment.TESTING,
        now=CURRENT_TIME,
        limit=50,
        offset=5,
    )

    assert result == experiments

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "experiments.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "experiments.environment = 'testing'"
        in sql
    )
    assert (
        "experiments.status = 'running'"
        in sql
    )
    assert (
        "experiments.effective_from IS NULL"
        in sql
    )
    assert (
        "experiments.effective_from <="
        in sql
    )
    assert (
        "experiments.effective_to IS NULL"
        in sql
    )
    assert (
        "experiments.effective_to >"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "method_name",
        "arguments",
        "expected_message",
    ),
    [
        (
            "list_experiments",
            {
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_experiments",
            {
                "offset": -1,
            },
            "offset 不能小于 0",
        ),
        (
            "list_running_experiments",
            {
                "model_id": "mdl_test",
                "limit": -1,
            },
            "limit 不能小于 0",
        ),
        (
            "list_running_experiments",
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
    """测试实验列表方法拒绝负数分页参数."""
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


def test_experiment_patch_fields_and_defaults() -> None:
    """测试更新结构字段和默认值."""
    patch = ExperimentPatch()

    assert [
        field.name
        for field in fields(
            ExperimentPatch
        )
    ] == [
        "environment",
        "name",
        "description",
        "config",
        "effective_from",
        "effective_to",
    ]
    assert patch.environment is None
    assert patch.name is None
    assert patch.description is None
    assert patch.config is None
    assert patch.effective_from is None
    assert patch.effective_to is None
    assert not hasattr(
        patch,
        "status",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_experiment_patch_accepts_environment_enum() -> None:
    """测试更新结构接受环境枚举."""
    patch = ExperimentPatch(
        environment=Environment.PRODUCTION
    )

    assert patch.environment is (
        Environment.PRODUCTION
    )


def test_create_experiment() -> None:
    """测试创建实验并显式设置 draft 状态."""
    repository, _, add = create_repository()

    experiment = repository.create_experiment(
        experiment_id="exp_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        environment=Environment.PRODUCTION,
        name="scorecard_ab_test",
        description="信用评分模型实验",
        config={
            "strategy": "hash",
            "traffic_ratio": 0.3,
        },
        effective_from=EARLIER_TIME,
        effective_to=LATER_TIME,
        created_by="creator",
    )

    add.assert_called_once_with(
        experiment
    )
    assert experiment.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert experiment.model_id == (
        "mdl_0123456789abcdef"
    )
    assert experiment.environment == (
        "production"
    )
    assert experiment.name == "scorecard_ab_test"
    assert experiment.description == (
        "信用评分模型实验"
    )
    assert experiment.status == str(
        ExperimentStatus.DRAFT
    )
    assert experiment.config == {
        "strategy": "hash",
        "traffic_ratio": 0.3,
    }
    assert (
        experiment.effective_from
        == EARLIER_TIME
    )
    assert (
        experiment.effective_to
        == LATER_TIME
    )
    assert experiment.created_by == "creator"


# noinspection PyUnreachableCode
def test_create_experiment_allows_optional_fields() -> None:
    """测试创建实验时允许省略可选字段."""
    repository, _, add = create_repository()

    experiment = repository.create_experiment(
        experiment_id="exp_minimum",
        model_id="mdl_minimum",
        environment=Environment.DEVELOPMENT,
    )

    add.assert_called_once_with(
        experiment
    )
    assert experiment.environment == (
        "development"
    )
    assert experiment.status == str(
        ExperimentStatus.DRAFT
    )
    assert experiment.name is None
    assert experiment.description is None
    assert experiment.config is None
    assert experiment.effective_from is None
    assert experiment.effective_to is None
    assert experiment.created_by is None


def test_update_experiment() -> None:
    """测试更新所有非空普通实验字段."""
    repository, _, _ = create_repository()
    experiment = create_experiment()
    original_status = experiment.status

    result = repository.update_experiment(
        experiment,
        ExperimentPatch(
            environment=Environment.STAGING,
            name="scorecard_ab_test_v2",
            description="更新后的实验说明",
            config={
                "strategy": "manual",
            },
            effective_from=CURRENT_TIME,
            effective_to=LATER_TIME,
        ),
        updated_by="operator",
    )

    assert result is experiment
    assert experiment.environment == "staging"
    assert experiment.name == (
        "scorecard_ab_test_v2"
    )
    assert experiment.description == (
        "更新后的实验说明"
    )
    assert experiment.config == {
        "strategy": "manual",
    }
    assert (
        experiment.effective_from
        == CURRENT_TIME
    )
    assert (
        experiment.effective_to
        == LATER_TIME
    )
    assert experiment.updated_by == "operator"
    assert experiment.status == original_status


def test_update_experiment_ignores_none_fields() -> None:
    """测试值为 None 的字段不会覆盖原值."""
    repository, _, _ = create_repository()
    experiment = create_experiment()

    result = repository.update_experiment(
        experiment,
        ExperimentPatch(),
    )

    assert result is experiment
    assert experiment.environment == (
        "development"
    )
    assert experiment.name == "scorecard_ab_test"
    assert experiment.description == (
        "信用评分模型实验"
    )


def test_update_experiment_accepts_empty_strings() -> None:
    """测试空字符串作为明确更新值写入对象."""
    repository, _, _ = create_repository()
    experiment = create_experiment()

    repository.update_experiment(
        experiment,
        ExperimentPatch(
            name="",
            description="",
        ),
        updated_by="",
    )

    assert experiment.name == ""
    assert experiment.description == ""
    assert experiment.updated_by == ""


@pytest.mark.parametrize(
    (
        "method_name",
        "current_status",
        "target_status",
    ),
    [
        (
            "start_experiment",
            ExperimentStatus.DRAFT,
            ExperimentStatus.RUNNING,
        ),
        (
            "stop_experiment",
            ExperimentStatus.RUNNING,
            ExperimentStatus.STOPPED,
        ),
        (
            "pause_experiment",
            ExperimentStatus.RUNNING,
            ExperimentStatus.PAUSED,
        ),
        (
            "complete_experiment",
            ExperimentStatus.RUNNING,
            ExperimentStatus.COMPLETED,
        ),
        (
            "archive_experiment",
            ExperimentStatus.COMPLETED,
            ExperimentStatus.ARCHIVED,
        ),
    ],
)
def test_experiment_lifecycle_transition(
        monkeypatch: pytest.MonkeyPatch,
        method_name: str,
        current_status: ExperimentStatus,
        target_status: ExperimentStatus,
) -> None:
    """测试生命周期方法调用守卫并写入字符串状态."""
    validator = MagicMock()
    monkeypatch.setattr(
        ModelGuard,
        "validate_experiment_transition",
        validator,
    )

    repository, _, _ = create_repository()
    experiment = create_experiment(
        status=str(
            current_status
        )
    )
    method = getattr(
        repository,
        method_name,
    )

    result = method(
        experiment,
        updated_by="operator",
    )

    assert result is experiment
    assert experiment.status == str(
        target_status
    )
    assert experiment.updated_by == "operator"
    validator.assert_called_once_with(
        current=current_status,
        target=target_status,
    )


def test_start_experiment_sets_missing_effective_from(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启动时使用当前时间补全生效时间."""
    clock = MagicMock()
    clock.now.return_value = CURRENT_TIME
    monkeypatch.setitem(
        vars(experiment_module),
        "datetime",
        clock,
    )
    repository, _, _ = create_repository()
    experiment = create_experiment(
        effective_from=None
    )

    result = repository.start_experiment(
        experiment,
        updated_by="operator",
    )

    assert result.effective_from == CURRENT_TIME
    clock.now.assert_called_once_with(
        timezone.utc
    )


def test_start_experiment_preserves_configured_effective_from() -> None:
    """测试启动时保留显式配置的生效时间."""
    repository, _, _ = create_repository()
    experiment = create_experiment(
        effective_from=LATER_TIME
    )

    result = repository.start_experiment(
        experiment,
        updated_by="operator",
    )

    assert result.effective_from == LATER_TIME


@pytest.mark.parametrize(
    (
        "method_name",
        "target_status",
    ),
    [
        (
            "start_experiment",
            ExperimentStatus.RUNNING,
        ),
        (
            "stop_experiment",
            ExperimentStatus.STOPPED,
        ),
        (
            "pause_experiment",
            ExperimentStatus.PAUSED,
        ),
        (
            "complete_experiment",
            ExperimentStatus.COMPLETED,
        ),
        (
            "archive_experiment",
            ExperimentStatus.ARCHIVED,
        ),
    ],
)
def test_experiment_lifecycle_is_idempotent(
        monkeypatch: pytest.MonkeyPatch,
        method_name: str,
        target_status: ExperimentStatus,
) -> None:
    """测试目标状态相同时保持幂等."""
    validator = MagicMock()
    monkeypatch.setattr(
        ModelGuard,
        "validate_experiment_transition",
        validator,
    )

    repository, _, _ = create_repository()
    experiment = create_experiment(
        status=str(
            target_status
        ),
        updated_by="original_operator",
    )
    method = getattr(
        repository,
        method_name,
    )

    result = method(
        experiment,
        updated_by="new_operator",
    )

    assert result is experiment
    assert experiment.status == str(
        target_status
    )
    assert experiment.updated_by == (
        "original_operator"
    )
    validator.assert_not_called()


def test_experiment_lifecycle_accepts_empty_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试生命周期方法允许写入空字符串操作人."""
    monkeypatch.setattr(
        ModelGuard,
        "validate_experiment_transition",
        MagicMock(),
    )

    repository, _, _ = create_repository()
    experiment = create_experiment(
        status=str(
            ExperimentStatus.DRAFT
        )
    )

    repository.start_experiment(
        experiment,
        updated_by="",
    )

    assert experiment.status == str(
        ExperimentStatus.RUNNING
    )
    assert experiment.updated_by == ""


def test_experiment_lifecycle_propagates_guard_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试守卫拒绝迁移时不修改实验."""
    validator = MagicMock(
        side_effect=RuntimeError(
            "transition blocked"
        )
    )
    monkeypatch.setattr(
        ModelGuard,
        "validate_experiment_transition",
        validator,
    )

    repository, _, _ = create_repository()
    experiment = create_experiment(
        status=str(
            ExperimentStatus.DRAFT
        ),
        updated_by="original_operator",
    )

    with pytest.raises(
            RuntimeError,
            match="transition blocked",
    ):
        repository.archive_experiment(
            experiment,
            updated_by="operator",
        )

    assert experiment.status == str(
        ExperimentStatus.DRAFT
    )
    assert experiment.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "start_experiment",
        "stop_experiment",
        "pause_experiment",
        "complete_experiment",
        "archive_experiment",
    ],
)
def test_experiment_lifecycle_rejects_unknown_status(
        method_name: str,
) -> None:
    """测试未知状态不能进入实验生命周期迁移."""
    repository, _, _ = create_repository()
    experiment = create_experiment(
        status="unknown"
    )
    method = getattr(
        repository,
        method_name,
    )

    with pytest.raises(
            ValueError,
            match=(
                "'unknown' is not a valid "
                "ExperimentStatus"
            ),
    ):
        method(
            experiment,
            updated_by="operator",
        )

    assert experiment.status == "unknown"
