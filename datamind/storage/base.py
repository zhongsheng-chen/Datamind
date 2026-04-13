# datamind/storage/base.py

"""存储基类

提供统一的存储抽象接口，定义所有存储后端必须实现的方法。

设计说明：
  - 所有存储后端都继承此类
  - 具体实现类负责添加审计日志和链路追踪
  - 基类只定义接口，不包含业务逻辑

存储后端实现：
  - LocalStorage: 本地文件系统存储

使用示例：
    storage = LocalStorage(root_path="/data")

    # 保存文件
    with open("file.txt", "rb") as f:
        result = await storage.save("path/to/file.txt", f)

    # 加载文件
    content = await storage.load("path/to/file.txt")

    # 获取签名URL
    url = await storage.get_signed_url("path/to/file.txt")
"""

import hashlib
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, List, Dict, Any, AsyncIterator, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from datamind.core.logging import get_logger
from datamind.core.common import StorageQuotaException

_logger = get_logger(__name__)


# ============== 结果类型 ==============

@dataclass
class StorageResult:
    """存储操作结果"""
    path: str
    size: int
    hash: str
    etag: Optional[str] = None
    version_id: Optional[str] = None
    metadata: Optional[Dict] = None
    bucket: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    size: int
    last_modified: Optional[str] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_dir: bool = False
    hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'path': self.path,
            'size': self.size,
            'last_modified': self.last_modified,
            'etag': self.etag,
            'content_type': self.content_type,
            'metadata': self.metadata,
            'is_dir': self.is_dir,
            'hash': self.hash,
        }


@dataclass
class QuotaInfo:
    """配额信息"""
    total_size: int = 0
    file_count: int = 0
    max_size: Optional[int] = None
    max_files: Optional[int] = None

    @property
    def usage_percent(self) -> Optional[float]:
        """使用率百分比"""
        if self.max_size and self.max_size > 0:
            return (self.total_size / self.max_size) * 100
        return None

    @property
    def is_quota_exceeded(self) -> bool:
        """是否超过配额"""
        if self.max_size and self.total_size > self.max_size:
            return True
        if self.max_files and self.file_count > self.max_files:
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'total_size': self.total_size,
            'total_size_mb': round(self.total_size / 1024 / 1024, 2),
            'file_count': self.file_count,
            'max_size': self.max_size,
            'max_size_mb': round(self.max_size / 1024 / 1024, 2) if self.max_size else None,
            'max_files': self.max_files,
            'usage_percent': self.usage_percent,
            'is_quota_exceeded': self.is_quota_exceeded,
        }


# ============== 进度回调 ==============

class ProgressCallback:
    """进度回调基类"""

    async def __call__(self, current: int, total: int, phase: str = "upload"):
        """
        进度回调

        参数:
            current: 当前进度（字节）
            total: 总大小（字节）
            phase: 阶段（upload/download/copy）
        """
        pass


# ============== 存储后端基类 ==============

class StorageBackend(ABC):
    """存储后端基类

    所有存储后端实现必须继承此类并实现所有抽象方法。

    属性:
        bucket_name: 存储桶名称（本地存储忽略）
        base_path: 基础路径前缀
    """

    def __init__(self, bucket_name: str = None, base_path: str = ""):
        """
        初始化存储后端

        参数:
            bucket_name: 存储桶名称（本地存储忽略）
            base_path: 基础路径前缀，所有文件路径都会添加此前缀
        """
        self.bucket_name = bucket_name
        self.base_path = base_path.rstrip('/')
        self._closed = False
        _logger.debug("初始化存储后端: %s", self.__class__.__name__)

    @abstractmethod
    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None,
                   progress_callback: Optional[ProgressCallback] = None) -> StorageResult:
        """保存文件到存储后端"""
        pass

    @abstractmethod
    async def load(self, path: str, version: Optional[str] = None,
                   progress_callback: Optional[ProgressCallback] = None) -> bytes:
        """从存储后端加载文件"""
        pass

    @abstractmethod
    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """从存储后端删除文件"""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        pass

    @abstractmethod
    async def list(self, prefix: str = "", max_keys: int = 1000) -> List[FileInfo]:
        """列出指定前缀下的所有文件"""
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> FileInfo:
        """获取文件元数据"""
        pass

    @abstractmethod
    async def copy(self, source_path: str, dest_path: str) -> StorageResult:
        """复制文件"""
        pass

    @abstractmethod
    async def move(self, source_path: str, dest_path: str) -> StorageResult:
        """移动文件"""
        pass

    @abstractmethod
    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """获取文件签名URL（用于临时访问）"""
        pass

    # ============== 批量操作 ==============

    async def batch_save(self, items: List[Tuple[str, BinaryIO, Optional[Dict]]]) -> List[StorageResult]:
        """批量保存文件"""
        results = []
        for path, content, metadata in items:
            result = await self.save(path, content, metadata)
            results.append(result)
        return results

    async def batch_delete(self, paths: List[str]) -> Dict[str, bool]:
        """批量删除文件"""
        results = {}
        for path in paths:
            results[path] = await self.delete(path)
        return results

    # ============== 配额管理 ==============

    async def get_quota(self) -> QuotaInfo:
        """获取存储配额信息"""
        files = await self.list()
        total_size = sum(f.size for f in files)
        return QuotaInfo(
            total_size=total_size,
            file_count=len(files)
        )

    async def check_quota(self, additional_size: int = 0) -> bool:
        """检查配额"""
        quota = await self.get_quota()
        if quota.is_quota_exceeded:
            raise StorageQuotaException(
                current=quota.total_size,
                limit=quota.max_size
            )
        if quota.max_size and quota.total_size + additional_size > quota.max_size:
            raise StorageQuotaException(
                current=quota.total_size + additional_size,
                limit=quota.max_size
            )
        return True

    # ============== 流式处理 ==============

    async def stream_load(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """流式加载大文件"""
        content = await self.load(path)
        for i in range(0, len(content), chunk_size):
            yield content[i:i + chunk_size]

    async def stream_save(self, path: str, chunks: AsyncIterator[bytes],
                          metadata: Optional[Dict] = None) -> StorageResult:
        """流式保存大文件"""
        all_chunks = []
        async for chunk in chunks:
            all_chunks.append(chunk)

        content = b''.join(all_chunks)

        from io import BytesIO
        return await self.save(path, BytesIO(content), metadata)

    # ============== 辅助方法 ==============

    def _get_full_path(self, path: str) -> str:
        """获取完整路径（添加 base_path 前缀）"""
        path = path.lstrip('/')
        if self.base_path:
            return f"{self.base_path}/{path}"
        return path

    @staticmethod
    def _calculate_hash(content: BinaryIO) -> str:
        """计算文件内容的 SHA256 哈希值"""
        sha256 = hashlib.sha256()
        position = content.tell()
        content.seek(0)

        while chunk := content.read(8192):
            sha256.update(chunk)

        content.seek(position)
        return sha256.hexdigest()

    async def close(self):
        """关闭存储后端连接"""
        self._closed = True
        _logger.debug("关闭存储后端: %s", self.__class__.__name__)