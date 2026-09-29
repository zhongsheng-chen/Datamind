"""Datamind 模型框架集成验证脚本.

验证各可选模型框架与 Datamind 的集成能否完成模型训练、制品加载和推理。

运行方式：
  python -m scripts.verify_framework sklearn
"""

from __future__ import annotations

import argparse
import importlib
from io import BytesIO
from pathlib import Path
import tempfile

import numpy as np

from datamind.core.inference.adapters.factory import ModelAdapterFactory
from datamind.models.artifact import ModelArtifactLoader


FEATURES = np.array([
    [0.0, 0.0],
    [0.0, 1.0],
    [1.0, 0.0],
    [1.0, 1.0],
    [0.2, 0.8],
    [0.8, 0.2],
])
TARGET = np.array([0, 0, 1, 1, 0, 1])


def verify_prediction(model: object) -> None:
    """验证制品加载、适配器选择与概率预测.

    参数：
        model: 已加载的模型对象
    """
    adapter = ModelAdapterFactory.create(
        model=model,
        feature_names=["feature_a", "feature_b"],
    )
    prediction = adapter.predict(np.array([0.25, 0.75]))
    assert isinstance(prediction, float)
    assert 0.0 <= prediction <= 1.0


def verify_sklearn() -> None:
    """验证 Sklearn 模型制品."""
    import joblib
    import optbinning
    from sklearn.linear_model import LogisticRegression

    assert optbinning is not None
    model = LogisticRegression(random_state=0).fit(FEATURES, TARGET)
    artifact = BytesIO()
    joblib.dump(model, artifact)
    loaded = ModelArtifactLoader.load("sklearn", artifact.getvalue())
    verify_prediction(loaded)


def verify_xgboost() -> None:
    """验证 XGBoost 模型制品."""
    import xgboost as xgb

    dataset = xgb.DMatrix(FEATURES, label=TARGET)
    model = xgb.train(
        {"objective": "binary:logistic", "max_depth": 1},
        dataset,
        num_boost_round=2,
    )
    artifact = bytes(model.save_raw(raw_format="json"))
    loaded = ModelArtifactLoader.load("xgboost", artifact)
    verify_prediction(loaded)


def verify_lightgbm() -> None:
    """验证 LightGBM 模型制品."""
    import lightgbm as lgb

    dataset = lgb.Dataset(FEATURES, label=TARGET)
    model = lgb.train(
        {"objective": "binary", "verbosity": -1},
        dataset,
        num_boost_round=2,
    )
    artifact = model.model_to_string().encode("utf-8")
    loaded = ModelArtifactLoader.load("lightgbm", artifact)
    verify_prediction(loaded)


def verify_catboost() -> None:
    """验证 CatBoost 模型制品."""
    from catboost import CatBoostClassifier

    model = CatBoostClassifier(
        iterations=2,
        depth=1,
        verbose=False,
        allow_writing_files=False,
    )
    model.fit(FEATURES, TARGET)

    with tempfile.TemporaryDirectory() as temporary_directory:
        artifact_path = Path(temporary_directory) / "model.cbm"
        model.save_model(str(artifact_path))
        artifact = artifact_path.read_bytes()

    loaded = ModelArtifactLoader.load("catboost", artifact)
    verify_prediction(loaded)


VERIFY = {
    "sklearn": verify_sklearn,
    "xgboost": verify_xgboost,
    "lightgbm": verify_lightgbm,
    "catboost": verify_catboost,
}


def verify_imports(framework: str) -> None:
    """验证框架及其 Datamind 集成模块可以独立导入.

    参数：
        framework: 模型框架名称
    """
    importlib.import_module(framework)
    importlib.import_module(
        f"datamind.core.inference.adapters.{framework}"
    )
    importlib.import_module(
        f"datamind.models.artifact.handlers.{framework}"
    )
    importlib.import_module("datamind.runtime")


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(
        description="验证模型框架与 Datamind 的集成",
    )
    parser.add_argument(
        "framework",
        choices=[*VERIFY, "full"],
        help="需要验证的模型框架",
    )
    return parser.parse_args(arguments)


def main() -> None:
    """执行验证流程."""
    framework = parse_arguments().framework
    frameworks = (
        VERIFY
        if framework == "full"
        else {framework: VERIFY[framework]}
    )

    for framework_name, verify in frameworks.items():
        verify_imports(framework_name)
        verify()


if __name__ == "__main__":
    main()
