"""实验分组仓储测试

验证 VariantRepository 的实验分组查询、列表筛选、创建、
普通字段更新，以及启用、停用和归档生命周期管理。

核心功能：
  - test_get_variant:
    验证按实验分组 ID 查询
  - test_list_variants:
    验证状态、对照组、排序和分页
  - test_list_active_variants:
    验证获取启用的实验分组
  - test_get_control_variant:
    验证获取启用的实验对照组
  - test_variant_patch:
    验证更新结构字段
  - test_create_variant:
    验证创建实验分组和权重校验
  - test_update_variant:
    验证普通实验分组字段更新
  - test_variant_lifecycle:
    验证启用、停用和归档状态管理
"""

from dataclasses import fields
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

from datamind.db.models.variants import Variant
from datamind.db.repositories.variant import (
    VariantPatch,
    VariantRepository,
)
from datamind.models.enums import ExperimentVariantStatus


def create_variant(
        **overrides: Any,
) -> Variant:
    """创建实验分组测试对象"""
    values: dict[str, Any] = {
        "variant_id": "var_0123456789abcdef",
        "experiment_id": "exp_0123456789abcdef",
        "name": "control",
        "deployment_id": "dep_0123456789abcdef",
        "weight": 0.5,
        "is_control": True,
        "status": str(
            ExperimentVariantStatus.ACTIVE
        ),
        "config": {
            "strategy": "hash",
        },
        "description": "实验对照组",
        "created_by": "creator",
        "updated_by": "original_operator",
    }
    values.update(
        overrides
    )

    return Variant(
        **values
    )


def create_repository(
        *,
        scalar_result: Variant | None = None,
        list_result: list[Variant] | None = None,
) -> tuple[
    VariantRepository,
    AsyncMock,
    MagicMock,
]:
    """创建实验分组仓储及会话方法替身"""
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
    repository = VariantRepository(
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
async def test_get_variant() -> None:
    """验证按实验分组 ID 查询"""
    expected = create_variant()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_variant(
        "var_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "variants.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_variant_returns_none_when_not_found() -> None:
    """验证实验分组不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_variant(
        "var_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_variants_without_filters() -> None:
    """验证无筛选时返回全部分组并按时间倒序"""
    variants = [
        create_variant()
    ]
    repository, execute, _ = create_repository(
        list_result=variants
    )

    result = await repository.list_variants()

    assert result == variants

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "ORDER BY variants.updated_at DESC, "
        "variants.created_at DESC"
        in sql
    )
    assert " WHERE " not in sql
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_variants_applies_filters_and_pagination() -> None:
    """验证状态、对照组、普通字段筛选和分页"""
    variants = [
        create_variant(
            name="treatment",
            is_control=False,
            status=str(
                ExperimentVariantStatus.INACTIVE
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=variants
    )

    result = await repository.list_variants(
        variant_id="var_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        name="treatment",
        deployment_id="dep_0123456789abcdef",
        status=ExperimentVariantStatus.INACTIVE,
        is_control=False,
        created_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == variants

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "variants.variant_id = "
        "'var_0123456789abcdef'"
        in sql
    )
    assert (
        "variants.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert "variants.name = 'treatment'" in sql
    assert (
        "variants.deployment_id = "
        "'dep_0123456789abcdef'"
        in sql
    )
    assert (
        "variants.status = 'inactive'"
        in sql
    )
    assert "variants.is_control = false" in sql
    assert (
        "variants.created_by = 'model_admin'"
        in sql
    )
    assert (
        "ORDER BY variants.updated_at DESC, "
        "variants.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_variants_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_variants(
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
async def test_list_variants_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """验证拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_variants(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_variants() -> None:
    """验证获取启用的实验分组"""
    variants = [
        create_variant(
            status=str(
                ExperimentVariantStatus.ACTIVE
            )
        )
    ]
    repository, execute, _ = create_repository(
        list_result=variants
    )

    result = await repository.list_active_variants(
        "exp_0123456789abcdef",
        limit=50,
        offset=5,
    )

    assert result == variants

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "variants.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert "variants.status = 'active'" in sql
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


@pytest.mark.asyncio
async def test_get_control_variant() -> None:
    """验证获取最早创建的启用对照组"""
    expected = create_variant(
        is_control=True,
        status=str(
            ExperimentVariantStatus.ACTIVE
        ),
    )
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_control_variant(
        "exp_0123456789abcdef"
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "variants.experiment_id = "
        "'exp_0123456789abcdef'"
        in sql
    )
    assert "variants.is_control IS true" in sql
    assert "variants.status = 'active'" in sql
    assert (
        "ORDER BY variants.created_at ASC"
        in sql
    )
    assert "LIMIT 1" in sql


@pytest.mark.asyncio
async def test_get_control_variant_returns_none() -> None:
    """验证没有启用对照组时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_control_variant(
        "exp_missing"
    )

    assert result is None
    execute.assert_awaited_once()


def test_variant_patch_fields_and_defaults() -> None:
    """验证更新结构字段和默认值"""
    patch = VariantPatch()

    assert [
        field.name
        for field in fields(
            VariantPatch
        )
    ] == [
        "name",
        "deployment_id",
        "weight",
        "is_control",
        "config",
        "description",
    ]
    assert patch.name is None
    assert patch.deployment_id is None
    assert patch.weight is None
    assert patch.is_control is None
    assert patch.config is None
    assert patch.description is None
    assert not hasattr(
        patch,
        "status",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


# noinspection PyUnreachableCode
def test_create_variant() -> None:
    """验证创建实验分组并保存字符串状态"""
    repository, _, add = create_repository()

    variant = repository.create_variant(
        variant_id="var_0123456789abcdef",
        experiment_id="exp_0123456789abcdef",
        name="treatment",
        deployment_id="dep_0123456789abcdef",
        weight=0.5,
        is_control=False,
        status=ExperimentVariantStatus.INACTIVE,
        config={
            "strategy": "manual",
        },
        description="实验组",
        created_by="creator",
    )

    add.assert_called_once_with(
        variant
    )
    assert variant.variant_id == (
        "var_0123456789abcdef"
    )
    assert variant.experiment_id == (
        "exp_0123456789abcdef"
    )
    assert variant.name == "treatment"
    assert variant.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert variant.weight == 0.5
    assert variant.is_control is False
    assert variant.status == str(
        ExperimentVariantStatus.INACTIVE
    )
    assert variant.config == {
        "strategy": "manual",
    }
    assert variant.description == "实验组"
    assert variant.created_by == "creator"


# noinspection PyUnreachableCode
def test_create_variant_uses_optional_defaults() -> None:
    """验证创建实验分组的可选默认值"""
    repository, _, add = create_repository()

    variant = repository.create_variant(
        variant_id="var_minimum",
        experiment_id="exp_minimum",
        name="control",
        deployment_id="dep_minimum",
        weight=0.0,
    )

    add.assert_called_once_with(
        variant
    )
    assert variant.weight == 0.0
    assert variant.is_control is False
    assert variant.status == str(
        ExperimentVariantStatus.ACTIVE
    )
    assert variant.config is None
    assert variant.description is None
    assert variant.created_by is None


@pytest.mark.parametrize(
    "weight",
    [
        0.0,
        1.0,
    ],
)
def test_create_variant_accepts_boundary_weight(
        weight: float,
) -> None:
    """验证实验分组权重边界值有效"""
    repository, _, add = create_repository()

    variant = repository.create_variant(
        variant_id="var_boundary",
        experiment_id="exp_boundary",
        name="boundary",
        deployment_id="dep_boundary",
        weight=weight,
    )

    add.assert_called_once_with(
        variant
    )
    assert variant.weight == weight


@pytest.mark.parametrize(
    "weight",
    [
        -0.01,
        1.01,
    ],
)
def test_create_variant_rejects_invalid_weight(
        weight: float,
) -> None:
    """验证创建时拒绝非法权重"""
    repository, _, add = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "实验分组 weight "
                "必须在 0 到 1 之间"
            ),
    ):
        repository.create_variant(
            variant_id="var_invalid",
            experiment_id="exp_invalid",
            name="invalid",
            deployment_id="dep_invalid",
            weight=weight,
        )

    add.assert_not_called()


# noinspection PyUnreachableCode
def test_update_variant() -> None:
    """验证更新所有非空普通实验分组字段"""
    repository, _, _ = create_repository()
    variant = create_variant()
    original_status = variant.status

    result = repository.update_variant(
        variant,
        VariantPatch(
            name="treatment",
            deployment_id="dep_new",
            weight=0.7,
            is_control=False,
            config={
                "strategy": "manual",
            },
            description="更新后的实验组",
        ),
        updated_by="operator",
    )

    assert result is variant
    assert variant.name == "treatment"
    assert variant.deployment_id == "dep_new"
    assert variant.weight == 0.7
    assert variant.is_control is False
    assert variant.config == {
        "strategy": "manual",
    }
    assert variant.description == (
        "更新后的实验组"
    )
    assert variant.updated_by == "operator"
    assert variant.status == original_status


# noinspection PyUnreachableCode
def test_update_variant_ignores_none_fields() -> None:
    """验证值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    variant = create_variant()

    result = repository.update_variant(
        variant,
        VariantPatch(),
    )

    assert result is variant
    assert variant.name == "control"
    assert variant.deployment_id == (
        "dep_0123456789abcdef"
    )
    assert variant.weight == 0.5
    assert variant.is_control is True
    assert variant.description == "实验对照组"


# noinspection PyUnreachableCode
def test_update_variant_accepts_false_and_empty_strings() -> None:
    """验证 False 和空字符串作为明确更新值写入对象"""
    repository, _, _ = create_repository()
    variant = create_variant()

    repository.update_variant(
        variant,
        VariantPatch(
            name="",
            deployment_id="",
            is_control=False,
            description="",
        ),
        updated_by="",
    )

    assert variant.name == ""
    assert variant.deployment_id == ""
    assert variant.is_control is False
    assert variant.description == ""
    assert variant.updated_by == ""


@pytest.mark.parametrize(
    "weight",
    [
        -0.01,
        1.01,
    ],
)
def test_update_variant_rejects_invalid_weight(
        weight: float,
) -> None:
    """验证更新时拒绝非法权重且不修改其他字段"""
    repository, _, _ = create_repository()
    variant = create_variant()
    original_name = variant.name
    original_weight = variant.weight

    with pytest.raises(
            ValueError,
            match=(
                "实验分组 weight "
                "必须在 0 到 1 之间"
            ),
    ):
        repository.update_variant(
            variant,
            VariantPatch(
                name="treatment",
                weight=weight,
            ),
            updated_by="operator",
        )

    assert variant.name == original_name
    assert variant.weight == original_weight
    assert variant.updated_by == (
        "original_operator"
    )


def test_activate_variant() -> None:
    """验证从 inactive 状态启用实验分组"""
    repository, _, _ = create_repository()
    variant = create_variant(
        status=str(
            ExperimentVariantStatus.INACTIVE
        )
    )

    result = repository.activate_variant(
        variant,
        updated_by="operator",
    )

    assert result is variant
    assert variant.status == str(
        ExperimentVariantStatus.ACTIVE
    )
    assert variant.updated_by == "operator"


def test_deactivate_variant() -> None:
    """验证从 active 状态停用实验分组"""
    repository, _, _ = create_repository()
    variant = create_variant(
        status=str(
            ExperimentVariantStatus.ACTIVE
        )
    )

    result = repository.deactivate_variant(
        variant,
        updated_by="operator",
    )

    assert result is variant
    assert variant.status == str(
        ExperimentVariantStatus.INACTIVE
    )
    assert variant.updated_by == "operator"


@pytest.mark.parametrize(
    "current_status",
    [
        ExperimentVariantStatus.ACTIVE,
        ExperimentVariantStatus.INACTIVE,
    ],
)
def test_archive_variant(
        current_status: ExperimentVariantStatus,
) -> None:
    """验证 active 和 inactive 状态可以归档"""
    repository, _, _ = create_repository()
    variant = create_variant(
        status=str(
            current_status
        )
    )

    result = repository.archive_variant(
        variant,
        updated_by="operator",
    )

    assert result is variant
    assert variant.status == str(
        ExperimentVariantStatus.ARCHIVED
    )
    assert variant.updated_by == "operator"


@pytest.mark.parametrize(
    (
        "method_name",
        "target_status",
    ),
    [
        (
            "activate_variant",
            ExperimentVariantStatus.ACTIVE,
        ),
        (
            "deactivate_variant",
            ExperimentVariantStatus.INACTIVE,
        ),
        (
            "archive_variant",
            ExperimentVariantStatus.ARCHIVED,
        ),
    ],
)
def test_variant_lifecycle_is_idempotent(
        method_name: str,
        target_status: ExperimentVariantStatus,
) -> None:
    """验证重复设置相同状态保持幂等"""
    repository, _, _ = create_repository()
    variant = create_variant(
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
        variant,
        updated_by="new_operator",
    )

    assert result is variant
    assert variant.status == str(
        target_status
    )
    assert variant.updated_by == (
        "original_operator"
    )


def test_variant_lifecycle_accepts_empty_operator() -> None:
    """验证生命周期方法允许写入空字符串操作人"""
    repository, _, _ = create_repository()
    variant = create_variant(
        status=str(
            ExperimentVariantStatus.INACTIVE
        )
    )

    repository.activate_variant(
        variant,
        updated_by="",
    )

    assert variant.status == str(
        ExperimentVariantStatus.ACTIVE
    )
    assert variant.updated_by == ""


@pytest.mark.parametrize(
    "method_name",
    [
        "activate_variant",
        "deactivate_variant",
    ],
)
def test_archived_variant_rejects_state_change(
        method_name: str,
) -> None:
    """验证归档实验分组不能重新启用或停用"""
    repository, _, _ = create_repository()
    variant = create_variant(
        status=str(
            ExperimentVariantStatus.ARCHIVED
        ),
        updated_by="original_operator",
    )
    method = getattr(
        repository,
        method_name,
    )

    with pytest.raises(
            ValueError,
            match=(
                "archived 实验分组不能修改状态"
            ),
    ):
        method(
            variant,
            updated_by="operator",
        )

    assert variant.status == str(
        ExperimentVariantStatus.ARCHIVED
    )
    assert variant.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "activate_variant",
        "deactivate_variant",
        "archive_variant",
    ],
)
def test_variant_lifecycle_rejects_unknown_status(
        method_name: str,
) -> None:
    """验证未知状态不能进入生命周期管理"""
    repository, _, _ = create_repository()
    variant = create_variant(
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
                "ExperimentVariantStatus"
            ),
    ):
        method(
            variant,
            updated_by="operator",
        )

    assert variant.status == "unknown"
