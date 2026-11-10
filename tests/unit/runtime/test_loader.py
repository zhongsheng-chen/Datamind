"""模型加载器测试.

验证模型缓存复用、制品同步、依赖恢复及加载阶段耗时记录。

核心功能：
  - test_loader_uses_default_dependencies:
    验证默认使用全局存储和 BentoML 后端
  - test_loader_initializes_storage_after_bento_model_miss:
    验证 BentoML 模型缺失时才连接对象存储
  - test_loader_retries_storage_after_dependency_recovers:
    验证对象存储恢复后可以再次加载模型
  - test_load_returns_existing_bento_model:
    验证直接复用 BentoML 中已有的模型
  - test_load_materializes_missing_bento_model:
    验证从统一存储同步缺失的 BentoML 模型
  - test_load_reuses_concurrently_materialized_model:
    验证并发同步冲突后复用已有模型
  - test_load_rejects_blank_reference:
    验证拒绝空模型引用
  - test_load_logs_stage_durations:
    验证缓存命中、未命中及并发恢复的加载阶段耗时
  - test_load_logs_failed_stage_without_masking_error:
    验证加载失败仍记录耗时并保留原始异常
"""

from unittest.mock import MagicMock

import pytest
from bentoml.exceptions import (
    BentoMLException,
    NotFound,
)
from structlog.testing import capture_logs

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
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        get_storage,
    )
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
    storage.load_by_key.assert_called_once_with("models/mdl/ver/art/model.pkl")


def test_loader_retries_storage_after_dependency_recovers(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试对象存储晚于运行服务恢复后可以再次加载模型."""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    get_storage = MagicMock(
        side_effect=[
            StorageConnectionError("minio unavailable"),
            storage,
        ],
    )
    backend = MagicMock()
    loaded_model = object()
    backend.load.side_effect = [
        NotFound("model missing"),
        NotFound("model missing"),
        loaded_model,
    ]
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        get_storage,
    )
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
    storage.load_by_key.assert_called_once_with("models/mdl/ver/art/model.pkl")


def test_load_returns_existing_bento_model() -> None:
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
    load_artifact = MagicMock(return_value=artifact_model)
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
    storage.load_by_key.assert_called_once_with("models/mdl/ver/art/model.pkl")
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
        "model already exists",
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


@pytest.mark.parametrize("mode", ["cached", "missing", "concurrent"])
def test_load_logs_stage_durations(
        monkeypatch: pytest.MonkeyPatch,
        mode: str,
) -> None:
    """测试各加载路径的阶段、耗时和模型引用准确."""
    backend = MagicMock()
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    expected = object()
    if mode == "cached":
        backend.load.return_value = expected
    else:
        backend.load.side_effect = [
            NotFound("missing"),
            expected,
        ]
    if mode == "concurrent":
        backend.save.side_effect = BentoMLException("already exists")
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        MagicMock(return_value=object()),
    )
    stage_count = 1 if mode == "cached" else 5
    monkeypatch.setitem(
        vars(loader_module),
        "perf_counter",
        MagicMock(
            side_effect=[
                value / 1000
                for value in range(stage_count * 2)
            ],
        ),
    )

    with capture_logs() as logs:
        result = ModelLoader(
            storage=storage,
            backend=backend,
        ).load(
            framework="sklearn",
            bento_tag="scorecard:test",
            model_key="models/test/model.pkl",
        )

    assert result is expected
    stages = [
        entry
        for entry in logs
        if entry["event"] == "模型加载耗时"
    ]
    assert [entry["stage"] for entry in stages] == (
        ["bento_load"]
        if mode == "cached"
        else [
            "bento_load",
            "storage_load",
            "artifact_load",
            "bento_save",
            "bento_reload",
        ]
    )
    for entry in stages:
        assert "status" not in entry
        assert entry["duration_ms"] == 1.0
        assert entry["log_level"] == "debug"
        assert entry["framework"] == "sklearn"
        assert entry["bento_tag"] == "scorecard:test"
        assert entry["model_key"] == "models/test/model.pkl"


def test_load_logs_failed_stage_without_masking_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存储失败仍记录耗时，且抛出原始异常、不执行后续阶段."""
    backend = MagicMock()
    backend.load.side_effect = NotFound("missing")
    storage = MagicMock()
    error = StorageConnectionError("storage unavailable")
    storage.load_by_key.side_effect = error
    monkeypatch.setitem(
        vars(loader_module),
        "perf_counter",
        MagicMock(side_effect=[0.0, 0.01, 0.02, 0.05]),
    )

    with capture_logs() as logs, pytest.raises(StorageConnectionError) as raised:
        ModelLoader(
            storage=storage,
            backend=backend,
        ).load(
            framework="sklearn",
            bento_tag="scorecard:test",
            model_key="models/test/model.pkl",
        )

    assert raised.value is error
    stages = [
        entry
        for entry in logs
        if entry["event"] == "模型加载耗时"
    ]
    assert [
        (entry["stage"], entry["duration_ms"])
        for entry in stages
    ] == [
        ("bento_load", 10.0),
        ("storage_load", 30.0),
    ]
    backend.save.assert_not_called()
