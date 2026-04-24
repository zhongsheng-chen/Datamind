# datamind/storage/local.py

"""本地文件系统存储后端

将数据存储在本地文件系统中，使用文件路径作为key。

核心功能：
  - put_object: 写入文件，自动创建父目录
  - get_object: 读取文件内容
  - delete_object: 删除文件
  - object_exists: 检查文件是否存在
  - list_objects: 递归列出目录下所有文件

特性：
  - 自动创建目录：写入时自动创建不存在的父目录
  - 路径安全：防止路径遍历攻击
  - 跨平台兼容：Windows/Linux/macOS 路径自动转换
"""

from pathlib import Path

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import StorageKeyError, StorageNotFoundError


class LocalStorageBackend(BaseStorageBackend):
    """本地文件系统存储后端"""

    def __init__(self, base_dir: Path):
        """初始化本地存储后端

        参数：
            base_dir: 基础目录，所有文件存储在此目录下
        """
        self.base_dir = Path(base_dir).expanduser().resolve()

    def _safe_path(self, key: str) -> Path:
        """构造完整文件路径，并防止路径遍历攻击

        参数：
            key: 存储键

        返回：
            完整文件路径

        异常：
            StorageKeyError: 检测到路径遍历攻击
        """
        full_path = (self.base_dir / key).resolve()

        if not str(full_path).startswith(str(self.base_dir)):
            raise StorageKeyError(f"非法的存储键，检测到路径遍历: {key}")

        return full_path

    def put_object(self, key: str, data: bytes) -> None:
        """存储数据到文件

        参数：
            key: 存储键
            data: 二进制数据
        """
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_object(self, key: str) -> bytes:
        """读取文件内容

        参数：
            key: 存储键

        返回：
            文件二进制内容

        异常：
            StorageNotFoundError: 文件不存在
        """
        path = self._safe_path(key)
        if not path.exists():
            raise StorageNotFoundError(f"文件不存在: {key}")
        return path.read_bytes()

    def delete_object(self, key: str) -> None:
        """删除文件

        参数：
            key: 存储键
        """
        path = self._safe_path(key)
        if path.exists():
            path.unlink()

    def object_exists(self, key: str) -> bool:
        """检查文件是否存在

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False
        """
        try:
            return self._safe_path(key).exists()
        except StorageKeyError:
            return False

    def list_objects(self, prefix: str) -> list[str]:
        """列出目录下所有文件

        参数：
            prefix: 目录前缀

        返回：
            完整key列表（相对于 base_dir）
        """
        root = self.base_dir / prefix
        if not root.exists():
            return []
        return [
            str(p.relative_to(self.base_dir))
            for p in root.rglob("*")
            if p.is_file()
        ]