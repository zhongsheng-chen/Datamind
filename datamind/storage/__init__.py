# datamind/storage/__init__.py

"""
存储模块

提供统一的文件存储接口，支持本地文件系统存储
"""

from datamind.storage.base import StorageBackend, StorageResult, FileInfo, QuotaInfo, ProgressCallback
from datamind.storage.local_storage import LocalStorage
from datamind.storage.models.model_storage import ModelStorage
from datamind.storage.models.version_manager import VersionManager

__all__ = [
    'StorageBackend',
    'StorageResult',
    'FileInfo',
    'QuotaInfo',
    'ProgressCallback',
    'LocalStorage',
    'ModelStorage',
    'VersionManager',
]