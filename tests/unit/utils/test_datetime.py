"""日期时间工具测试.

验证时区读取、日期时间解析、UTC 与本地时间转换和格式化行为。

核心功能：
  - test_get_timezone_defaults_to_utc:
    验证未配置 TZ 时默认使用 UTC
  - test_get_timezone_reads_environment_variable:
    验证从 TZ 环境变量读取时区名称
  - test_get_timezone_rejects_invalid_timezone:
    验证非法时区名称抛出异常
  - test_parse_datetime_returns_none_for_none:
    验证 None 解析后返回 None
  - test_parse_datetime_returns_utc_datetime:
    验证解析不同时间表示并统一转换为 UTC
  - test_parse_datetime_rejects_invalid_value:
    验证非法日期时间字符串抛出异常
  - test_to_utc_returns_none_for_none:
    验证 None 转换为 UTC 时返回 None
  - test_to_utc_treats_naive_datetime_as_utc:
    验证无时区时间按 UTC 处理
  - test_to_utc_converts_aware_datetime:
    验证带时区时间转换为 UTC
  - test_to_local_returns_none_for_none:
    验证 None 转换为本地时间时返回 None
  - test_to_local_treats_naive_datetime_as_utc:
    验证无时区时间按 UTC 转换为本地时间
  - test_to_local_converts_aware_datetime:
    验证带时区时间转换为本地时间
  - test_format_datetime_returns_placeholder_for_none:
    验证 None 格式化后返回占位符
  - test_format_datetime_uses_local_timezone:
    验证使用本地时区和默认格式输出
  - test_format_datetime_supports_custom_format:
    验证支持自定义日期时间格式
  - test_format_datetime_supports_explicit_timezone:
    验证支持显式指定应用时区
  - test_format_iso_utc_returns_none_for_none:
    验证 None 格式化为 ISO 8601 UTC 时返回 None
  - test_format_iso_utc_converts_timezone_and_truncates_microseconds:
    验证转换为 UTC 并截断到毫秒精度
  - test_format_iso_utc_includes_zero_milliseconds:
    验证无微秒时仍输出三位毫秒
  - test_format_iso_utc_treats_naive_datetime_as_utc:
    验证无时区时间按 UTC 格式化
  - test_iso_format_and_parse_support_round_trip:
    验证 ISO 8601 UTC 格式化结果可以重新解析
  - test_parse_datetime_uses_explicit_timezone_for_naive_value:
    测试无时区输入按显式指定的本地时区解析
  - test_parse_datetime_preserves_input_timezone_offset:
    测试输入时区优先于无时区输入的默认时区
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

import pytest

import datamind.utils.datetime as datetime_utils


def test_get_timezone_defaults_to_utc(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未配置 TZ 时默认使用 UTC."""
    monkeypatch.delenv(
        "TZ",
        raising=False,
    )

    result = datetime_utils.get_timezone()

    assert result.key == "UTC"


def test_get_timezone_reads_environment_variable(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试从 TZ 环境变量读取时区名称."""
    requested_names: list[str] = []

    def create_zone_info(
            name: str,
    ) -> ZoneInfo:
        requested_names.append(
            name
        )

        return ZoneInfo(
            "UTC"
        )

    monkeypatch.setenv(
        "TZ",
        "Asia/Shanghai",
    )
    monkeypatch.setitem(
        vars(datetime_utils),
        "ZoneInfo",
        create_zone_info,
    )

    result = datetime_utils.get_timezone()

    assert result.key == "UTC"
    assert requested_names == [
        "Asia/Shanghai",
    ]


def test_get_timezone_rejects_invalid_timezone(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非法时区名称抛出异常."""
    monkeypatch.setenv(
        "TZ",
        "Invalid/Timezone",
    )

    with pytest.raises(
            ZoneInfoNotFoundError
    ):
        datetime_utils.get_timezone()


def test_parse_datetime_returns_none_for_none() -> None:
    """测试 None 解析后返回 None."""
    assert (
        datetime_utils.parse_datetime(
            None
        )
        is None
    )


@pytest.mark.parametrize(
    (
        "raw",
        "expected",
    ),
    [
        (
            "2026-07-23T16:30:15+08:00",
            datetime(
                2026,
                7,
                23,
                8,
                30,
                15,
                tzinfo=timezone.utc,
            ),
        ),
        (
            "2026-07-23T08:30:15Z",
            datetime(
                2026,
                7,
                23,
                8,
                30,
                15,
                tzinfo=timezone.utc,
            ),
        ),
        (
            "2026-07-23T08:30:15.123Z",
            datetime(
                2026,
                7,
                23,
                8,
                30,
                15,
                123000,
                tzinfo=timezone.utc,
            ),
        ),
        (
            "2026-07-23T08:30:15",
            datetime(
                2026,
                7,
                23,
                8,
                30,
                15,
                tzinfo=timezone.utc,
            ),
        ),
    ],
)
def test_parse_datetime_returns_utc_datetime(
        raw: str,
        expected: datetime,
) -> None:
    """测试解析不同时间表示并统一转换为 UTC."""
    assert (
        datetime_utils.parse_datetime(
            raw
        )
        == expected
    )


def test_parse_datetime_uses_explicit_timezone_for_naive_value() -> None:
    """测试无时区输入按显式指定的本地时区解析."""
    result = datetime_utils.parse_datetime(
        "2026-07-23 16:30:15",
        timezone_name="Asia/Shanghai",
    )

    assert result == datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )


def test_parse_datetime_preserves_input_timezone_offset() -> None:
    """测试输入时区优先于无时区输入的默认时区."""
    result = datetime_utils.parse_datetime(
        "2026-07-23T16:30:15+02:00",
        timezone_name="Asia/Shanghai",
    )

    assert result == datetime(
        2026,
        7,
        23,
        14,
        30,
        15,
        tzinfo=timezone.utc,
    )


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "invalid",
        "2026-13-23T08:30:15",
        "2026-07-23T25:30:15",
    ],
)
def test_parse_datetime_rejects_invalid_value(
        raw: str,
) -> None:
    """测试非法日期时间字符串抛出 ValueError."""
    with pytest.raises(
            ValueError
    ):
        datetime_utils.parse_datetime(
            raw
        )


def test_to_utc_returns_none_for_none() -> None:
    """测试 None 转换为 UTC 时返回 None."""
    assert datetime_utils.to_utc(
        None
    ) is None


def test_to_utc_treats_naive_datetime_as_utc() -> None:
    """测试无时区时间按 UTC 处理."""
    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
    )

    result = datetime_utils.to_utc(
        dt
    )

    assert result == datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )
    assert result is not dt


def test_to_utc_converts_aware_datetime() -> None:
    """测试带时区时间正确转换为 UTC."""
    dt = datetime(
        2026,
        7,
        23,
        16,
        30,
        15,
        tzinfo=timezone(
            timedelta(
                hours=8
            )
        ),
    )

    result = datetime_utils.to_utc(
        dt
    )

    assert result == datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )
    assert result is not None
    assert result.tzinfo is timezone.utc


def test_to_local_returns_none_for_none() -> None:
    """测试 None 转换为本地时间时返回 None."""
    assert datetime_utils.to_local(
        None
    ) is None


def test_to_local_treats_naive_datetime_as_utc(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试无时区时间按 UTC 转换为本地时间."""
    local_timezone = timezone(
        timedelta(
            hours=8
        )
    )
    monkeypatch.setitem(
        vars(datetime_utils),
        "get_timezone",
        lambda: local_timezone,
    )

    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
    )

    result = datetime_utils.to_local(
        dt
    )

    assert result == datetime(
        2026,
        7,
        23,
        16,
        30,
        15,
        tzinfo=local_timezone,
    )


def test_to_local_converts_aware_datetime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试带时区时间正确转换为本地时间."""
    local_timezone = timezone(
        timedelta(
            hours=8
        )
    )
    monkeypatch.setitem(
        vars(datetime_utils),
        "get_timezone",
        lambda: local_timezone,
    )

    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )

    result = datetime_utils.to_local(
        dt
    )

    assert result == datetime(
        2026,
        7,
        23,
        16,
        30,
        15,
        tzinfo=local_timezone,
    )


def test_format_datetime_returns_placeholder_for_none() -> None:
    """测试 None 格式化后返回占位符."""
    assert (
        datetime_utils.format_datetime(
            None
        )
        == "-"
    )


def test_format_datetime_uses_local_timezone(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按本地时区使用默认格式输出."""
    monkeypatch.setitem(
        vars(datetime_utils),
        "get_timezone",
        lambda: timezone(
            timedelta(
                hours=8
            )
        ),
    )

    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )

    result = datetime_utils.format_datetime(
        dt
    )

    assert result == "2026-07-23 16:30:15"


def test_format_datetime_supports_custom_format(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试支持自定义日期时间格式."""
    monkeypatch.setitem(
        vars(datetime_utils),
        "get_timezone",
        lambda: timezone.utc,
    )

    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )

    result = datetime_utils.format_datetime(
        dt,
        fmt="%Y/%m/%d %H:%M",
    )

    assert result == "2026/07/23 08:30"


def test_format_datetime_supports_explicit_timezone() -> None:
    """测试支持显式指定应用时区."""
    dt = datetime(
        2026,
        8,
        3,
        0,
        46,
        39,
        tzinfo=timezone.utc,
    )

    result = datetime_utils.format_datetime(
        dt,
        timezone_name="Asia/Shanghai",
    )

    assert result == "2026-08-03 08:46:39"


def test_format_iso_utc_returns_none_for_none() -> None:
    """测试 None 格式化为 ISO 8601 UTC 时返回 None."""
    assert (
        datetime_utils.format_iso_utc(
            None
        )
        is None
    )


def test_format_iso_utc_converts_timezone_and_truncates_microseconds() -> None:
    """测试转换为 UTC 并截断到毫秒精度."""
    dt = datetime(
        2026,
        7,
        23,
        16,
        30,
        15,
        123999,
        tzinfo=timezone(
            timedelta(
                hours=8
            )
        ),
    )

    result = datetime_utils.format_iso_utc(
        dt
    )

    assert result == "2026-07-23T08:30:15.123Z"


def test_format_iso_utc_includes_zero_milliseconds() -> None:
    """测试无微秒时仍输出三位毫秒."""
    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        tzinfo=timezone.utc,
    )

    result = datetime_utils.format_iso_utc(
        dt
    )

    assert result == "2026-07-23T08:30:15.000Z"


def test_format_iso_utc_treats_naive_datetime_as_utc() -> None:
    """测试无时区时间按 UTC 格式化."""
    dt = datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        456789,
    )

    result = datetime_utils.format_iso_utc(
        dt
    )

    assert result == "2026-07-23T08:30:15.456Z"


def test_iso_format_and_parse_support_round_trip() -> None:
    """测试 ISO 8601 UTC 格式化结果可以重新解析."""
    dt = datetime(
        2026,
        7,
        23,
        16,
        30,
        15,
        987654,
        tzinfo=timezone(
            timedelta(
                hours=8
            )
        ),
    )

    raw = datetime_utils.format_iso_utc(
        dt
    )
    result = datetime_utils.parse_datetime(
        raw
    )

    assert result == datetime(
        2026,
        7,
        23,
        8,
        30,
        15,
        987000,
        tzinfo=timezone.utc,
    )
