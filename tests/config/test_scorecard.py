# tests/config/test_scorecard.py

"""评分卡配置测试

验证默认参数、自定义参数、环境变量读取、类型转换、
评分范围、PDO 边界、额外字段处理和配置不可变行为。

核心功能：
  - test_scorecard_config_defaults:
    验证评分卡配置默认值
  - test_scorecard_config_accepts_custom_values:
    验证接受有效的自定义评分卡参数
  - test_scorecard_config_converts_numeric_strings:
    验证将数字字符串转换为浮点参数
  - test_scorecard_config_reads_environment_variables:
    验证从环境变量读取评分卡参数
  - test_initial_values_override_environment_variables:
    验证初始化参数优先于环境变量
  - test_scorecard_config_rejects_non_positive_base_odds:
    验证基准好坏比必须大于零
  - test_scorecard_config_rejects_negative_min_score:
    验证评分下限不能为负数
  - test_scorecard_config_requires_min_less_than_max:
    验证评分下限必须小于评分上限
  - test_scorecard_config_requires_minimum_score_range:
    验证评分范围至少为 100
  - test_scorecard_config_accepts_pdo_boundaries:
    验证接受 PDO 合法边界值
  - test_scorecard_config_rejects_out_of_range_pdo:
    验证拒绝范围外的 PDO
  - test_scorecard_config_accepts_base_score_boundaries:
    验证基准分可以等于评分上下限
  - test_scorecard_config_rejects_base_score_outside_range:
    验证基准分必须位于评分范围内
  - test_scorecard_config_rejects_invalid_numeric_values:
    验证拒绝无法转换为浮点数的配置值
  - test_scorecard_config_ignores_extra_fields:
    验证忽略未声明的额外配置字段
  - test_scorecard_config_is_frozen:
    验证评分卡配置创建后不可修改
  - test_scorecard_config_model_settings:
    验证评分卡配置元数据
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

from datamind.config.scorecard import ScorecardConfig


class IsolatedScorecardConfig(ScorecardConfig):
    """仅使用初始化参数和字段默认值的测试评分卡配置"""

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
def isolate_scorecard_config(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离评分卡配置的环境变量和 .env 文件"""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_SCORECARD_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )

    monkeypatch.chdir(tmp_path)


def create_config(
        **overrides: Any,
) -> ScorecardConfig:
    """创建隔离外部配置源的评分卡配置"""
    return IsolatedScorecardConfig(**overrides)


def test_scorecard_config_defaults() -> None:
    """测试评分卡配置默认值"""
    config = create_config()

    assert config.base_score == 600.0
    assert config.base_odds == 50.0
    assert config.pdo == 20.0
    assert config.min_score == 0.0
    assert config.max_score == 1000.0


def test_scorecard_config_accepts_custom_values() -> None:
    """测试接受有效的自定义评分卡参数"""
    config = create_config(
        base_score=650.0,
        base_odds=30.0,
        pdo=40.0,
        min_score=300.0,
        max_score=900.0,
    )

    assert config.base_score == 650.0
    assert config.base_odds == 30.0
    assert config.pdo == 40.0
    assert config.min_score == 300.0
    assert config.max_score == 900.0


def test_scorecard_config_converts_numeric_strings() -> None:
    """测试将数字字符串转换为浮点参数"""
    config = create_config(
        base_score="650",
        base_odds="30",
        pdo="40",
        min_score="300",
        max_score="900",
    )

    assert config.base_score == 650.0
    assert config.base_odds == 30.0
    assert config.pdo == 40.0
    assert config.min_score == 300.0
    assert config.max_score == 900.0


def test_scorecard_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从环境变量读取评分卡参数"""
    environment = {
        "DATAMIND_SCORECARD_BASE_SCORE": "650",
        "DATAMIND_SCORECARD_BASE_ODDS": "30",
        "DATAMIND_SCORECARD_PDO": "40",
        "DATAMIND_SCORECARD_MIN_SCORE": "300",
        "DATAMIND_SCORECARD_MAX_SCORE": "900",
    }

    for key, value in environment.items():
        monkeypatch.setenv(
            key,
            value,
        )

    config = ScorecardConfig()

    assert config.base_score == 650.0
    assert config.base_odds == 30.0
    assert config.pdo == 40.0
    assert config.min_score == 300.0
    assert config.max_score == 900.0


def test_initial_values_override_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化参数优先于环境变量"""
    monkeypatch.setenv(
        "DATAMIND_SCORECARD_BASE_SCORE",
        "650",
    )
    monkeypatch.setenv(
        "DATAMIND_SCORECARD_PDO",
        "40",
    )

    config = create_config(
        base_score=700.0,
        pdo=60.0,
    )

    assert config.base_score == 700.0
    assert config.pdo == 60.0


@pytest.mark.parametrize(
    "base_odds",
    [
        0.0,
        -1.0,
    ],
)
def test_scorecard_config_rejects_non_positive_base_odds(
        base_odds: float,
) -> None:
    """测试基准好坏比必须大于零"""
    with pytest.raises(
            ValidationError,
            match="base_odds 必须大于 0",
    ):
        create_config(base_odds=base_odds)


@pytest.mark.parametrize(
    "min_score",
    [
        -0.01,
        -100.0,
    ],
)
def test_scorecard_config_rejects_negative_min_score(
        min_score: float,
) -> None:
    """测试评分下限不能为负数"""
    with pytest.raises(
            ValidationError,
            match="min_score 必须大于等于 0",
    ):
        create_config(min_score=min_score)


@pytest.mark.parametrize(
    (
        "min_score",
        "max_score",
    ),
    [
        (
            500.0,
            500.0,
        ),
        (
            600.0,
            500.0,
        ),
    ],
)
def test_scorecard_config_requires_min_less_than_max(
        min_score: float,
        max_score: float,
) -> None:
    """测试评分下限必须小于评分上限"""
    with pytest.raises(
            ValidationError,
            match="必须小于 max_score",
    ):
        create_config(
            min_score=min_score,
            max_score=max_score,
        )


@pytest.mark.parametrize(
    (
        "min_score",
        "max_score",
    ),
    [
        (
            0.0,
            99.99,
        ),
        (
            500.0,
            599.0,
        ),
    ],
)
def test_scorecard_config_requires_minimum_score_range(
        min_score: float,
        max_score: float,
) -> None:
    """测试评分范围至少为 100"""
    with pytest.raises(
            ValidationError,
            match="至少需要 100",
    ):
        create_config(
            base_score=min_score,
            min_score=min_score,
            max_score=max_score,
        )


@pytest.mark.parametrize(
    "pdo",
    [
        20.0,
        50.0,
        100.0,
    ],
)
def test_scorecard_config_accepts_pdo_boundaries(
        pdo: float,
) -> None:
    """测试接受 PDO 合法边界值"""
    config = create_config(pdo=pdo)

    assert config.pdo == pdo


@pytest.mark.parametrize(
    "pdo",
    [
        19.99,
        100.01,
    ],
)
def test_scorecard_config_rejects_out_of_range_pdo(
        pdo: float,
) -> None:
    """测试 PDO 必须在 20 到 100 之间"""
    with pytest.raises(
            ValidationError,
            match="必须在 20 到 100 之间",
    ):
        create_config(pdo=pdo)


@pytest.mark.parametrize(
    (
        "base_score",
        "min_score",
        "max_score",
    ),
    [
        (
            300.0,
            300.0,
            900.0,
        ),
        (
            900.0,
            300.0,
            900.0,
        ),
    ],
)
def test_scorecard_config_accepts_base_score_boundaries(
        base_score: float,
        min_score: float,
        max_score: float,
) -> None:
    """测试基准分可以等于评分上下限"""
    config = create_config(
        base_score=base_score,
        min_score=min_score,
        max_score=max_score,
    )

    assert config.base_score == base_score


@pytest.mark.parametrize(
    (
        "base_score",
        "min_score",
        "max_score",
    ),
    [
        (
            299.99,
            300.0,
            900.0,
        ),
        (
            900.01,
            300.0,
            900.0,
        ),
    ],
)
def test_scorecard_config_rejects_base_score_outside_range(
        base_score: float,
        min_score: float,
        max_score: float,
) -> None:
    """测试基准分必须位于评分范围内"""
    with pytest.raises(
            ValidationError,
            match="必须在 min_score",
    ):
        create_config(
            base_score=base_score,
            min_score=min_score,
            max_score=max_score,
        )


@pytest.mark.parametrize(
    (
        "field",
        "value",
    ),
    [
        (
            "base_score",
            "invalid",
        ),
        (
            "base_odds",
            None,
        ),
        (
            "pdo",
            "",
        ),
        (
            "min_score",
            object(),
        ),
        (
            "max_score",
            [],
        ),
    ],
)
def test_scorecard_config_rejects_invalid_numeric_values(
        field: str,
        value: object,
) -> None:
    """测试拒绝无法转换为浮点数的配置值"""
    with pytest.raises(ValidationError):
        create_config(
            **{
                field: value,
            }
        )


def test_scorecard_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段"""
    config = create_config(
        unknown_option="ignored",
    )

    assert not hasattr(config, "unknown_option")


def test_scorecard_config_is_frozen() -> None:
    """测试评分卡配置创建后不可修改"""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "base_score", 700.0)


def test_scorecard_config_model_settings() -> None:
    """测试评分卡配置元数据"""
    model_config = ScorecardConfig.model_config

    assert model_config.get("env_prefix") == "DATAMIND_SCORECARD_"
    assert model_config.get("env_file") == ".env"
    assert model_config.get("extra") == "ignore"
    assert model_config.get("frozen") is True
