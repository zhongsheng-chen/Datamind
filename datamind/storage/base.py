# datamind/storage/base.py

"""存储基类

提供统一的存储抽象接口，定义所有存储后端必须实现的方法。

设计说明：
  - 所有存储后端（LocalStorage、MinIOStorage、S3Storage）都继承此类
  - 具体实现类负责添加审计日志和链路追踪
  - 基类只定义接口，不包含业务逻辑

存储后端实现：
  - LocalStorage: 本地文件系统存储
  - MinIOStorage: MinIO 对象存储（兼容 S3 API）
  - S3Storage: AWS S3 对象存储

审计日志说明：
  - 审计日志在具体实现类中添加，使用 AuditAction 枚举
  - 所有存储操作都记录以下审计信息：
    - FILE_UPLOAD: 文件上传/保存
    - FILE_DOWNLOAD: 文件下载/加载
    - FILE_DELETE: 文件删除
    - FILE_COPY: 文件复制
    - FILE_MOVE: 文件移动
    - FILE_LIST: 列出文件
    - FILE_METADATA: 获取/修改文件元数据
  - 所有审计日志包含完整的链路追踪信息（trace_id, span_id, parent_span_id）

使用示例：
    # 创建存储实例
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
from typing import BinaryIO, Optional, List, Dict, Any

from datamind.core.logging import get_logger

_logger = get_logger(__name__)


class StorageBackend(ABC):
    """存储后端基类

    所有存储后端实现必须继承此类并实现所有抽象方法。

    属性:
        bucket_name: 存储桶名称（S3/MinIO使用，本地存储忽略）
        base_path: 基础路径前缀
    """

    def __init__(self, bucket_name: str = None, base_path: str = ""):
        """
        初始化存储后端

        参数:
            bucket_name: 存储桶名称（S3/MinIO使用，本地存储忽略）
            base_path: 基础路径前缀，所有文件路径都会添加此前缀
        """
        self.bucket_name = bucket_name
        self.base_path = base_path.rstrip('/')
        _logger.debug("初始化存储后端: %s", self.__class__.__name__)

    @abstractmethod
    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        保存文件到存储后端

        参数:
            path: 文件路径（相对于 base_path）
            content: 文件内容（二进制流）
            metadata: 自定义元数据

        返回:
            Dict: {
                'path': str,        # 完整存储路径
                'size': int,        # 文件大小（字节）
                'hash': str,        # 文件哈希值（SHA256）
                'etag': str,        # ETag（S3/MinIO）
                'version_id': str,  # 版本ID（如果启用版本控制）
                'metadata': dict    # 保存的元数据
            }

        审计日志:
            - 成功: FILE_UPLOAD
            - 失败: FILE_UPLOAD (包含错误信息)
        """
        pass

    @abstractmethod
    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """
        从存储后端加载文件

        参数:
            path: 文件路径（相对于 base_path）
            version: 版本ID（如果启用版本控制）

        返回:
            文件内容（字节）

        审计日志:
            - 成功: FILE_DOWNLOAD
            - 失败: FILE_DOWNLOAD (包含错误信息)
        """
        pass

    @abstractmethod
    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """
        从存储后端删除文件

        参数:
            path: 文件路径（相对于 base_path）
            version: 版本ID（如果启用版本控制）

        返回:
            True: 删除成功
            False: 文件不存在

        审计日志:
            - 成功: FILE_DELETE
            - 失败: FILE_DELETE (包含错误信息)
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        检查文件是否存在

        参数:
            path: 文件路径（相对于 base_path）

        返回:
            True: 文件存在
            False: 文件不存在
        """
        pass

    @abstractmethod
    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        列出指定前缀下的所有文件

        参数:
            prefix: 路径前缀（相对于 base_path）

        返回:
            List[Dict]: 文件信息列表，每个元素包含:
                - path: 文件路径
                - size: 文件大小
                - last_modified: 最后修改时间
                - etag: ETag
                - metadata: 元数据

        审计日志:
            - FILE_LIST (记录文件数量)
        """
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """
        获取文件元数据

        参数:
            path: 文件路径（相对于 base_path）

        返回:
            Dict: 元数据信息，包含:
                - path: 文件路径
                - size: 文件大小
                - last_modified: 最后修改时间
                - content_type: 内容类型
                - metadata: 自定义元数据

        审计日志:
            - FILE_METADATA
        """
        pass

    @abstractmethod
    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """
        复制文件

        参数:
            source_path: 源文件路径
            dest_path: 目标文件路径

        返回:
            Dict: 复制结果，包含源路径和目标路径

        审计日志:
            - 成功: FILE_COPY
            - 失败: FILE_COPY (包含错误信息)
        """
        pass

    @abstractmethod
    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """
        移动文件（复制后删除原文件）

        参数:
            source_path: 源文件路径
            dest_path: 目标文件路径

        返回:
            Dict: 移动结果，包含源路径和目标路径

        审计日志:
            - FILE_MOVE
        """
        pass

    @abstractmethod
    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """
        获取文件签名URL（用于临时访问）

        参数:
            path: 文件路径（相对于 base_path）
            expires_in: 过期时间（秒），默认3600秒（1小时）

        返回:
            签名URL字符串

        本地存储返回: file://绝对路径
        S3/MinIO返回: 预签名URL
        """
        pass

    def _get_full_path(self, path: str) -> str:
        """
        获取完整路径（添加 base_path 前缀）

        参数:
            path: 原始路径

        返回:
            添加前缀后的完整路径
        """
        if self.base_path:
            return f"{self.base_path}/{path.lstrip('/')}"
        return path

    @staticmethod
    def _calculate_hash(content: BinaryIO) -> str:
        """
        计算文件内容的 SHA256 哈希值

        参数:
            content: 文件内容（二进制流）

        返回:
            SHA256 哈希值（十六进制字符串）

        注意:
            此方法会保存文件指针位置，计算完成后恢复
        """
        sha256 = hashlib.sha256()
        position = content.tell()
        content.seek(0)

        while chunk := content.read(8192):
            sha256.update(chunk)

        content.seek(position)
        return sha256.hexdigest()