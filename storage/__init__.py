# datamind/storage/__init__.py
"""
存储模块

提供统一的文件存储接口，支持本地文件系统、S3、MinIO等
"""

from storage.base import StorageBackend
from storage.local_storage import LocalStorage
from storage.s3_storage import S3Storage
from storage.minio_storage import MinIOStorage
from storage.models.model_storage import ModelStorage

__all__ = [
    'StorageBackend',
    'LocalStorage',
    'S3Storage',
    'MinIOStorage',
    'ModelStorage',
]