"""应用通用配置测试.

验证运行环境必填、时区默认值、配置源优先级、参数校验，
以及时间解析、显示和导出对通用配置的使用。

核心功能：
  - test_default_timezone:
    验证默认时区为 Asia/Shanghai
  - test_timezone_source_precedence:
    验证环境变量和 .env 文件的读取优先级
  - test_explicit_timezone_overrides_sources:
    验证初始化参数优先于环境变量
  - test_invalid_timezone_rejected:
    验证拒绝空字符串和无效时区名称
  - test_shared_timezone_for_input_and_display:
    验证时间输入解析和显示共用默认时区
  - test_routing_service_uses_application_timezone:
    验证路由生效时间使用默认时区解析
  - test_export_filename_uses_application_timezone:
    验证控制台导出文件名使用默认时区
  - test_application_environment_required:
    验证运行环境必须显式配置
  - test_application_environment_values:
    验证运行环境的枚举转换
  - test_application_environment_from_dotenv:
    验证从 .env 文件读取运行环境
  - test_unknown_environment_rejected:
    验证拒绝未知运行环境
"""

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

import pytest
from pydantic import ValidationError

from datamind.config import get_common_config
from datamind.config.common import CommonConfig
from datamind.constants import Environment
from datamind.utils.datetime import (
    format_datetime,
    parse_datetime,
)


@pytest.fixture(autouse=True)
def isolate_timezone(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """隔离通用配置环境变量和 .env 文件."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATAMIND_ENVIRONMENT", "testing")
    monkeypatch.delenv("DATAMIND_TIMEZONE", raising=False)


def test_default_timezone() -> None:
    """测试默认时区为 Asia/Shanghai."""
    assert get_common_config().timezone == "Asia/Shanghai"


@pytest.mark.parametrize(
    "environment,dotenv,expected",
    [
        ({"DATAMIND_TIMEZONE": "UTC"}, "", "UTC"),
        ({}, "DATAMIND_TIMEZONE=Europe/London", "Europe/London"),
        ({"DATAMIND_TIMEZONE": "Europe/London"}, "DATAMIND_TIMEZONE=UTC", "Europe/London"),
    ],
)
def test_timezone_source_precedence(
        monkeypatch: pytest.MonkeyPatch,
        environment: dict[str, str],
        dotenv: str,
        expected: str,
) -> None:
    """测试环境变量优先于 .env 文件中的时区配置."""
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    Path(".env").write_text(dotenv, encoding="utf-8")
    assert get_common_config().timezone == expected


def test_explicit_timezone_overrides_sources(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化参数优先于环境变量."""
    monkeypatch.setenv("DATAMIND_TIMEZONE", "UTC")
    config = CommonConfig(environment=Environment.TESTING, timezone="Europe/London")
    assert config.timezone == "Europe/London"


@pytest.mark.parametrize("value", ["", " ", "Invalid/Timezone"])
def test_invalid_timezone_rejected(
        monkeypatch: pytest.MonkeyPatch,
        value: str,
) -> None:
    """测试拒绝空字符串和无效时区名称."""
    monkeypatch.setenv("DATAMIND_TIMEZONE", value)
    with pytest.raises(ValidationError):
        get_common_config()


def test_shared_timezone_for_input_and_display(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试默认时区用于解析和显示，显式偏移优先于默认时区."""
    monkeypatch.setenv("DATAMIND_TIMEZONE", "Asia/Tokyo")
    parsed = parse_datetime("2026-10-01T00:00:00", timezone_name=get_common_config().timezone)
    assert parsed == datetime(2026, 9, 30, 15, tzinfo=timezone.utc)
    assert format_datetime(parsed) == "2026-10-01 00:00:00"
    explicit = parse_datetime("2026-10-01T00:00:00+08:00", timezone_name=get_common_config().timezone)
    assert explicit == datetime(2026, 9, 30, 16, tzinfo=timezone.utc)


def test_routing_service_uses_application_timezone(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由生效时间按默认时区解析."""
    from datamind.services.routing import _parse_effective_window

    monkeypatch.setenv("DATAMIND_TIMEZONE", "Asia/Tokyo")
    start, end = _parse_effective_window(
        effective_from="2026-10-01T00:00:00",
        effective_to="2026-10-02T00:00:00",
    )
    assert start == datetime(2026, 9, 30, 15, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 1, 15, tzinfo=timezone.utc)


def test_export_filename_uses_application_timezone(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台导出文件名使用默认时区."""
    from datamind.console.exports import export_filename

    monkeypatch.setenv("DATAMIND_TIMEZONE", "Asia/Tokyo")
    name = export_filename(
        "deployments", now=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )
    assert name == "deployments_20261001_090000.csv"


def test_application_environment_required(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行环境必须显式配置."""
    monkeypatch.delenv("DATAMIND_ENVIRONMENT")
    with pytest.raises(ValidationError) as error:
        get_common_config()
    assert error.value.errors()[0]["loc"] == ("environment",)
    assert error.value.errors()[0]["type"] == "missing"


@pytest.mark.parametrize("environment", ["development", "testing", "staging", "production"])
def test_application_environment_values(
        monkeypatch: pytest.MonkeyPatch,
        environment: str,
) -> None:
    """测试将四种运行环境解析为对应枚举."""
    monkeypatch.setenv("DATAMIND_ENVIRONMENT", environment)
    assert get_common_config().environment == Environment(environment)


def test_application_environment_from_dotenv(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从 .env 文件读取运行环境."""
    monkeypatch.delenv("DATAMIND_ENVIRONMENT")
    Path(".env").write_text("DATAMIND_ENVIRONMENT=production", encoding="utf-8")
    assert get_common_config().environment.value == "production"


def test_unknown_environment_rejected(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝未知运行环境."""
    monkeypatch.setenv("DATAMIND_ENVIRONMENT", "unknown")
    with pytest.raises(ValidationError):
        get_common_config()
