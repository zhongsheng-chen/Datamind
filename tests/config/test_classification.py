# tests/config/test_classification.py

"""分类模型配置测试

验证默认阈值、自定义阈值、环境变量读取、类型转换、
边界值、额外字段处理和配置不可变行为。

核心功能：
  - test_classification_config_defaults:
    验证分类阈值默认值
  - test_classification_config_accepts_valid_threshold:
    验证接受有效的分类阈值
  - test_classification_config_converts_numeric_strings:
    验证将数字字符串转换为浮点阈值
  - test_classification_config_reads_environment_variable:
    验证从环境变量读取分类阈值
  - test_initial_value_overrides_environment_variable:
    验证初始化参数优先于环境变量
  - test_classification_config_rejects_out_of_range_threshold:
    验证拒绝范围外和非有限阈值
  - test_classification_config_rejects_invalid_threshold_type:
    验证拒绝无法转换为浮点数的阈值
  - test_classification_config_ignores_extra_fields:
    验证忽略未声明的额外配置字段
  - test_classification_config_is_frozen:
    验证分类模型配置创建后不可修改
  - test_classification_config_model_settings:
    验证分类模型配置元数据
"""

import os
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from datamind.config.classification import ClassificationConfig


class IsolatedClassificationConfig(ClassificationConfig):
    """仅使用初始化参数和字段默认值的测试分类配置"""

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源"""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        return (init_settings,)


@pytest.fixture(autouse=True)
def isolate_classification_config(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离分类模型配置的环境变量和 .env 文件"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_CLASSIFICATION_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def create_config(
        **overrides: Any,
) -> ClassificationConfig:
    """创建隔离外部配置源的分类模型配置"""
    return IsolatedClassificationConfig(**overrides)


def test_classification_config_defaults() -> None:
    """测试分类阈值默认值"""
    config = create_config()

    assert config.threshold == 0.5


@pytest.mark.parametrize(
    "threshold",
    [
        0.0,
        0.25,
        0.5,
        0.75,
        1.0,
    ],
)
def test_classification_config_accepts_valid_threshold(
        threshold: float,
) -> None:
    """测试接受有效的分类阈值"""
    config = create_config(threshold=threshold)

    assert config.threshold == threshold


@pytest.mark.parametrize(
    (
        "value",
        "expected",
    ),
    [
        (
            "0",
            0.0,
        ),
        (
            "0.35",
            0.35,
        ),
        (
            "1",
            1.0,
        ),
    ],
)
def test_classification_config_converts_numeric_strings(
        value: str,
        expected: float,
) -> None:
    """测试将数字字符串转换为浮点阈值"""
    config = create_config(threshold=value)

    assert config.threshold == expected


def test_classification_config_reads_environment_variable(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取分类阈值"""
    monkeypatch.setenv(
        "DATAMIND_CLASSIFICATION_THRESHOLD",
        "0.65",
    )

    config = ClassificationConfig()

    assert config.threshold == 0.65


def test_initial_value_overrides_environment_variable(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化参数优先于环境变量"""
    monkeypatch.setenv(
        "DATAMIND_CLASSIFICATION_THRESHOLD",
        "0.65",
    )

    config = create_config(threshold=0.8)

    assert config.threshold == 0.8


@pytest.mark.parametrize(
    "threshold",
    [
        -0.01,
        1.01,
        float("-inf"),
        float("inf"),
        float("nan"),
    ],
)
def test_classification_config_rejects_out_of_range_threshold(
        threshold: float,
) -> None:
    """测试拒绝超出范围或非有限的分类阈值"""
    with pytest.raises(
            ValidationError,
            match="threshold 必须在 0 到 1 之间",
    ):
        create_config(threshold=threshold)


@pytest.mark.parametrize(
    "threshold",
    [
        "",
        "invalid",
        None,
    ],
)
def test_classification_config_rejects_invalid_threshold_type(
        threshold: object,
) -> None:
    """测试拒绝无法转换为浮点数的分类阈值"""
    with pytest.raises(ValidationError):
        create_config(threshold=threshold)


def test_classification_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段"""
    config = create_config(
        unknown_option="ignored",
    )

    assert not hasattr(config, "unknown_option")


def test_classification_config_is_frozen() -> None:
    """测试分类模型配置创建后不可修改"""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "threshold", 0.7)


def test_classification_config_model_settings() -> None:
    """测试分类模型配置元数据"""
    model_config = ClassificationConfig.model_config

    assert model_config.get("env_prefix") == "DATAMIND_CLASSIFICATION_"
    assert model_config.get("env_file") == ".env"
    assert model_config.get("extra") == "ignore"
    assert model_config.get("frozen") is True
