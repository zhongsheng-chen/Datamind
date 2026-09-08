"""模型元数据仓储测试

验证 MetadataRepository 的模型查询、列表筛选、创建、
普通字段更新，以及由 ModelGuard 控制的激活和归档状态迁移。

核心功能：
  - test_get_model_by_model_id:
    验证按模型 ID 查询并去除首尾空格
  - test_get_model_by_name:
    验证按模型名称查询并去除首尾空格
  - test_get_model_rejects_invalid_conditions:
    验证查询条件必须且只能提供一个
  - test_list_models:
    验证归档可见性、状态筛选、排序和分页
  - test_list_models_rejects_negative_pagination:
    验证拒绝负数分页参数
  - test_list_active_models:
    验证活跃模型列表
  - test_metadata_patch:
    验证更新结构和模型相关常量枚举
  - test_create_model:
    验证创建模型并设置 inactive 状态
  - test_update_model:
    验证普通元数据字段更新
  - test_mark_deleted:
    验证标记模型已删除
  - test_archive_model:
    验证允许的归档状态迁移
  - test_archive_model_rejects_invalid_transition:
    验证拒绝非法归档状态迁移
  - test_activate_model:
    验证从 inactive 激活模型
  - test_activate_model_rejects_invalid_transition:
    验证归档模型不能重新激活
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

import datamind.db.repositories.metadata as metadata_module
from datamind.constants import (
    Framework,
    ModelType,
    TaskType,
)
from datamind.db.models.metadata import Metadata
from datamind.db.repositories.metadata import (
    MetadataPatch,
    MetadataRepository,
)
from datamind.models.enums import MetadataStatus
from datamind.models.errors import InvalidModelStateError


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    9,
    30,
    tzinfo=timezone.utc,
)


def create_metadata(
        **overrides: Any,
) -> Metadata:
    """创建模型元数据测试对象"""
    values: dict[str, Any] = {
        "model_id": "mdl_0123456789abcdef",
        "name": "scorecard",
        "model_type": "logistic_regression",
        "task_type": "scoring",
        "framework": "sklearn",
        "description": "信用评分模型",
        "status": str(
            MetadataStatus.INACTIVE
        ),
        "created_by": "creator",
        "updated_by": "original_operator",
        "archived_at": None,
        "archived_by": None,
    }
    values.update(
        overrides
    )

    return Metadata(
        **values
    )


def create_repository(
        *,
        scalar_result: Metadata | None = None,
        list_result: list[Metadata] | None = None,
) -> tuple[
    MetadataRepository,
    AsyncMock,
    MagicMock,
]:
    """创建模型元数据仓储及会话方法替身"""
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
    repository = MetadataRepository(
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
async def test_get_model_by_model_id() -> None:
    """验证按模型 ID 查询并去除首尾空格"""
    expected = create_metadata()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_model(
        model_id=(
            "  mdl_0123456789abcdef  "
        )
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_model_by_name() -> None:
    """验证按模型名称查询并去除首尾空格"""
    expected = create_metadata()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_model(
        name="  scorecard  "
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.name = 'scorecard'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_model_returns_none_when_not_found() -> None:
    """验证模型不存在时返回 None"""
    repository, execute, _ = create_repository(
        scalar_result=None
    )

    result = await repository.get_model(
        name="missing-model"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {
            "model_id": (
                "mdl_0123456789abcdef"
            ),
            "name": "scorecard",
        },
        {
            "model_id": "",
        },
        {
            "name": "",
        },
        {
            "model_id": "   ",
        },
        {
            "name": "   ",
        },
        {
            "model_id": "   ",
            "name": "   ",
        },
    ],
)
async def test_get_model_rejects_invalid_conditions(
        arguments: dict[str, str],
) -> None:
    """验证查询条件必须且只能提供一个"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=(
                "必须且只能提供 model_id "
                "或 name 其中一个"
            ),
    ):
        await repository.get_model(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_models_excludes_archived_by_default() -> None:
    """验证模型列表默认排除归档模型"""
    models = [
        create_metadata()
    ]
    repository, execute, _ = create_repository(
        list_result=models
    )

    result = await repository.list_models()

    assert result == models
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.status != 'archived'"
        in sql
    )
    assert (
        "ORDER BY metadata.updated_at DESC, "
        "metadata.created_at DESC"
        in sql
    )
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_models_includes_archived_when_requested() -> None:
    """验证显式请求时包含归档模型"""
    repository, execute, _ = create_repository()

    await repository.list_models(
        include_archived=True,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "metadata.status =" not in sql
    assert "metadata.status !=" not in sql


@pytest.mark.asyncio
async def test_list_models_status_overrides_archive_filter() -> None:
    """验证显式状态过滤优先于默认归档排除"""
    repository, execute, _ = create_repository()

    await repository.list_models(
        status=MetadataStatus.ARCHIVED,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.status = 'archived'"
        in sql
    )
    assert "metadata.status !=" not in sql


@pytest.mark.asyncio
async def test_list_models_applies_filters_and_pagination() -> None:
    """验证列表筛选、状态、排序和分页"""
    models = [
        create_metadata(
            model_type=ModelType.XGBOOST,
            task_type=TaskType.CLASSIFICATION,
            framework=Framework.XGBOOST,
            status=str(
                MetadataStatus.ACTIVE
            ),
            created_by="model_admin",
        )
    ]
    repository, execute, _ = create_repository(
        list_result=models
    )

    result = await repository.list_models(
        model_type=ModelType.XGBOOST,
        task_type=TaskType.CLASSIFICATION,
        framework=Framework.XGBOOST,
        status=MetadataStatus.ACTIVE,
        created_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == models

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.model_type = 'xgboost'"
        in sql
    )
    assert (
        "metadata.task_type = "
        "'classification'"
        in sql
    )
    assert (
        "metadata.framework = 'xgboost'"
        in sql
    )
    assert (
        "metadata.status = 'active'"
        in sql
    )
    assert "metadata.status !=" not in sql
    assert (
        "metadata.created_by = "
        "'model_admin'"
        in sql
    )
    assert (
        "ORDER BY metadata.updated_at DESC, "
        "metadata.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_models_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_models(
        limit=0,
        offset=0,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "metadata.status != 'archived'" in sql
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
async def test_list_models_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """验证拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_models(
            **arguments
        )

    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_models() -> None:
    """验证活跃模型列表使用字符串状态和分页"""
    models = [
        create_metadata(
            status=str(
                MetadataStatus.ACTIVE
            )
        )
    ]
    repository, execute, _ = create_repository(
        list_result=models
    )

    result = await repository.list_active_models(
        limit=50,
        offset=5,
    )

    assert result == models

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "metadata.status = 'active'"
        in sql
    )
    assert "LIMIT 50" in sql
    assert "OFFSET 5" in sql


def test_metadata_patch_fields_and_defaults() -> None:
    """验证更新结构仅包含普通元数据字段"""
    patch = MetadataPatch()

    assert [
        field.name
        for field in fields(
            MetadataPatch
        )
    ] == [
        "name",
        "display_name",
        "model_type",
        "task_type",
        "framework",
        "description",
    ]
    assert patch.name is None
    assert patch.display_name is None
    assert patch.model_type is None
    assert patch.task_type is None
    assert patch.framework is None
    assert patch.description is None
    assert not hasattr(
        patch,
        "status",
    )
    assert not hasattr(
        patch,
        "deleted_at",
    )
    assert not hasattr(
        patch,
        "deleted_by",
    )
    assert not hasattr(
        patch,
        "archived_at",
    )
    assert not hasattr(
        patch,
        "archived_by",
    )
    assert not hasattr(
        patch,
        "__dict__",
    )


def test_metadata_patch_accepts_constant_enums() -> None:
    """验证更新结构接受模型相关常量枚举"""
    patch = MetadataPatch(
        model_type=ModelType.XGBOOST,
        task_type=TaskType.CLASSIFICATION,
        framework=Framework.XGBOOST,
    )

    assert patch.model_type is (
        ModelType.XGBOOST
    )
    assert patch.task_type is (
        TaskType.CLASSIFICATION
    )
    assert patch.framework is (
        Framework.XGBOOST
    )


def test_create_model() -> None:
    """验证创建模型并显式设置 inactive 状态"""
    repository, _, add = create_repository()

    metadata = repository.create_model(
        model_id="mdl_0123456789abcdef",
        name="scorecard",
        model_type=ModelType.LOGISTIC_REGRESSION,
        task_type=TaskType.SCORING,
        framework=Framework.SKLEARN,
        description="信用评分模型",
        created_by="creator",
        updated_by="operator",
    )

    add.assert_called_once_with(
        metadata
    )
    assert metadata.model_id == (
        "mdl_0123456789abcdef"
    )
    assert metadata.name == "scorecard"
    assert metadata.model_type == (
        "logistic_regression"
    )
    assert metadata.task_type == "scoring"
    assert metadata.framework == "sklearn"
    assert metadata.status == str(
        MetadataStatus.INACTIVE
    )
    assert metadata.description == (
        "信用评分模型"
    )
    assert metadata.created_by == "creator"
    assert metadata.updated_by == "operator"


# noinspection PyUnreachableCode
def test_create_model_allows_optional_fields() -> None:
    """验证创建模型时允许省略可选字段"""
    repository, _, add = create_repository()

    metadata = repository.create_model(
        model_id="mdl_minimum",
        name="minimum",
        model_type=ModelType.DECISION_TREE,
        task_type=TaskType.CLASSIFICATION,
        framework=Framework.SKLEARN,
    )

    add.assert_called_once_with(
        metadata
    )
    assert metadata.status == str(
        MetadataStatus.INACTIVE
    )
    assert metadata.description is None
    assert metadata.created_by is None
    assert metadata.updated_by is None


def test_update_model_updates_non_none_fields() -> None:
    """验证更新所有非空普通元数据字段"""
    repository, _, _ = create_repository()
    metadata = create_metadata()
    original_status = metadata.status
    original_archived_at = (
        metadata.archived_at
    )
    original_archived_by = (
        metadata.archived_by
    )

    result = repository.update_model(
        metadata,
        MetadataPatch(
            name="scorecard_v2",
            model_type=ModelType.XGBOOST,
            task_type=TaskType.CLASSIFICATION,
            framework=Framework.XGBOOST,
            description="更新后的模型说明",
        ),
        updated_by="operator",
    )

    assert result is metadata
    assert metadata.name == "scorecard_v2"
    assert metadata.model_type == "xgboost"
    assert metadata.task_type == (
        "classification"
    )
    assert metadata.framework == "xgboost"
    assert metadata.description == (
        "更新后的模型说明"
    )
    assert metadata.updated_by == "operator"
    assert metadata.status == original_status
    assert (
        metadata.archived_at
        == original_archived_at
    )
    assert (
        metadata.archived_by
        == original_archived_by
    )


def test_update_model_ignores_none_fields() -> None:
    """验证值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        description="原模型说明",
        updated_by="original_operator",
    )

    result = repository.update_model(
        metadata,
        MetadataPatch(
            name=None,
            model_type=None,
            task_type=None,
            framework=None,
            description=None,
        ),
    )

    assert result is metadata
    assert metadata.name == "scorecard"
    assert metadata.model_type == (
        "logistic_regression"
    )
    assert metadata.task_type == "scoring"
    assert metadata.framework == "sklearn"
    assert metadata.description == (
        "原模型说明"
    )
    assert metadata.updated_by == (
        "original_operator"
    )


def test_update_model_accepts_empty_strings() -> None:
    """验证空字符串作为明确更新值写入对象"""
    repository, _, _ = create_repository()
    metadata = create_metadata()

    repository.update_model(
        metadata,
        MetadataPatch(
            name="",
            description="",
        ),
        updated_by="",
    )

    assert metadata.name == ""
    assert metadata.description == ""
    assert metadata.updated_by == ""


@pytest.mark.parametrize(
    "current_status",
    [
        MetadataStatus.INACTIVE,
        MetadataStatus.DEPRECATED,
    ],
)
def test_archive_model(
        monkeypatch: pytest.MonkeyPatch,
        current_status: MetadataStatus,
) -> None:
    """验证从 inactive 或 deprecated 状态归档模型"""
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
    metadata = create_metadata(
        status=str(
            current_status
        )
    )

    monkeypatch.setitem(
        vars(metadata_module),
        "datetime",
        FrozenDateTime,
    )

    result = repository.archive_model(
        metadata,
        updated_by="operator",
    )

    assert result is metadata
    assert metadata.status == str(
        MetadataStatus.ARCHIVED
    )
    assert metadata.archived_at == CURRENT_TIME
    assert metadata.updated_by == "operator"
    assert metadata.archived_by == "operator"


# noinspection PyUnreachableCode
def test_archive_model_without_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证未提供操作人时不覆盖审计字段"""
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
    metadata = create_metadata(
        status=str(
            MetadataStatus.INACTIVE
        ),
        updated_by="original_operator",
        archived_by=None,
    )

    monkeypatch.setitem(
        vars(metadata_module),
        "datetime",
        FrozenDateTime,
    )

    repository.archive_model(
        metadata
    )

    assert metadata.status == str(
        MetadataStatus.ARCHIVED
    )
    assert metadata.archived_at == CURRENT_TIME
    assert metadata.updated_by == (
        "original_operator"
    )
    assert metadata.archived_by is None


def test_archive_model_accepts_empty_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证空字符串操作人会写入归档审计字段"""
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
    metadata = create_metadata(
        status=str(
            MetadataStatus.INACTIVE
        )
    )

    monkeypatch.setitem(
        vars(metadata_module),
        "datetime",
        FrozenDateTime,
    )

    repository.archive_model(
        metadata,
        updated_by="",
    )

    assert metadata.updated_by == ""
    assert metadata.archived_by == ""


def test_archive_model_is_idempotent() -> None:
    """验证重复归档不会修改时间和审计信息"""
    original_time = datetime(
        2026,
        7,
        20,
        10,
        0,
        tzinfo=timezone.utc,
    )
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.ARCHIVED
        ),
        archived_at=original_time,
        archived_by="original_archiver",
        updated_by="original_operator",
    )

    result = repository.archive_model(
        metadata,
        updated_by="new_operator",
    )

    assert result is metadata
    assert metadata.status == str(
        MetadataStatus.ARCHIVED
    )
    assert metadata.archived_at == original_time
    assert metadata.archived_by == (
        "original_archiver"
    )
    assert metadata.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_archive_model_rejects_active_status() -> None:
    """验证 active 状态不能直接归档"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.ACTIVE
        )
    )

    with pytest.raises(
            InvalidModelStateError,
            match=(
                "非法模型状态迁移: "
                "active -> archived"
            ),
    ):
        repository.archive_model(
            metadata,
            updated_by="operator",
        )

    assert metadata.status == str(
        MetadataStatus.ACTIVE
    )
    assert metadata.archived_at is None
    assert metadata.archived_by is None
    assert metadata.updated_by == (
        "original_operator"
    )


def test_activate_model() -> None:
    """验证从 inactive 状态激活模型"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.INACTIVE
        )
    )

    result = repository.activate_model(
        metadata,
        updated_by="operator",
    )

    assert result is metadata
    assert metadata.status == str(
        MetadataStatus.ACTIVE
    )
    assert metadata.updated_by == "operator"


def test_activate_model_without_operator() -> None:
    """验证激活时未提供操作人则保留原值"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.INACTIVE
        ),
        updated_by="original_operator",
    )

    repository.activate_model(
        metadata
    )

    assert metadata.status == str(
        MetadataStatus.ACTIVE
    )
    assert metadata.updated_by == (
        "original_operator"
    )


def test_activate_model_accepts_empty_operator() -> None:
    """验证空字符串操作人会写入更新字段"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.INACTIVE
        )
    )

    repository.activate_model(
        metadata,
        updated_by="",
    )

    assert metadata.status == str(
        MetadataStatus.ACTIVE
    )
    assert metadata.updated_by == ""


def test_activate_model_is_idempotent() -> None:
    """验证重复激活不会修改更新人"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            MetadataStatus.ACTIVE
        ),
        updated_by="original_operator",
    )

    result = repository.activate_model(
        metadata,
        updated_by="new_operator",
    )

    assert result is metadata
    assert metadata.status == str(
        MetadataStatus.ACTIVE
    )
    assert metadata.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "current_status",
    [
        MetadataStatus.DEPRECATED,
        MetadataStatus.ARCHIVED,
    ],
)
def test_activate_model_rejects_invalid_transition(
        current_status: MetadataStatus,
) -> None:
    """验证 deprecated 和 archived 状态不能激活"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
        status=str(
            current_status
        )
    )

    with pytest.raises(
            InvalidModelStateError,
            match=(
                "非法模型状态迁移: "
                f"{current_status} -> active"
            ),
    ):
        repository.activate_model(
            metadata,
            updated_by="operator",
        )

    assert metadata.status == str(
        current_status
    )
    assert metadata.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "archive_model",
        "activate_model",
    ],
)
def test_lifecycle_methods_reject_unknown_status(
        method_name: str,
) -> None:
    """验证未知状态字符串不能进入生命周期迁移"""
    repository, _, _ = create_repository()
    metadata = create_metadata(
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
                "MetadataStatus"
            ),
    ):
        method(
            metadata,
            updated_by="operator",
        )

    assert metadata.status == "unknown"


def test_mark_deleted() -> None:
    """验证标记模型已删除并记录操作人"""
    repository, _, _ = create_repository()
    metadata = create_metadata()
    deleted_at = datetime.now(timezone.utc)

    result = repository.mark_deleted(
        metadata,
        deleted_at=deleted_at,
        deleted_by="operator",
        deletion_id="del_test",
        deletion_reason="模型停用",
    )

    assert result is metadata
    assert metadata.deleted_at is deleted_at
    assert metadata.deleted_by == "operator"
    assert metadata.updated_by == "operator"
    assert metadata.status == "archived"
    assert metadata.archived_at is deleted_at
    assert metadata.archived_by == "operator"
    assert metadata.deletion_id == "del_test"
    assert metadata.deletion_reason == "模型停用"


def test_restore_model() -> None:
    """验证恢复逻辑删除模型并重置为 inactive"""
    repository, _, _ = create_repository()
    metadata: Any = create_metadata(
        status="archived",
        deleted_at=datetime.now(timezone.utc),
        deleted_by="operator",
        deletion_id="del_test",
        deletion_reason="模型停用",
        archived_at=datetime.now(timezone.utc),
        archived_by="operator",
    )

    result = repository.restore_model(
        metadata,
        restored_by="admin",
    )

    assert result is metadata
    assert metadata.status == "inactive"
    assert metadata.deleted_at is None
    assert metadata.deletion_id is None
    assert metadata.archived_at is None
    assert metadata.restored_at is not None
    assert metadata.restored_by == "admin"
