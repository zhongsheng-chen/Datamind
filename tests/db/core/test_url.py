# tests/db/core/test_url.py

"""数据库 URL 获取测试

验证 get_db_url 从全局配置中读取并原样返回
数据库连接 URL。

核心功能：
  - test_get_db_url:
    验证返回数据库配置中的 URL
  - test_get_db_url_reads_settings_each_time:
    验证每次调用都从全局配置获取当前 URL
  - test_get_db_url_does_not_modify_value:
    验证 URL 不会被裁剪或转换
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import datamind.db.core.url as url_module


DATABASE_URL = (
    "postgresql+asyncpg://"
    "datamind:password@localhost:5432/datamind"
)


def test_get_db_url(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证返回数据库配置中的 URL"""
    database_config = SimpleNamespace(
        url=DATABASE_URL
    )
    settings = SimpleNamespace(
        database=database_config
    )
    get_settings = MagicMock(
        return_value=settings
    )

    monkeypatch.setitem(
        vars(url_module),
        "get_settings",
        get_settings,
    )

    result = url_module.get_db_url()

    assert result == DATABASE_URL
    get_settings.assert_called_once_with()


def test_get_db_url_reads_settings_each_time(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证每次调用都从全局配置获取当前 URL"""
    first_url = (
        "postgresql+asyncpg://"
        "datamind:first@localhost:5432/datamind"
    )
    second_url = (
        "postgresql+asyncpg://"
        "datamind:second@localhost:5432/datamind_test"
    )
    first_settings = SimpleNamespace(
        database=SimpleNamespace(
            url=first_url
        )
    )
    second_settings = SimpleNamespace(
        database=SimpleNamespace(
            url=second_url
        )
    )
    get_settings = MagicMock(
        side_effect=[
            first_settings,
            second_settings,
        ]
    )

    monkeypatch.setitem(
        vars(url_module),
        "get_settings",
        get_settings,
    )

    first = url_module.get_db_url()
    second = url_module.get_db_url()

    assert first == first_url
    assert second == second_url
    assert get_settings.call_count == 2


def test_get_db_url_does_not_modify_value(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证 URL 不会被裁剪或转换"""
    configured_url = (
        " postgresql+asyncpg://"
        "datamind:password@localhost:5432/datamind "
    )
    settings = SimpleNamespace(
        database=SimpleNamespace(
            url=configured_url
        )
    )
    get_settings = MagicMock(
        return_value=settings
    )

    monkeypatch.setitem(
        vars(url_module),
        "get_settings",
        get_settings,
    )

    result = url_module.get_db_url()

    assert result is configured_url
    assert result == configured_url
