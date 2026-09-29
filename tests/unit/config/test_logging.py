"""日志配置测试.

验证日志默认值、环境变量读取、静默模式、参数校验和配置不可变行为。

核心功能：
  - test_logging_config_defaults:
    验证日志配置默认值
  - test_logging_config_ignores_external_sources:
    验证隔离配置不读取环境变量和 .env 文件
  - test_logging_config_reads_environment_variables:
    验证从环境变量读取并转换日志配置
  - test_logging_config_allows_silent_mode:
    验证允许同时关闭控制台和文件输出
  - test_logging_config_accepts_valid_values:
    验证接受有效的自定义日志配置
  - test_logging_config_rejects_invalid_values:
    验证拒绝无效日志配置参数
  - test_logging_config_accepts_valid_sample_rate:
    验证接受有效采样率边界
  - test_logging_config_ignores_extra_fields:
    验证忽略未声明的额外配置字段
  - test_logging_config_is_frozen:
    验证日志配置创建后不可修改
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

from datamind.config.logging import LoggingConfig
from datamind.constants import (
    LogFormat,
    LogLevel,
    MB,
    RotationType,
    RotationWhen,
)


class IsolatedLoggingConfig(LoggingConfig):
    """仅使用初始化参数和字段默认值的日志配置."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """禁用环境变量、.env 和密钥文件配置源."""
        _ = (
            cls,
            settings_cls,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

        return (init_settings,)


@pytest.fixture(autouse=True)
def clear_logging_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """清除日志配置相关环境变量."""
    for key in tuple(os.environ):
        if key.startswith("DATAMIND_LOG_"):
            monkeypatch.delenv(
                key,
                raising=False,
            )


def create_config(
        **overrides: Any,
) -> LoggingConfig:
    """创建隔离外部配置源的日志配置."""
    return IsolatedLoggingConfig(**overrides)


def test_logging_config_defaults() -> None:
    """测试日志配置默认值."""
    config = create_config()

    assert config.level == LogLevel.INFO
    assert config.format == LogFormat.JSON
    assert config.encoding == "utf-8"
    assert config.dir == Path("logs")
    assert config.filename == "datamind.log"
    assert config.date_format is None
    assert config.timezone == "Asia/Shanghai"
    assert config.rotation == RotationType.TIME
    assert config.rotation_when == RotationWhen.MIDNIGHT
    assert config.rotation_interval == 1
    assert config.max_bytes == 100 * MB
    assert config.backup_count == 30
    assert config.retention_days == 90
    assert config.enable_console is True
    assert config.console_level == LogLevel.WARNING
    assert config.enable_file is True
    assert config.enable_async is False
    assert config.sample_rate == 1.0
    assert config.mask_sensitive is True
    assert config.mask_char == "*"
    assert config.unmasked_prefix == 2
    assert config.unmasked_suffix == 2


def test_logging_config_ignores_external_sources(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试隔离配置不读取环境变量和 .env 文件."""
    monkeypatch.setenv(
        "DATAMIND_LOG_FORMAT",
        "text",
    )
    monkeypatch.setenv(
        "DATAMIND_LOG_LEVEL",
        "DEBUG",
    )

    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            "DATAMIND_LOG_FORMAT=text\n"
            "DATAMIND_LOG_LEVEL=DEBUG\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    config = create_config()

    assert config.format == LogFormat.JSON
    assert config.level == LogLevel.INFO


def test_logging_config_reads_environment_variables(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试从环境变量读取并转换日志配置."""
    monkeypatch.chdir(tmp_path)

    environment = {
        "DATAMIND_LOG_LEVEL": "DEBUG",
        "DATAMIND_LOG_FORMAT": "text",
        "DATAMIND_LOG_ENCODING": "gb18030",
        "DATAMIND_LOG_DIR": "runtime/logs",
        "DATAMIND_LOG_FILENAME": "service.log",
        "DATAMIND_LOG_DATE_FORMAT": "%Y-%m-%d %H:%M:%S",
        "DATAMIND_LOG_TIMEZONE": "UTC",
        "DATAMIND_LOG_ROTATION": "size",
        "DATAMIND_LOG_ROTATION_WHEN": "H",
        "DATAMIND_LOG_ROTATION_INTERVAL": "2",
        "DATAMIND_LOG_MAX_BYTES": str(10 * MB),
        "DATAMIND_LOG_BACKUP_COUNT": "10",
        "DATAMIND_LOG_RETENTION_DAYS": "30",
        "DATAMIND_LOG_ENABLE_CONSOLE": "false",
        "DATAMIND_LOG_CONSOLE_LEVEL": "ERROR",
        "DATAMIND_LOG_ENABLE_FILE": "false",
        "DATAMIND_LOG_ENABLE_ASYNC": "true",
        "DATAMIND_LOG_SAMPLE_RATE": "0.5",
        "DATAMIND_LOG_MASK_SENSITIVE": "false",
        "DATAMIND_LOG_MASK_CHAR": "#",
        "DATAMIND_LOG_UNMASKED_PREFIX": "1",
        "DATAMIND_LOG_UNMASKED_SUFFIX": "3",
    }

    for key, value in environment.items():
        monkeypatch.setenv(
            key,
            value,
        )

    config = LoggingConfig()

    assert config.level == LogLevel.DEBUG
    assert config.format == LogFormat.TEXT
    assert config.encoding == "gb18030"
    assert config.dir == Path("runtime/logs")
    assert config.filename == "service.log"
    assert config.date_format == "%Y-%m-%d %H:%M:%S"
    assert config.timezone == "UTC"
    assert config.rotation == RotationType.SIZE
    assert config.rotation_when == RotationWhen.HOUR
    assert config.rotation_interval == 2
    assert config.max_bytes == 10 * MB
    assert config.backup_count == 10
    assert config.retention_days == 30
    assert config.enable_console is False
    assert config.console_level == LogLevel.ERROR
    assert config.enable_file is False
    assert config.enable_async is True
    assert config.sample_rate == 0.5
    assert config.mask_sensitive is False
    assert config.mask_char == "#"
    assert config.unmasked_prefix == 1
    assert config.unmasked_suffix == 3


def test_logging_config_allows_silent_mode() -> None:
    """测试允许同时关闭控制台和文件输出."""
    config = create_config(
        enable_console=False,
        console_level=LogLevel.ERROR,
        enable_file=False,
    )

    assert config.enable_console is False
    assert config.console_level == LogLevel.ERROR
    assert config.enable_file is False


def test_logging_config_accepts_valid_values() -> None:
    """测试接受有效的自定义日志配置."""
    config = create_config(
        level=LogLevel.DEBUG,
        format=LogFormat.TEXT,
        encoding="gb18030",
        dir=Path("runtime/logs"),
        filename="service.log",
        date_format="%Y-%m-%d %H:%M:%S",
        timezone="UTC",
        rotation=RotationType.SIZE,
        rotation_when=RotationWhen.HOUR,
        rotation_interval=2,
        max_bytes=10 * MB,
        backup_count=10,
        retention_days=30,
        enable_console=False,
        enable_file=False,
        enable_async=True,
        sample_rate=0.5,
        mask_sensitive=False,
        mask_char="#",
        unmasked_prefix=1,
        unmasked_suffix=3,
    )

    assert config.level == LogLevel.DEBUG
    assert config.format == LogFormat.TEXT
    assert config.encoding == "gb18030"
    assert config.dir == Path("runtime/logs")
    assert config.filename == "service.log"
    assert config.date_format == "%Y-%m-%d %H:%M:%S"
    assert config.timezone == "UTC"
    assert config.rotation == RotationType.SIZE
    assert config.rotation_when == RotationWhen.HOUR
    assert config.rotation_interval == 2
    assert config.max_bytes == 10 * MB
    assert config.backup_count == 10
    assert config.retention_days == 30
    assert config.enable_console is False
    assert config.enable_file is False
    assert config.enable_async is True
    assert config.sample_rate == 0.5
    assert config.mask_sensitive is False
    assert config.mask_char == "#"
    assert config.unmasked_prefix == 1
    assert config.unmasked_suffix == 3


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "error_message",
    ),
    [
        (
            "encoding",
            "",
            "encoding 不能为空",
        ),
        (
            "encoding",
            "invalid-codec",
            "encoding 不是有效的字符编码",
        ),
        (
            "filename",
            " ",
            "filename 不能为空",
        ),
        (
            "date_format",
            " ",
            "date_format 不能是空字符串",
        ),
        (
            "timezone",
            "",
            "timezone 不能为空",
        ),
        (
            "timezone",
            "Invalid/Timezone",
            "timezone 不是有效的 IANA 时区",
        ),
        (
            "rotation_interval",
            0,
            "rotation_interval 必须大于 0",
        ),
        (
            "max_bytes",
            0,
            "max_bytes 必须大于 0",
        ),
        (
            "backup_count",
            0,
            "backup_count 必须大于 0",
        ),
        (
            "retention_days",
            0,
            "retention_days 必须大于 0",
        ),
        (
            "sample_rate",
            0,
            "sample_rate 必须大于 0",
        ),
        (
            "sample_rate",
            1.1,
            "sample_rate 必须大于 0",
        ),
        (
            "mask_char",
            "",
            "mask_char 不能为空",
        ),
        (
            "mask_char",
            "**",
            "mask_char 只能包含一个字符",
        ),
        (
            "unmasked_prefix",
            -1,
            "unmasked_prefix 必须大于等于 0",
        ),
        (
            "unmasked_suffix",
            -1,
            "unmasked_suffix 必须大于等于 0",
        ),
    ],
)
def test_logging_config_rejects_invalid_values(
        field: str,
        value: object,
        error_message: str,
) -> None:
    """测试拒绝无效日志配置参数."""
    with pytest.raises(
            ValidationError,
            match=error_message,
    ):
        create_config(
            **{
                field: value,
            }
        )


@pytest.mark.parametrize(
    "sample_rate",
    [
        0.01,
        0.5,
        1.0,
    ],
)
def test_logging_config_accepts_valid_sample_rate(
        sample_rate: float,
) -> None:
    """测试接受有效采样率边界."""
    config = create_config(sample_rate=sample_rate)

    assert config.sample_rate == sample_rate


def test_logging_config_ignores_extra_fields() -> None:
    """测试忽略未声明的额外配置字段."""
    config = create_config(
        unknown_option="ignored",
    )

    assert not hasattr(config, "unknown_option")


def test_logging_config_is_frozen() -> None:
    """测试日志配置创建后不可修改."""
    config = create_config()

    with pytest.raises(ValidationError):
        setattr(config, "level", LogLevel.DEBUG)
