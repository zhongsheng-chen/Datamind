"""本地文件系统存储后端

将数据存储在本地文件系统中，使用文件路径作为 key。

核心功能：
  - put_object: 写入文件，自动创建父目录
  - get_object: 读取文件内容
  - delete_object: 删除文件
  - object_exists: 检查文件是否存在
  - list_objects: 递归列出目录下所有文件

使用示例：
  from pathlib import Path

  from datamind.storage.local import LocalStorageBackend

  storage = LocalStorageBackend(
      base_dir=Path("./data")
  )

  storage.put_object(
      key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      ),
      data=b"model data",
  )

  data = storage.get_object(
      key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      )
  )

  keys = storage.list_objects(
      prefix="models/mdl_0123456789abcdef"
  )
"""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
import time

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import StorageKeyError, StorageNotFoundError

_IS_WINDOWS = os.name == "nt"


class LocalStorageBackend(BaseStorageBackend):
    """本地文件系统存储后端"""

    _WINDOWS_REPLACE_ATTEMPTS = 5
    _WINDOWS_REPLACE_RETRY_SECONDS = 0.01

    def __init__(
            self,
            base_dir: Path,
    ) -> None:
        """初始化本地存储后端

        参数：
            base_dir: 基础目录，所有文件存储在此目录下
        """
        self.base_dir = Path(base_dir).expanduser().resolve()

    def _safe_path(
            self,
            key: str,
            *,
            allow_base_dir: bool = False,
    ) -> Path:
        """构造安全的完整文件路径

        参数：
            key: 存储键
            allow_base_dir: 是否允许 key 指向基础目录本身

        返回：
            完整文件路径

        异常：
            StorageKeyError: 存储键为空、格式非法或发生路径越界
        """
        if not isinstance(key, str):
            raise StorageKeyError(
                "存储键必须是字符串"
            )

        if "\x00" in key:
            raise StorageKeyError(
                "存储键不能包含空字符"
            )

        normalized_key = key.replace(
            "\\",
            "/",
        )

        if not normalized_key:
            if allow_base_dir:
                return self.base_dir

            raise StorageKeyError(
                "存储键不能为空"
            )

        if normalized_key.startswith("/"):
            raise StorageKeyError(
                f"存储键不能使用绝对路径: {key}"
            )

        if allow_base_dir:
            normalized_key = normalized_key.rstrip("/")

            if not normalized_key:
                return self.base_dir

        parts = normalized_key.split("/")

        if any(
                part in {"", ".", ".."}
                for part in parts
        ):
            raise StorageKeyError(
                f"非法的存储键: {key}"
            )

        full_path = (
            self.base_dir
            / Path(normalized_key)
        ).resolve()

        if not full_path.is_relative_to(self.base_dir):
            raise StorageKeyError(
                f"非法的存储键，检测到路径遍历: {key}"
            )

        if (
                not allow_base_dir
                and full_path == self.base_dir
        ):
            raise StorageKeyError(
                f"非法的存储键，不能指向基础目录: {key}"
            )

        return full_path

    def put_object(
            self,
            key: str,
            data: bytes,
    ) -> None:
        """存储数据到文件

        参数：
            key: 存储键
            data: 二进制数据
        """
        path = self._safe_path(key)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_file = NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temporary_path = Path(
            temporary_file.name
        )

        try:
            with temporary_file:
                temporary_file.write(data)
                temporary_file.flush()
                os.fsync(
                    temporary_file.fileno()
                )

            self._replace_file(
                temporary_path,
                path,
            )

        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @classmethod
    def _replace_file(
            cls,
            source: Path,
            target: Path,
    ) -> None:
        """原子替换文件，并重试 Windows 短暂占用错误"""
        for attempt in range(
                cls._WINDOWS_REPLACE_ATTEMPTS
        ):
            try:
                os.replace(
                    source,
                    target,
                )
                return

            except PermissionError:
                is_last_attempt = (
                    attempt
                    == cls._WINDOWS_REPLACE_ATTEMPTS - 1
                )

                if not _IS_WINDOWS or is_last_attempt:
                    raise

                time.sleep(
                    cls._WINDOWS_REPLACE_RETRY_SECONDS
                    * (attempt + 1)
                )

    def get_object(
            self,
            key: str,
    ) -> bytes:
        """读取文件内容

        参数：
            key: 存储键

        返回：
            二进制数据

        异常：
            StorageNotFoundError: 文件不存在
        """
        path = self._safe_path(key)

        if not path.is_file():
            raise StorageNotFoundError(
                f"文件不存在: {key}"
            )

        return path.read_bytes()

    def delete_object(
            self,
            key: str,
    ) -> None:
        """删除文件

        文件不存在时保持幂等，不抛出异常。

        参数：
            key: 存储键
        """
        path = self._safe_path(key)

        if path.is_file():
            path.unlink()

    def object_exists(
            self,
            key: str,
    ) -> bool:
        """检查文件是否存在

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False

        异常：
            StorageKeyError: 存储键为空、格式非法或发生路径越界
        """
        return self._safe_path(
            key
        ).is_file()

    def list_objects(
            self,
            prefix: str,
    ) -> list[str]:
        """列出目录下所有文件

        参数：
            prefix: 目录前缀；空字符串表示基础目录

        返回：
            相对于 base_dir 的存储键列表

        异常：
            StorageKeyError: 目录前缀格式非法或发生路径越界
        """
        root = self._safe_path(
            prefix,
            allow_base_dir=True,
        )

        if not root.is_dir():
            return []

        keys = []

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            resolved_path = path.resolve()

            if not resolved_path.is_relative_to(
                    self.base_dir
            ):
                continue

            keys.append(
                path.relative_to(
                    self.base_dir
                ).as_posix()
            )

        return sorted(keys)
