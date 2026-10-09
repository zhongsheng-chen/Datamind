"""模型加载器测试.

验证模型加载器复用 BentoML 模型，
并在模型缺失时从统一存储完成同步。

核心功能：
  - test_loader_uses_default_dependencies:
    验证默认使用全局存储和 BentoML 后端
  - test_load_returns_existing_bento_model:
    验证直接复用 BentoML 中已有的模型
  - test_load_materializes_missing_bento_model:
    验证从统一存储同步缺失的 BentoML 模型
  - test_load_reuses_concurrently_materialized_model:
    验证并发同步冲突后复用已有模型
  - test_load_rejects_blank_reference:
    验证拒绝空模型引用
  - test_loader_initializes_storage_after_bento_model_miss:
    测试 Bento 模型缺失时才连接对象存储
  - test_loader_retries_storage_after_dependency_recovers:
    测试对象存储晚于运行服务恢复后可以再次加载模型
"""

from unittest.mock import MagicMock

import pytest
from bentoml.exceptions import BentoMLException, NotFound

import datamind.runtime.loader as loader_module
from datamind.models.artifact import ModelArtifactLoader
from datamind.runtime.loader import ModelLoader
from datamind.storage.errors import StorageConnectionError


def test_loader_uses_default_dependencies(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有 Bento 模型不要求对象存储在启动时可用."""
    storage = MagicMock()
    backend = MagicMock()
    get_storage = MagicMock(return_value=storage)
    expected = object()
    backend.load.return_value = expected
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        get_storage,
    )
    monkeypatch.setitem(
        vars(loader_module),
        "BentoBackend",
        lambda: backend,
    )

    result = ModelLoader().load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is expected
    backend.load.assert_called_once_with(
        framework="sklearn",
        tag="scorecard:test",
    )
    get_storage.assert_not_called()
    storage.load_by_key.assert_not_called()


def test_loader_initializes_storage_after_bento_model_miss(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Bento 模型缺失时才连接对象存储."""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    get_storage = MagicMock(return_value=storage)
    backend = MagicMock()
    loaded_model = object()
    backend.load.side_effect = [
        NotFound("model missing"),
        loaded_model,
    ]
    monkeypatch.setitem(vars(loader_module), "get_storage", get_storage)
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        MagicMock(return_value=object()),
    )

    result = ModelLoader(backend=backend).load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is loaded_model
    get_storage.assert_called_once_with()
    storage.load_by_key.assert_called_once_with(
        "models/mdl/ver/art/model.pkl"
    )


def test_loader_retries_storage_after_dependency_recovers(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试对象存储晚于运行服务恢复后可以再次加载模型."""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    get_storage = MagicMock(side_effect=[
        StorageConnectionError("minio unavailable"),
        storage,
    ])
    backend = MagicMock()
    loaded_model = object()
    backend.load.side_effect = [
        NotFound("model missing"),
        NotFound("model missing"),
        loaded_model,
    ]
    monkeypatch.setitem(vars(loader_module), "get_storage", get_storage)
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        MagicMock(return_value=object()),
    )
    loader = ModelLoader(backend=backend)

    with pytest.raises(StorageConnectionError, match="minio unavailable"):
        loader.load(
            framework="sklearn",
            bento_tag="scorecard:test",
            model_key="models/mdl/ver/art/model.pkl",
        )

    result = loader.load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is loaded_model
    assert get_storage.call_count == 2
    storage.load_by_key.assert_called_once_with(
        "models/mdl/ver/art/model.pkl"
    )


def test_load_returns_existing_bento_model(
) -> None:
    """测试直接复用 BentoML 中已有的模型."""
    storage = MagicMock()
    backend = MagicMock()
    expected = object()
    backend.load.return_value = expected

    result = ModelLoader(
        storage=storage,
        backend=backend,
    ).load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is expected
    storage.load_by_key.assert_not_called()
    backend.save.assert_not_called()


def test_load_materializes_missing_bento_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从统一存储同步缺失的 BentoML 模型."""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    backend = MagicMock()
    loaded_model = object()
    backend.load.side_effect = [
        NotFound("model missing"),
        loaded_model,
    ]
    artifact_model = object()
    load_artifact = MagicMock(
        return_value=artifact_model
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        load_artifact,
    )

    result = ModelLoader(
        storage=storage,
        backend=backend,
    ).load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is loaded_model
    storage.load_by_key.assert_called_once_with(
        "models/mdl/ver/art/model.pkl"
    )
    load_artifact.assert_called_once_with(
        framework="sklearn",
        data=b"model-data",
    )
    backend.save.assert_called_once_with(
        name="scorecard:test",
        framework="sklearn",
        model=artifact_model,
        labels={
            "model_key": "models/mdl/ver/art/model.pkl",
        },
    )
    assert backend.load.call_count == 2


def test_load_reuses_concurrently_materialized_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试并发同步冲突后复用已有模型."""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    backend = MagicMock()
    loaded_model = object()
    backend.load.side_effect = [
        NotFound("model missing"),
        loaded_model,
    ]
    backend.save.side_effect = BentoMLException(
        "model already exists"
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        MagicMock(return_value=object()),
    )

    result = ModelLoader(
        storage=storage,
        backend=backend,
    ).load(
        framework="sklearn",
        bento_tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is loaded_model
    assert backend.load.call_count == 2


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("bento_tag", "", "bento_tag 不能为空"),
        ("bento_tag", "   ", "bento_tag 不能为空"),
        ("model_key", "", "model_key 不能为空"),
        ("model_key", "   ", "model_key 不能为空"),
    ],
)
def test_load_rejects_blank_reference(
        field: str,
        value: str,
        message: str,
) -> None:
    """测试拒绝空模型引用."""
    storage = MagicMock()
    backend = MagicMock()
    references = {
        "bento_tag": "scorecard:test",
        "model_key": "models/mdl/ver/art/model.pkl",
        field: value,
    }

    with pytest.raises(
            ValueError,
            match=message,
    ):
        ModelLoader(
            storage=storage,
            backend=backend,
        ).load(
            framework="sklearn",
            **references,
        )

    storage.load_by_key.assert_not_called()
    backend.load.assert_not_called()
