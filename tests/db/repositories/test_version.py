# tests/db/repositories/test_version.py

"""模型版本仓储测试

验证 VersionRepository 的版本查询、列表筛选、创建、
普通字段更新，以及由 ModelGuard 控制的版本生命周期迁移。

核心功能：
  - test_get_version:
    验证按版本 ID 查询
  - test_get_latest_version:
    验证按创建时间获取最新版本
  - test_list_versions:
    验证归档可见性、状态筛选、排序和分页
  - test_version_patch:
    验证更新结构和框架枚举
  - test_create_version:
    验证创建版本并设置 inactive 状态
  - test_update_version:
    验证普通版本字段更新
  - test_mark_deleted:
    验证标记版本已删除
  - test_archive_version:
    验证允许的归档状态迁移
  - test_activate_version:
    验证从 inactive 激活版本
  - test_deprecate_version:
    验证从 active 废弃版本
  - test_version_lifecycle_rejects_invalid_transition:
    验证拒绝非法状态迁移
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

import datamind.db.repositories.version as version_module
from datamind.constants import Framework
from datamind.db.models.versions import Version
from datamind.db.repositories.version import (
    VersionPatch,
    VersionRepository,
)
from datamind.models.enums import VersionStatus
from datamind.models.errors import InvalidModelStateError


CURRENT_TIME = datetime(
    2026,
    7,
    26,
    10,
    30,
    tzinfo=timezone.utc,
)


def create_version(
        **overrides: Any,
) -> Version:
    """创建模型版本测试对象"""
    values: dict[str, Any] = {
        "version_id": "ver_0123456789abcdef",
        "model_id": "mdl_0123456789abcdef",
        "version": "1.0.0",
        "framework": "sklearn",
        "input_schema": {
            "type": "object",
        },
        "output_schema": {
            "type": "object",
        },
        "status": str(
            VersionStatus.INACTIVE
        ),
        "bento_tag": "scorecard:abc123def",
        "model_path": (
            "s3://datamind/models/"
            "mdl_0123456789abcdef/"
            "1.0.0/scorecard.pkl"
        ),
        "model_key": (
            "models/"
            "mdl_0123456789abcdef/"
            "1.0.0/scorecard.pkl"
        ),
        "input_schema_key": (
            "schemas/"
            "mdl_0123456789abcdef/"
            "1.0.0/input.json"
        ),
        "output_schema_key": (
            "schemas/"
            "mdl_0123456789abcdef/"
            "1.0.0/output.json"
        ),
        "params": {
            "solver": "lbfgs",
        },
        "metrics": {
            "auc": 0.81,
        },
        "description": "信用评分模型版本",
        "created_by": "creator",
        "updated_by": "original_operator",
        "archived_at": None,
        "archived_by": None,
    }
    values.update(
        overrides
    )

    return Version(
        **values
    )


def create_repository(
        *,
        scalar_result: Version | None = None,
        list_result: list[Version] | None = None,
) -> tuple[
    VersionRepository,
    AsyncMock,
    MagicMock,
]:
    """创建模型版本仓储及会话方法替身"""
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
    repository = VersionRepository(
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
async def test_get_version() -> None:
    """验证按版本 ID 查询"""
    expected = create_version()
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_version(
        "ver_0123456789abcdef"
    )

    assert result is expected
    execute.assert_awaited_once()

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.version_id = "
        "'ver_0123456789abcdef'"
        in sql
    )


@pytest.mark.asyncio
async def test_get_version_returns_none_when_not_found() -> None:
    """验证版本不存在时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_version(
        "ver_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_latest_version() -> None:
    """验证按创建时间获取最新版本"""
    expected = create_version(
        version="2.0.0"
    )
    repository, execute, _ = create_repository(
        scalar_result=expected
    )

    result = await repository.get_latest_version(
        "mdl_0123456789abcdef"
    )

    assert result is expected

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "ORDER BY versions.created_at DESC"
        in sql
    )
    assert "LIMIT 1" in sql


@pytest.mark.asyncio
async def test_get_latest_version_returns_none() -> None:
    """验证模型没有版本时返回 None"""
    repository, execute, _ = create_repository()

    result = await repository.get_latest_version(
        "mdl_missing"
    )

    assert result is None
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_versions_excludes_archived_by_default() -> None:
    """验证版本列表默认排除归档版本"""
    versions = [
        create_version()
    ]
    repository, execute, _ = create_repository(
        list_result=versions
    )

    result = await repository.list_versions()

    assert result == versions

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.status != 'archived'"
        in sql
    )
    assert (
        "ORDER BY versions.created_at DESC"
        in sql
    )
    assert " LIMIT " not in sql
    assert " OFFSET " not in sql


@pytest.mark.asyncio
async def test_list_versions_includes_archived_when_requested() -> None:
    """验证显式请求时包含归档版本"""
    repository, execute, _ = create_repository()

    await repository.list_versions(
        include_archived=True,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert "versions.status =" not in sql
    assert "versions.status !=" not in sql


@pytest.mark.asyncio
async def test_list_versions_status_overrides_archive_filter() -> None:
    """验证显式状态过滤优先于默认归档排除"""
    repository, execute, _ = create_repository()

    await repository.list_versions(
        status=VersionStatus.ARCHIVED,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.status = 'archived'"
        in sql
    )
    assert "versions.status !=" not in sql


@pytest.mark.asyncio
async def test_list_versions_applies_filters_and_pagination() -> None:
    """验证列表筛选、状态、排序和分页"""
    versions = [
        create_version(
            framework="xgboost",
            status=str(
                VersionStatus.ACTIVE
            ),
        )
    ]
    repository, execute, _ = create_repository(
        list_result=versions
    )

    result = await repository.list_versions(
        model_id="mdl_0123456789abcdef",
        version="2.0.0",
        framework=Framework.XGBOOST,
        status=VersionStatus.ACTIVE,
        created_by="model_admin",
        limit=25,
        offset=10,
    )

    assert result == versions

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.model_id = "
        "'mdl_0123456789abcdef'"
        in sql
    )
    assert (
        "versions.version = '2.0.0'"
        in sql
    )
    assert (
        "versions.framework = 'xgboost'"
        in sql
    )
    assert (
        "versions.status = 'active'"
        in sql
    )
    assert "versions.status !=" not in sql
    assert (
        "versions.created_by = 'model_admin'"
        in sql
    )
    assert (
        "ORDER BY versions.created_at DESC"
        in sql
    )
    assert "LIMIT 25" in sql
    assert "OFFSET 10" in sql


@pytest.mark.asyncio
async def test_list_versions_applies_zero_pagination() -> None:
    """验证零值分页参数仍会应用"""
    repository, execute, _ = create_repository()

    await repository.list_versions(
        limit=0,
        offset=0,
    )

    sql = compile_statement(
        get_executed_statement(
            execute
        )
    )

    assert (
        "versions.status != 'archived'"
        in sql
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
    ],
)
async def test_list_versions_rejects_negative_pagination(
        arguments: dict[str, int],
        expected_message: str,
) -> None:
    """验证拒绝负数分页参数"""
    repository, execute, _ = create_repository()

    with pytest.raises(
            ValueError,
            match=expected_message,
    ):
        await repository.list_versions(
            **arguments
        )

    execute.assert_not_awaited()


def test_version_patch_fields_and_defaults() -> None:
    """验证更新结构仅包含普通版本字段"""
    patch = VersionPatch()

    assert [
        field.name
        for field in fields(
            VersionPatch
        )
    ] == [
        "version",
        "framework",
        "input_schema",
        "output_schema",
        "bento_tag",
        "model_path",
        "model_key",
        "input_schema_key",
        "output_schema_key",
        "params",
        "metrics",
        "description",
    ]
    assert patch.version is None
    assert patch.framework is None
    assert patch.input_schema is None
    assert patch.output_schema is None
    assert patch.bento_tag is None
    assert patch.model_path is None
    assert patch.model_key is None
    assert patch.input_schema_key is None
    assert patch.output_schema_key is None
    assert patch.params is None
    assert patch.metrics is None
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


def test_version_patch_accepts_framework_enum() -> None:
    """验证更新结构接受框架枚举"""
    patch = VersionPatch(
        framework=Framework.XGBOOST
    )

    assert patch.framework is (
        Framework.XGBOOST
    )


def test_create_version() -> None:
    """验证创建版本并显式设置 inactive 状态"""
    repository, _, add = create_repository()

    version = repository.create_version(
        version_id="ver_0123456789abcdef",
        model_id="mdl_0123456789abcdef",
        version="1.0.0",
        framework=Framework.SKLEARN,
        bento_tag="scorecard:abcdefgh",
        model_path=(
            "s3://datamind/models/"
            "mdl_0123456789abcdef/"
            "1.0.0/scorecard.pkl"
        ),
        model_key=(
            "models/"
            "mdl_0123456789abcdef/"
            "1.0.0/scorecard.pkl"
        ),
        current_artifact_id="art_0123456789abcdef",
        artifact_revision=1,
        artifact_sha256="a" * 64,
        artifact_digest="b" * 64,
        input_schema={
            "type": "object",
        },
        output_schema={
            "type": "object",
        },
        input_schema_key="schemas/input.json",
        output_schema_key="schemas/output.json",
        params={
            "solver": "lbfgs",
        },
        metrics={
            "auc": 0.81,
        },
        description="信用评分模型版本",
        created_by="creator",
    )

    add.assert_called_once_with(
        version
    )
    assert version.version_id == (
        "ver_0123456789abcdef"
    )
    assert version.model_id == (
        "mdl_0123456789abcdef"
    )
    assert version.version == "1.0.0"
    assert version.framework == "sklearn"
    assert version.status == str(
        VersionStatus.INACTIVE
    )
    assert version.bento_tag == (
        "scorecard:abcdefgh"
    )
    assert version.current_artifact_id == "art_0123456789abcdef"
    assert version.artifact_revision == 1
    assert version.params == {
        "solver": "lbfgs",
    }
    assert version.metrics == {
        "auc": 0.81,
    }
    assert version.created_by == "creator"


# noinspection PyUnreachableCode
def test_create_version_allows_optional_fields() -> None:
    """验证创建版本时允许省略可选字段"""
    repository, _, add = create_repository()

    version = repository.create_version(
        version_id="ver_minimum",
        model_id="mdl_minimum",
        version="1.0.0",
        framework=Framework.SKLEARN,
        bento_tag="minimum:abcdefgh",
        model_path="/models/minimum.pkl",
        model_key="models/minimum.pkl",
        current_artifact_id="art_minimum",
        artifact_sha256="a" * 64,
        artifact_digest="b" * 64,
    )

    add.assert_called_once_with(
        version
    )
    assert version.status == str(
        VersionStatus.INACTIVE
    )
    assert version.input_schema is None
    assert version.output_schema is None
    assert version.params is None
    assert version.metrics is None
    assert version.description is None
    assert version.created_by is None


def test_update_version() -> None:
    """验证普通版本字段更新"""
    repository, _, _ = create_repository()
    version = create_version()
    original_status = version.status
    original_archived_at = (
        version.archived_at
    )
    original_archived_by = (
        version.archived_by
    )

    result = repository.update_version(
        version,
        VersionPatch(
            version="2.0.0",
            framework=Framework.XGBOOST,
            input_schema={
                "type": "object",
                "required": [
                    "income",
                ],
            },
            output_schema={
                "type": "object",
                "required": [
                    "probability",
                ],
            },
            bento_tag="scorecard:ijklmnop",
            model_path="/models/scorecard-v2.pkl",
            model_key="models/scorecard-v2.pkl",
            input_schema_key="schemas/input-v2.json",
            output_schema_key="schemas/output-v2.json",
            params={
                "max_depth": 6,
            },
            metrics={
                "auc": 0.85,
            },
            description="更新后的版本说明",
        ),
        updated_by="operator",
    )

    assert result is version
    assert version.version == "2.0.0"
    assert version.framework == "xgboost"
    assert version.bento_tag == (
        "scorecard:ijklmnop"
    )
    assert version.model_path == (
        "/models/scorecard-v2.pkl"
    )
    assert version.model_key == (
        "models/scorecard-v2.pkl"
    )
    assert version.params == {
        "max_depth": 6,
    }
    assert version.metrics == {
        "auc": 0.85,
    }
    assert version.description == (
        "更新后的版本说明"
    )
    assert version.updated_by == "operator"
    assert version.status == original_status
    assert (
        version.archived_at
        == original_archived_at
    )
    assert (
        version.archived_by
        == original_archived_by
    )


def test_update_version_ignores_none_fields() -> None:
    """验证值为 None 的字段不会覆盖原值"""
    repository, _, _ = create_repository()
    version = create_version(
        description="原版本说明"
    )

    repository.update_version(
        version,
        VersionPatch(),
    )

    assert version.version == "1.0.0"
    assert version.framework == "sklearn"
    assert version.description == (
        "原版本说明"
    )


@pytest.mark.parametrize(
    "current_status",
    [
        VersionStatus.INACTIVE,
        VersionStatus.DEPRECATED,
    ],
)
def test_archive_version(
        monkeypatch: pytest.MonkeyPatch,
        current_status: VersionStatus,
) -> None:
    """验证允许的状态可以归档"""
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
    version = create_version(
        status=str(
            current_status
        )
    )

    monkeypatch.setitem(
        vars(version_module),
        "datetime",
        FrozenDateTime,
    )

    result = repository.archive_version(
        version,
        updated_by="operator",
    )

    assert result is version
    assert version.status == str(
        VersionStatus.ARCHIVED
    )
    assert version.archived_at == CURRENT_TIME
    assert version.updated_by == "operator"
    assert version.archived_by == "operator"


def test_archive_version_is_idempotent() -> None:
    """验证重复归档保持幂等"""
    archived_at = datetime(
        2026,
        7,
        20,
        tzinfo=timezone.utc,
    )
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.ARCHIVED
        ),
        archived_at=archived_at,
        archived_by="archiver",
        updated_by="original_operator",
    )

    result = repository.archive_version(
        version,
        updated_by="new_operator",
    )

    assert result is version
    assert version.archived_at == archived_at
    assert version.archived_by == "archiver"
    assert version.updated_by == (
        "original_operator"
    )


# noinspection PyUnreachableCode
def test_archive_version_rejects_active_status() -> None:
    """验证 active 状态不能直接归档"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.ACTIVE
        )
    )

    with pytest.raises(
            InvalidModelStateError,
    ):
        repository.archive_version(
            version
        )

    assert version.status == str(
        VersionStatus.ACTIVE
    )
    assert version.archived_at is None


def test_activate_version() -> None:
    """验证从 inactive 状态激活版本"""
    repository, _, _ = create_repository()
    version = create_version()

    result = repository.activate_version(
        version,
        updated_by="operator",
    )

    assert result is version
    assert version.status == str(
        VersionStatus.ACTIVE
    )
    assert version.updated_by == "operator"


def test_activate_version_is_idempotent() -> None:
    """验证重复激活保持幂等"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.ACTIVE
        ),
        updated_by="original_operator",
    )

    result = repository.activate_version(
        version,
        updated_by="new_operator",
    )

    assert result is version
    assert version.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "current_status",
    [
        VersionStatus.DEPRECATED,
        VersionStatus.ARCHIVED,
    ],
)
def test_activate_version_rejects_invalid_transition(
        current_status: VersionStatus,
) -> None:
    """验证 deprecated 和 archived 状态不能激活"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            current_status
        )
    )

    with pytest.raises(
            InvalidModelStateError,
    ):
        repository.activate_version(
            version
        )

    assert version.status == str(
        current_status
    )


def test_deprecate_version() -> None:
    """验证从 active 状态废弃版本"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.ACTIVE
        )
    )

    result = repository.deprecate_version(
        version,
        updated_by="operator",
    )

    assert result is version
    assert version.status == str(
        VersionStatus.DEPRECATED
    )
    assert version.updated_by == "operator"


def test_deprecate_inactive_version() -> None:
    """验证从 inactive 状态废弃版本"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.INACTIVE
        )
    )

    result = repository.deprecate_version(
        version,
        updated_by="operator",
    )

    assert result is version
    assert version.status == str(
        VersionStatus.DEPRECATED
    )
    assert version.updated_by == "operator"


def test_deprecate_version_is_idempotent() -> None:
    """验证重复废弃保持幂等"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            VersionStatus.DEPRECATED
        ),
        updated_by="original_operator",
    )

    result = repository.deprecate_version(
        version,
        updated_by="new_operator",
    )

    assert result is version
    assert version.updated_by == (
        "original_operator"
    )


@pytest.mark.parametrize(
    "current_status",
    [
        VersionStatus.ARCHIVED,
    ],
)
def test_deprecate_version_rejects_invalid_transition(
        current_status: VersionStatus,
) -> None:
    """验证 archived 状态不能废弃"""
    repository, _, _ = create_repository()
    version = create_version(
        status=str(
            current_status
        )
    )

    with pytest.raises(
            InvalidModelStateError,
    ):
        repository.deprecate_version(
            version
        )

    assert version.status == str(
        current_status
    )


@pytest.mark.parametrize(
    "method_name",
    [
        "archive_version",
        "activate_version",
        "deprecate_version",
    ],
)
def test_version_lifecycle_rejects_unknown_status(
        method_name: str,
) -> None:
    """验证未知状态不能进入版本生命周期迁移"""
    repository, _, _ = create_repository()
    version = create_version(
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
                "VersionStatus"
            ),
    ):
        method(
            version
        )

    assert version.status == "unknown"


def test_mark_deleted() -> None:
    """验证标记版本已删除并记录操作人"""
    repository, _, _ = create_repository()
    version = create_version()
    deleted_at = datetime.now(timezone.utc)

    result = repository.mark_deleted(
        version,
        deleted_at=deleted_at,
        deleted_by="operator",
        deletion_id="del_test",
        deletion_reason="版本停用",
    )

    assert result is version
    assert version.deleted_at is deleted_at
    assert version.deleted_by == "operator"
    assert version.updated_by == "operator"
    assert version.status == "archived"
    assert version.archived_at is deleted_at
    assert version.archived_by == "operator"
    assert version.deletion_id == "del_test"
    assert version.deletion_reason == "版本停用"


def test_restore_version() -> None:
    """验证恢复逻辑删除版本并重置为 inactive"""
    repository, _, _ = create_repository()
    version: Any = create_version(
        status="archived",
        deleted_at=datetime.now(timezone.utc),
        deleted_by="operator",
        deletion_id="del_test",
        deletion_reason="版本停用",
        archived_at=datetime.now(timezone.utc),
        archived_by="operator",
    )

    result = repository.restore_version(
        version,
        restored_by="admin",
    )

    assert result is version
    assert version.status == "inactive"
    assert version.deleted_at is None
    assert version.deletion_id is None
    assert version.archived_at is None
    assert version.restored_at is not None
    assert version.restored_by == "admin"
