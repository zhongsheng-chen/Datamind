# tests/logging/test_retention.py

"""日志保留管理测试

验证过期日志清理和后台保留线程的启停行为。

核心功能：
  - test_cleanup_logs_deletes_expired_files:
    验证删除超过保留天数的日志文件
  - test_cleanup_logs_ignores_missing_directory:
    验证日志目录不存在时直接返回
  - test_cleanup_logs_ignores_non_positive_retention_days:
    验证保留天数小于等于零时不清理日志
  - test_cleanup_logs_skips_matching_directories:
    验证跳过名称匹配但类型为目录的路径
  - test_start_retention_worker_avoids_duplicate_threads:
    验证重复启动时不会创建多个保留线程
  - test_stop_retention_worker_stops_thread:
    验证停止已启动的日志保留线程
  - test_stop_retention_worker_without_start:
    验证未启动线程时停止操作可重复执行
"""

import os
from datetime import (
    datetime,
    timedelta,
)
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from datamind.config.logging import LoggingConfig
from datamind.logging import retention


def test_cleanup_logs_deletes_expired_files(
        tmp_path: Path,
) -> None:
    """测试删除超过保留天数的日志文件"""
    old_log = tmp_path / "datamind.log.1"
    current_log = tmp_path / "datamind.log"
    ignored_file = tmp_path / "notes.txt"

    old_log.write_text(
        "old",
        encoding="utf-8",
    )
    current_log.write_text(
        "current",
        encoding="utf-8",
    )
    ignored_file.write_text(
        "keep",
        encoding="utf-8",
    )

    now = datetime.now(
        ZoneInfo("Asia/Shanghai")
    )
    old_timestamp = (
        now
        - timedelta(days=10)
    ).timestamp()

    os.utime(
        old_log,
        (
            old_timestamp,
            old_timestamp,
        ),
    )

    retention.cleanup_logs(
        tmp_path,
        retention_days=7,
        timezone="Asia/Shanghai",
    )

    assert not old_log.exists()
    assert current_log.exists()
    assert ignored_file.exists()


def test_cleanup_logs_ignores_missing_directory(
        tmp_path: Path,
) -> None:
    """测试日志目录不存在时直接返回"""
    missing_dir = tmp_path / "missing"

    retention.cleanup_logs(
        missing_dir,
        retention_days=7,
        timezone="Asia/Shanghai",
    )

    assert not missing_dir.exists()


@pytest.mark.parametrize(
    "retention_days",
    [
        0,
        -1,
    ],
)
def test_cleanup_logs_ignores_non_positive_retention_days(
        tmp_path: Path,
        retention_days: int,
) -> None:
    """测试保留天数小于等于零时不清理日志"""
    log_file = tmp_path / "datamind.log.1"
    log_file.write_text(
        "keep",
        encoding="utf-8",
    )

    retention.cleanup_logs(
        tmp_path,
        retention_days=retention_days,
        timezone="Asia/Shanghai",
    )

    assert log_file.exists()


def test_cleanup_logs_skips_matching_directories(
        tmp_path: Path,
) -> None:
    """测试跳过名称匹配但类型为目录的路径"""
    log_directory = tmp_path / "archive.log.1"
    log_directory.mkdir()

    retention.cleanup_logs(
        tmp_path,
        retention_days=1,
        timezone="Asia/Shanghai",
    )

    assert log_directory.is_dir()


def test_start_retention_worker_avoids_duplicate_threads(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试重复启动时不会创建多个保留线程"""
    monkeypatch.setitem(
        vars(retention),
        "_CHECK_INTERVAL_SECONDS",
        0.01,
    )

    config = LoggingConfig.model_construct(
        dir=tmp_path,
        retention_days=7,
        timezone="Asia/Shanghai",
    )

    retention.start_retention_worker(config)
    first_thread = retention._RETENTION_THREAD

    retention.start_retention_worker(config)
    second_thread = retention._RETENTION_THREAD

    try:
        assert first_thread is not None
        assert first_thread.is_alive()
        assert second_thread is first_thread

    finally:
        retention.stop_retention_worker()


def test_stop_retention_worker_stops_thread(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试停止日志保留线程"""
    monkeypatch.setitem(
        vars(retention),
        "_CHECK_INTERVAL_SECONDS",
        0.01,
    )

    config = LoggingConfig.model_construct(
        dir=tmp_path,
        retention_days=7,
        timezone="Asia/Shanghai",
    )

    retention.start_retention_worker(config)
    thread = retention._RETENTION_THREAD

    assert thread is not None
    assert thread.is_alive()

    retention.stop_retention_worker()

    assert retention._RETENTION_THREAD is None
    assert not thread.is_alive()


def test_stop_retention_worker_without_start() -> None:
    """测试未启动线程时停止操作可重复执行"""
    retention.stop_retention_worker()
    retention.stop_retention_worker()

    assert retention._RETENTION_THREAD is None
