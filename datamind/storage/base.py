# datamind/storage/base.py
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, List, Dict, Any
import hashlib

from datamind.core import debug_print


class StorageBackend(ABC):
    """存储后端基类"""

    def __init__(self, bucket_name: str = None, base_path: str = ""):
        self.bucket_name = bucket_name
        self.base_path = base_path.rstrip('/')
        debug_print("StorageBackend", f"初始化存储后端: {self.__class__.__name__}")

    @abstractmethod
    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        保存文件

        Args:
            path: 文件路径
            content: 文件内容
            metadata: 元数据

        Returns:
            {
                'path': 完整路径,
                'size': 文件大小,
                'hash': 文件哈希,
                'version': 版本ID,
                'metadata': 元数据
            }
        """
        pass

    @abstractmethod
    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """
        加载文件

        Args:
            path: 文件路径
            version: 版本ID

        Returns:
            文件内容
        """
        pass

    @abstractmethod
    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """
        删除文件

        Args:
            path: 文件路径
            version: 版本ID
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        列出文件

        Args:
            prefix: 路径前缀

        Returns:
            文件列表
        """
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        pass

    @abstractmethod
    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """复制文件"""
        pass

    @abstractmethod
    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """移动文件"""
        pass

    @abstractmethod
    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """
        获取签名URL

        Args:
            path: 文件路径
            expires_in: 过期时间（秒）

        Returns:
            签名URL
        """
        pass

    def _get_full_path(self, path: str) -> str:
        """获取完整路径"""
        if self.base_path:
            return f"{self.base_path}/{path.lstrip('/')}"
        return path

    def _calculate_hash(self, content: BinaryIO) -> str:
        """计算文件哈希"""
        sha256 = hashlib.sha256()
        position = content.tell()
        content.seek(0)

        while chunk := content.read(8192):
            sha256.update(chunk)

        content.seek(position)
        return sha256.hexdigest()