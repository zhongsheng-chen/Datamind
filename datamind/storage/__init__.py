# datamind/storage/__init__.py

"""存储模块

提供统一的存储抽象层，支持本地文件系统和 MinIO 对象存储。

核心功能：
  - get_storage: 获取全局存储实例（单例）
  - Storage: 存储门面类，对外提供统一 API

实际存储路径：
  - 本地：{base_dir}/models/{model_id}/{version}/{filename}
  - MinIO：{bucket}/{base_prefix}/models/{model_id}/{version}/{filename}

使用示例：
  from datamind.storage import get_storage

  storage = get_storage()

  # 保存模型文件
  storage.save("mdl_a1b2c3d4", "1.0.0", "scorecard.pkl", data)

  # 加载模型文件
  data = storage.load("mdl_a1b2c3d4", "1.0.0", "scorecard.pkl")

  # 检查模型文件是否存在
  exists = storage.exists("mdl_a1b2c3d4", "1.0.0", "scorecard.pkl")

  # 列出模型的所有文件
  files = storage.list("mdl_a1b2c3d4")

  # 删除模型文件
  storage.delete("mdl_a1b2c3d4", "1.0.0", "scorecard.pkl")
"""

from functools import lru_cache

from datamind.config.settings import get_settings
from datamind.storage.admin import StorageAdmin


class Storage:
    """存储门面类

    对外提供统一的存储 API，内部委托给 StorageAdmin。
    """

    def __init__(self, storage_admin: StorageAdmin):
        """初始化存储实例

        参数：
            storage_admin: 存储管理 API 实例
        """
        self._admin = storage_admin

    def _kwargs(
        self,
        model_id: str,
        version: str | None = None,
        filename: str | None = None,
    ) -> dict:
        """构造模型参数

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            参数字典
        """
        return {
            "model_id": model_id,
            "version": version,
            "filename": filename,
        }

    def save(self, model_id: str, version: str, filename: str, data: bytes) -> str:
        """保存模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名
            data: 二进制数据

        返回：
            存储 key
        """
        return self._admin.save(
            **self._kwargs(model_id, version, filename),
            data=data,
        )

    def load(self, model_id: str, version: str, filename: str) -> bytes:
        """加载模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            二进制数据
        """
        return self._admin.load(
            **self._kwargs(model_id, version, filename),
        )

    def delete(self, model_id: str, version: str, filename: str) -> bool:
        """删除模型文件

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            删除成功返回 True
        """
        return self._admin.delete(
            **self._kwargs(model_id, version, filename),
        )

    def exists(self, model_id: str, version: str, filename: str) -> bool:
        """检查模型文件是否存在

        参数：
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            存在返回 True，否则返回 False
        """
        return self._admin.exists(
            **self._kwargs(model_id, version, filename),
        )

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