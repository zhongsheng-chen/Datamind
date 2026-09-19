"""运行时模型加载集成测试

验证真实模型制品从统一存储同步至隔离的 BentoML Model Store，并可在源制品删除后复用。

核心功能：
  - test_loader_materializes_and_reuses_bento_model:
    验证运行时物化并复用真实 BentoML 模型
"""

from io import BytesIO
from pathlib import Path
import uuid

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from datamind.config.storage import LocalStorageConfig, StorageConfig
from datamind.constants import StorageType
from datamind.storage import Storage
from datamind.storage.admin import StorageAdmin


pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_bento_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """提供不污染用户 BentoML 主目录的真实模型仓库"""
    home = tmp_path / "bentoml"
    monkeypatch.setenv("BENTOML_HOME", str(home))
    return home


def serialize_model(model: LogisticRegression) -> bytes:
    """将真实 sklearn 模型序列化为制品字节"""
    buffer = BytesIO()
    joblib.dump(model, buffer)
    return buffer.getvalue()


def test_loader_materializes_and_reuses_bento_model(
    tmp_path: Path,
    isolated_bento_home: Path,
) -> None:
    """测试运行时物化模型后可脱离源制品再次加载"""
    from datamind.runtime.backend import BentoBackend
    from datamind.runtime.loader import ModelLoader

    training_features = np.array(
        [
            [-2.0, -1.0],
            [-1.0, -0.5],
            [0.5, 0.8],
            [1.5, 2.0],
        ]
    )
    training_labels = np.array([0, 0, 1, 1])
    model = LogisticRegression(random_state=0).fit(
        training_features,
        training_labels,
    )
    expected = model.predict_proba([[0.75, 1.25]])

    storage = Storage(
        StorageAdmin(
            StorageConfig(
                type=StorageType.LOCAL,
                local=LocalStorageConfig(base_dir=tmp_path / "artifacts"),
            )
        )
    )
    model_key = "models/mdl_runtime/1.0.0/model.pkl"
    storage.save_by_key(model_key, serialize_model(model))
    loader = ModelLoader(
        storage=storage,
        backend=BentoBackend(),
    )
    bento_tag = f"datamind_runtime_{uuid.uuid4().hex}"

    materialized = loader.load(
        framework="sklearn",
        bento_tag=bento_tag,
        model_key=model_key,
    )
    storage.delete_by_key(model_key, strict=True)
    reused = loader.load(
        framework="sklearn",
        bento_tag=bento_tag,
        model_key=model_key,
    )

    assert (isolated_bento_home / "models").is_dir()
    assert materialized.predict_proba([[0.75, 1.25]]) == pytest.approx(expected)
    assert reused.predict_proba([[0.75, 1.25]]) == pytest.approx(expected)
