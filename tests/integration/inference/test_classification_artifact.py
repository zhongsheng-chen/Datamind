"""分类模型制品推理集成测试

验证多种真实分类模型经过原生序列化、持久化和重新加载后，
仍可通过框架适配器与统一推理接口产生一致的类别和概率结果。

核心功能：
  - test_classification_artifact_preserves_predictions:
    验证分类模型的制品加载与推理链路
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

from datamind.constants import (
    DataType,
    SUPPORTED_MODEL_TYPES_BY_FRAMEWORK,
)
from datamind.core.inference import Inference
from datamind.core.inference.adapters.factory import ModelAdapterFactory
from datamind.models.artifact import ModelArtifactLoader
from datamind.storage.local import LocalStorageBackend


pytestmark = pytest.mark.integration

FEATURE_NAMES = ["income", "debt_ratio"]
DATA_TYPES = {
    "income": DataType.NUMERIC,
    "debt_ratio": DataType.NUMERIC,
}
TRAINING_FEATURES = np.asarray(
    [
        [-2.0, -1.0],
        [-1.5, -0.8],
        [-1.0, -0.5],
        [-0.5, -0.2],
        [0.1, 0.2],
        [0.4, 0.5],
        [0.7, 0.9],
        [1.0, 1.1],
        [1.3, 1.5],
        [1.6, 1.8],
        [2.0, 2.2],
        [2.4, 2.6],
    ],
    dtype=float,
)
TRAINING_LABELS = np.asarray(
    [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
    dtype=int,
)
PREDICTION_FEATURES = np.asarray([[0.75, 1.25]], dtype=float)
PREDICTION_RECORD = {
    "income": 0.75,
    "debt_ratio": 1.25,
}


def supported_classification_models() -> list[tuple[str, str]]:
    """返回测试覆盖的框架与模型类型组合"""
    return [
        (framework, model_type)
        for framework, model_types in SUPPORTED_MODEL_TYPES_BY_FRAMEWORK.items()
        for model_type in sorted(model_types)
    ]


def fit_model(
    framework: str,
    model_type: str,
) -> Any:
    """按框架和模型类型训练确定性的真实二分类模型"""
    if framework == "sklearn":
        estimators = {
            "logistic_regression": LogisticRegression(random_state=0),
            "decision_tree": DecisionTreeClassifier(
                max_depth=3,
                random_state=0,
            ),
            "random_forest": RandomForestClassifier(
                n_estimators=12,
                max_depth=3,
                random_state=0,
            ),
        }
        model = estimators[model_type]

    elif framework == "xgboost":
        from xgboost import XGBClassifier

        model = XGBClassifier(
            n_estimators=12,
            max_depth=2,
            learning_rate=0.2,
            random_state=0,
            n_jobs=1,
        )

    elif framework == "lightgbm":
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(
            n_estimators=12,
            max_depth=3,
            learning_rate=0.2,
            random_state=0,
            n_jobs=1,
            verbosity=-1,
        )

    elif framework == "catboost":
        from catboost import CatBoostClassifier

        model = CatBoostClassifier(
            iterations=12,
            depth=3,
            learning_rate=0.2,
            random_seed=0,
            verbose=False,
            allow_writing_files=False,
        )

    else:
        raise AssertionError(f"缺少框架测试模型: {framework}")

    return model.fit(
        TRAINING_FEATURES,
        TRAINING_LABELS,
    )


def serialize_model(
    framework: str,
    model: Any,
    tmp_path: Path,
) -> bytes:
    """使用生产加载器对应的原生格式序列化模型"""
    if framework == "sklearn":
        buffer = BytesIO()
        joblib.dump(model, buffer)
        return buffer.getvalue()

    if framework == "xgboost":
        return bytes(model.get_booster().save_raw(raw_format="ubj"))

    if framework == "lightgbm":
        return model.booster_.model_to_string().encode("utf-8")

    if framework == "catboost":
        model_path = tmp_path / "model.cbm"
        model.save_model(model_path, format="cbm")
        return model_path.read_bytes()

    raise AssertionError(f"缺少框架序列化器: {framework}")


def restored_predictions(
    framework: str,
    model: Any,
) -> tuple[int, float]:
    """统一读取重载模型的预测类别与正类概率"""
    if framework == "xgboost":
        from xgboost import DMatrix

        probability = float(model.predict(DMatrix(PREDICTION_FEATURES))[0])

    elif framework == "lightgbm":
        probability = float(model.predict(PREDICTION_FEATURES)[0])

    elif framework == "catboost":
        probabilities = model.predict(
            PREDICTION_FEATURES,
            prediction_type="Probability",
        )
        classes = model.predict(
            PREDICTION_FEATURES,
            prediction_type="Class",
        )
        return int(classes[0]), float(probabilities[0, 1])

    else:
        probability = float(model.predict_proba(PREDICTION_FEATURES)[0, 1])
        predicted_class = int(model.predict(PREDICTION_FEATURES)[0])
        return predicted_class, probability

    return int(probability > 0.5), probability


@pytest.mark.parametrize(
    ("framework", "model_type"),
    supported_classification_models(),
)
def test_classification_artifact_preserves_predictions(
    tmp_path: Path,
    framework: str,
    model_type: str,
) -> None:
    """测试受支持分类模型持久化前后的类别和概率结果一致"""
    model = fit_model(framework, model_type)
    expected_class = int(model.predict(PREDICTION_FEATURES)[0])
    expected_probability = float(
        model.predict_proba(PREDICTION_FEATURES)[0, 1]
    )

    storage = LocalStorageBackend(tmp_path / "artifacts")
    model_key = f"models/{framework}/{model_type}/model.bin"
    storage.put_object(
        model_key,
        serialize_model(framework, model, tmp_path),
    )

    restored = ModelArtifactLoader.load(
        framework=framework,
        data=storage.get_object(model_key),
    )
    restored_class, restored_probability = restored_predictions(
        framework,
        restored,
    )

    adapter = ModelAdapterFactory.create(
        model=restored,
        feature_names=FEATURE_NAMES,
        data_types=DATA_TYPES,
    )
    inference = Inference(
        model=restored,
        feature_names=FEATURE_NAMES,
        data_types=DATA_TYPES,
    )

    assert restored_class == expected_class
    assert restored_probability == pytest.approx(expected_probability)
    assert adapter.predict(PREDICTION_RECORD) == pytest.approx(
        expected_probability
    )
    assert inference.predict(PREDICTION_RECORD) == pytest.approx(
        expected_probability
    )
