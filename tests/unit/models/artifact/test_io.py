"""模型产物临时文件测试

验证临时模型文件的写入、清理和清理异常处理。

核心功能：
  - test_temp_file_writes_and_removes_data:
    验证临时文件写入与正常清理
  - test_temp_file_handles_missing_file:
    验证容忍临时文件已被删除
  - test_temp_file_logs_cleanup_error:
    验证记录临时文件清理异常
"""

from pathlib import Path
from unittest.mock import Mock

import pytest

import datamind.models.artifact.io as io_module
from datamind.models.artifact.io import temp_file


def test_temp_file_writes_and_removes_data() -> None:
    """测试写入并自动删除临时文件"""
    data = b"model data"

    with temp_file(data, ".bin") as value:
        path = Path(value)

        assert path.suffix == ".bin"
        assert path.read_bytes() == data

    assert not path.exists()


def test_temp_file_handles_missing_file(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试容忍临时文件在退出前已被删除"""
    logger = Mock()
    monkeypatch.setitem(
        vars(io_module),
        "logger",
        logger,
    )

    with temp_file(b"model data", ".bin") as value:
        path = Path(value)
        path.unlink()

    logger.debug.assert_called_once_with(
        "临时文件已不存在",
        path=str(path),
    )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (
            PermissionError("file is busy"),
            "无法删除临时文件（权限不足或文件占用）",
        ),
        (
            OSError("filesystem error"),
            "删除临时文件失败",
        ),
    ],
)
def test_temp_file_logs_cleanup_error(
        monkeypatch: pytest.MonkeyPatch,
        error: OSError,
        message: str,
) -> None:
    """测试记录临时文件清理异常"""
    logger = Mock()

    with monkeypatch.context() as context:
        context.setitem(
            vars(io_module),
            "logger",
            logger,
        )
        context.setitem(
            vars(io_module.os),
            "remove",
            Mock(side_effect=error),
        )

        with temp_file(b"model data", ".bin") as value:
            path = Path(value)

    assert path.exists()
    path.unlink()
    logger.warning.assert_called_once_with(
        message,
        path=str(path),
        error=str(error),
    )
