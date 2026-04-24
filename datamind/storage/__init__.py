# datamind/storage/__init__.py

"""存储模块

提供统一的存储抽象层，支持本地文件系统和MinIO对象存储。

核心功能：
  - get_storage: 获取全局存储实例（单例）
  - Storage: 存储门面类，对外提供统一API

使用示例：
  from datamind.storage import get_storage

  storage = get_storage()

  # 保存模型
  storage.save("model_001", "scorecard.pkl", data)

  # 加载模型
  data = storage.load("model_001", "scorecard.pkl")

  # 列出模型文件
  files = storage.list("model_001")

架构层次：
  Storage (API门面)
     ↓
  StorageAdmin (唯一业务入口，model_id级别)
     ↓
  StorageKeyStrategy (唯一key规则来源)
     ↓
  BaseStorageBackend (IO抽象层，只认key)
     ↓
  LocalBackend / MinIOBackend (IO实现层)

核心原则：
  - StorageKeyStrategy 是唯一 key 规则来源
  - StorageAdmin 是唯一业务入口（model_id）
  - Backend 永远只认 key，不理解业务

实际存储路径：
  - 本地：{base_dir}/models/{model_id}/{version}/{filename}
  - MinIO：{bucket}/{base_prefix}/models/{model_id}/{version}/{filename}
"""

from functools import lru_cache

from datamind.config.settings import get_settings
from datamind.storage.admin import StorageAdmin


class Storage:
    """存储门面类

    对外提供统一的存储API，内部委托给 StorageAdmin。
    """

    def __init__(self, storage_admin: StorageAdmin):
        """初始化存储实例

        参数：
            storage_admin: 存储管理API实例
        """
        self._admin = storage_admin

    def save(self, model_id: str, version: str, filename: str, data: bytes) -> str:
        """保存模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名
            data: 文件二进制数据

        返回：
            存储 key
        """
        return self._admin.save(model_id, version, filename, data)

    def load(self, model_id: str, version: str, filename: str) -> bytes:
        """加载模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            文件二进制数据
        """
        return self._admin.load(model_id, version, filename)

    def delete(self, model_id: str, version: str, filename: str) -> bool:
        """删除模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            删除成功返回 True
        """
        return self._admin.delete(model_id, version, filename)

    def exists(self, model_id: str, version: str, filename: str) -> bool:
        """检查模型文件是否存在

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            存在返回 True，否则返回 False
        """
        return self._admin.exists(model_id, version, filename)

    def list(self, model_id: str) -> list[str]:
        """列出模型的所有文件

        参数：
            model_id: 模型ID

        返回：
            文件名列表
        """
        return self._admin.list(model_id)


@lru_cache
def get_storage() -> Storage:
    """获取全局存储实例（单例）

    返回：
        全局唯一的 Storage 实例
    """
    settings = get_settings()
    return Storage(StorageAdmin(settings.storage))