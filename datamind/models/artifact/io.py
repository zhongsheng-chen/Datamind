# datamind/models/artifact/io.py

"""临时文件工具

提供临时文件的创建和自动清理功能。

核心功能：
  - temp_file: 创建临时文件，退出时自动删除

使用示例：
  from datamind.models.artifact.io import temp_file

  with temp_file(data, ".onnx") as path:
      model = ort.InferenceSession(path)
"""

import os
import tempfile
import structlog
from contextlib import contextmanager
from typing import Iterator

logger = structlog.get_logger(__name__)


@contextmanager
def temp_file(data: bytes, suffix: str) -> Iterator[str]:
    """创建临时文件并写入数据，退出时自动删除

    参数：
        data: 二进制数据
        suffix: 文件后缀（如 .keras / .cbm / .onnx）

    返回：
        临时文件路径
    """
    fd, path = tempfile.mkstemp(suffix=suffix)

    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        yield path

    finally:
        try:
            os.remove(path)

        except FileNotFoundError:
            logger.debug("临时文件已不存在", path=path)

        except PermissionError as e:
            logger.warning("无法删除临时文件（权限不足或文件占用）", path=path, error=str(e))

        except Exception as e:
            logger.warning("删除临时文件失败", path=path, error=str(e))
