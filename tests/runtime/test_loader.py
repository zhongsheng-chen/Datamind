# tests/runtime/test_loader.py

"""模型加载器测试

验证对象存储制品优先加载和 BentoML 本地回退能力。

核心功能：
  - test_load_prefers_storage_artifact:
    验证优先从对象存储加载模型制品
  - test_load_falls_back_to_bento_store:
    验证没有存储键时使用 BentoML Store
  - test_load_rejects_missing_artifact_reference:
    验证缺少对象键和 BentoML 标签时拒绝加载
"""

from unittest.mock import MagicMock

import pytest

import datamind.runtime.loader as loader_module
from datamind.models.artifact import ModelArtifactLoader
from datamind.runtime.loader import ModelLoader


def test_load_prefers_storage_artifact(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试优先从对象存储加载模型制品"""
    storage = MagicMock()
    storage.load_by_key.return_value = b"model-data"
    backend = MagicMock()
    expected = object()
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(loader_module),
        "BentoBackend",
        lambda: backend,
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        lambda **_kwargs: expected,
    )

    result = ModelLoader().load(
        framework="sklearn",
        tag="scorecard:test",
        model_key="models/mdl/ver/art/model.pkl",
    )

    assert result is expected
    storage.load_by_key.assert_called_once_with(
        "models/mdl/ver/art/model.pkl"
    )
    backend.load.assert_not_called()


def test_load_falls_back_to_bento_store(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试没有存储键时使用 BentoML Store"""
    storage = MagicMock()
    backend = MagicMock()
    expected = object()
    backend.load.return_value = expected
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(loader_module),
        "BentoBackend",
        lambda: backend,
    )

    result = ModelLoader().load(
        framework="sklearn",
        tag="scorecard:test",
    )

    assert result is expected
    backend.load.assert_called_once_with(
        framework="sklearn",
        tag="scorecard:test",
    )
    storage.load_by_key.assert_not_called()


@pytest.mark.parametrize(
    "tag",
    [
        None,
        "",
        "   ",
    ],
)
def test_load_rejects_missing_artifact_reference(
        monkeypatch: pytest.MonkeyPatch,
        tag: str | None,
) -> None:
    """测试缺少对象键和 BentoML 标签时拒绝加载"""
    monkeypatch.setitem(
        vars(loader_module),
        "get_storage",
        MagicMock,
    )
    monkeypatch.setitem(
        vars(loader_module),
        "BentoBackend",
        MagicMock,
    )

    with pytest.raises(
            ValueError,
            match="tag 和 model_key 至少需要提供一个",
    ):
        ModelLoader().load(
            framework="sklearn",
            tag=tag,
        )
