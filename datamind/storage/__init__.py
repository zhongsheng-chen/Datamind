# datamind/storage/__init__.py

"""
存储模块

提供统一的文件存储接口，支持本地文件系统、S3、MinIO等
"""

from datamind.storage.base import StorageBackend, StorageResult, FileInfo, QuotaInfo, ProgressCallback
from datamind.storage.local_storage import LocalStorage
from datamind.storage.s3_storage import S3Storage
from datamind.storage.minio_storage import MinIOStorage
from datamind.storage.models.model_storage import ModelStorage
from datamind.storage.models.version_manager import VersionManager

__all__ = [
    'StorageBackend',
    'StorageResult',
    'FileInfo',
    'QuotaInfo',
    'ProgressCallback',
    'LocalStorage',
    'S3Storage',
    'MinIOStorage',
    'ModelStorage',
    'VersionManager',
]