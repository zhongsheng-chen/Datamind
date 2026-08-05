# tests/models/test_resolver.py

"""模型解析器测试

验证模型和版本解析及版本归属约束。

核心功能：
  - test_resolve_model_prioritizes_model_id:
    验证模型解析优先按模型 ID 查询
  - test_resolve_model_falls_back_to_name:
    验证模型 ID 未命中时按名称回退查询
  - test_resolve_model_rejects_unknown_model:
    验证拒绝不存在的模型
  - test_resolve_model_requires_identifier:
    验证解析模型必须提供模型标识
  - test_resolve_version_prioritizes_version_id:
    验证版本解析优先按版本 ID 查询
  - test_resolve_version_falls_back_to_version_number:
    验证未提供版本 ID 时按版本号查询
  - test_resolve_version_includes_archived_version:
    验证按版本号解析时不会隐藏归档版本
  - test_resolve_version_rejects_foreign_model_version:
    验证拒绝属于其他模型的版本
  - test_resolve_version_rejects_unknown_version_number:
    验证拒绝不存在的版本号
  - test_resolve_version_rejects_unknown_version_id:
    验证拒绝不存在的版本 ID
  - test_resolve_version_requires_identifier:
    验证解析版本必须提供版本标识
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from datamind.models.errors import ModelNotFoundError, VersionNotFoundError
from datamind.models.resolver import ModelResolver


@pytest.mark.asyncio
async def test_resolve_model_prioritizes_model_id() -> None:
    """测试同时提供模型 ID 和名称时优先按 ID 查询"""
    model = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
    )
    metadata_repo = AsyncMock()
    metadata_repo.get_model.return_value = model
    resolver = ModelResolver(
        metadata_repo,
        AsyncMock(),
    )

    result = await resolver.resolve_model(
        model_id="mdl_test",
        name="scorecard",
    )

    assert result is model
    metadata_repo.get_model.assert_awaited_once_with(
        model_id="mdl_test"
    )


@pytest.mark.asyncio
async def test_resolve_model_falls_back_to_name() -> None:
    """测试模型 ID 未命中时按名称回退查询"""
    model = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
    )
    metadata_repo = AsyncMock()
    metadata_repo.get_model.side_effect = [
        None,
        model,
    ]
    resolver = ModelResolver(
        metadata_repo,
        AsyncMock(),
    )

    result = await resolver.resolve_model(
        model_id="mdl_missing",
        name="scorecard",
    )

    assert result is model
    assert metadata_repo.get_model.await_args_list == [
        call(model_id="mdl_missing"),
        call(name="scorecard"),
    ]


@pytest.mark.asyncio
async def test_resolve_model_rejects_unknown_model() -> None:
    """测试拒绝不存在的模型"""
    metadata_repo = AsyncMock()
    metadata_repo.get_model.return_value = None
    resolver = ModelResolver(
        metadata_repo,
        AsyncMock(),
    )

    with pytest.raises(
        ModelNotFoundError,
        match="model_id=mdl_missing, name=未提供",
    ):
        await resolver.resolve_model(
            model_id="mdl_missing"
        )


@pytest.mark.asyncio
async def test_resolve_model_requires_identifier() -> None:
    """测试解析模型必须提供模型标识"""
    metadata_repo = AsyncMock()
    resolver = ModelResolver(
        metadata_repo,
        AsyncMock(),
    )

    with pytest.raises(
        ModelNotFoundError,
        match="model_id=未提供, name=未提供",
    ):
        await resolver.resolve_model()

    metadata_repo.get_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_version_prioritizes_version_id() -> None:
    """测试同时提供版本 ID 和版本号时优先按 ID 查询"""
    version = SimpleNamespace(version_id="ver_test", model_id="mdl_test")
    version_repo = AsyncMock()
    version_repo.get_version.return_value = version
    resolver = ModelResolver(AsyncMock(), version_repo)

    result = await resolver.resolve_version(
        model_id="mdl_test",
        version_id="ver_test",
        version="1.0.0",
    )

    assert result is version
    version_repo.get_version.assert_awaited_once_with(
        "ver_test"
    )
    version_repo.list_versions.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_version_falls_back_to_version_number() -> None:
    """测试未提供版本 ID 时按版本号查询"""
    expected = SimpleNamespace(
        version_id="ver_test",
        model_id="mdl_test",
        version="1.0.0",
    )
    version_repo = AsyncMock()
    version_repo.list_versions.return_value = [
        expected,
    ]
    resolver = ModelResolver(
        AsyncMock(),
        version_repo,
    )

    result = await resolver.resolve_version(
        model_id="mdl_test",
        version="1.0.0",
    )

    assert result is expected
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        version="1.0.0",
        include_archived=True,
        limit=1,
    )
    version_repo.get_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_version_includes_archived_version() -> None:
    """测试按版本号解析时返回归档版本"""
    archived_version = SimpleNamespace(
        version_id="ver_archived",
        model_id="mdl_test",
        version="1.0.0",
        status="archived",
    )
    version_repo = AsyncMock()
    version_repo.list_versions.return_value = [
        archived_version
    ]
    resolver = ModelResolver(
        AsyncMock(),
        version_repo,
    )

    result = await resolver.resolve_version(
        model_id="mdl_test",
        version="1.0.0",
    )

    assert result is archived_version
    version_repo.list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        version="1.0.0",
        include_archived=True,
        limit=1,
    )


@pytest.mark.asyncio
async def test_resolve_version_rejects_foreign_model_version() -> None:
    """测试拒绝属于其他模型的版本"""
    version_repo = AsyncMock()
    version_repo.get_version.return_value = SimpleNamespace(
        version_id="ver_foreign",
        model_id="mdl_other",
    )
    resolver = ModelResolver(AsyncMock(), version_repo)

    with pytest.raises(VersionNotFoundError, match="版本不存在"):
        await resolver.resolve_version(
            model_id="mdl_test",
            version_id="ver_foreign",
        )


@pytest.mark.asyncio
async def test_resolve_version_rejects_unknown_version_number() -> None:
    """测试拒绝不存在的版本号"""
    version_repo = AsyncMock()
    version_repo.list_versions.return_value = []
    resolver = ModelResolver(
        AsyncMock(),
        version_repo,
    )

    with pytest.raises(VersionNotFoundError, match="version=2.0.0"):
        await resolver.resolve_version(
            model_id="mdl_test",
            version="2.0.0",
        )


@pytest.mark.asyncio
async def test_resolve_version_rejects_unknown_version_id() -> None:
    """测试拒绝不存在的版本 ID"""
    version_repo = AsyncMock()
    version_repo.get_version.return_value = None
    resolver = ModelResolver(
        AsyncMock(),
        version_repo,
    )

    with pytest.raises(VersionNotFoundError, match="ver_missing"):
        await resolver.resolve_version(
            model_id="mdl_test",
            version_id="ver_missing",
        )


@pytest.mark.asyncio
async def test_resolve_version_requires_identifier() -> None:
    """测试解析版本必须提供版本标识"""
    version_repo = AsyncMock()
    resolver = ModelResolver(
        AsyncMock(),
        version_repo,
    )

    with pytest.raises(VersionNotFoundError, match="必须提供"):
        await resolver.resolve_version(
            model_id="mdl_test"
        )

    version_repo.get_version.assert_not_awaited()
    version_repo.list_versions.assert_not_awaited()
