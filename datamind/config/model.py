# datamind/config/model.py

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):

    registry_dir: str = "./models"

    supported_frameworks: list[str] = [
        "sklearn",
        "xgboost",
        "lightgbm",
        "torch",
        "tensorflow",
        "onnx",
        "catboost",
    ]

    supported_types: list[str] = [
        "decision_tree",
        "random_forest",
        "xgboost",
        "lightgbm",
        "logistic_regression",
        "scorecard",
    ]

    enable_hot_reload: bool = True

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_MODEL_",
        env_file=".env",
        extra="ignore",
    )