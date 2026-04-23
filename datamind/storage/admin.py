# datamind/storage/admin.py

"""存储管理API

提供业务级别的存储操作接口，是唯一业务入口。

核心功能：
  - save: 保存模型文件
  - load: 加载模型文件
  - delete: 删除模型文件
  - exists: 检查模型文件是否存在
  - list: 列出模型的所有文件

特性：
  - 唯一业务入口：只处理 model_id 级别逻辑
  - 策略委托：所有 key 操作委托给 StorageKeyStrategy
  - IO委托：存储操作委托给 backend
  - 输入校验：委托给 strategy 进行参数校验
"""

from datamind.config.storage import StorageConfig
from datamind.storage.base import BaseStorageBackend
from datamind.storage.factory import get_backend
from datamind.storage.strategy import StorageKeyStrategy
from datamind.storage.observability import observe_storage


class StorageAdmin:
    """存储管理类（唯一业务入口）"""

    def __init__(self, config: StorageConfig):
        """初始化存储管理API

        参数：
            config: 存储配置对象
        """
        self.config = config
        self.backend: BaseStorageBackend = get_backend(config)
        self._strategy = StorageKeyStrategy(config.model_dir)

    @observe_storage("save")
    def save(self, model_id: str, filename: str, data: bytes) -> str:
        """保存模型文件

        参数：
            model_id: 模型ID
            filename: 文件名
            data: 文件二进制数据

        返回：
            存储 key
        """
        key = self._strategy.model_key(model_id, filename)
        self.backend.put_object(key, data)
        return key

    @observe_storage("load")
    def load(self, model_id: str, filename: str) -> bytes:
        """加载模型文件

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            文件二进制数据
        """
        key = self._strategy.model_key(model_id, filename)
        return self.backend.get_object(key)

    @observe_storage("delete")
    def delete(self, model_id: str, filename: str) -> bool:
        """删除模型文件

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            删除成功返回 True
        """
        key = self._strategy.model_key(model_id, filename)
        self.backend.delete_object(key)
        return True

    @observe_storage("exists")
    def exists(self, model_id: str, filename: str) -> bool:
        """检查模型文件是否存在

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            存在返回 True，否则返回 False
        """
        key = self._strategy.model_key(model_id, filename)
        return self.backend.object_exists(key)

    @observe_storage("list")
    def list(self, model_id: str) -> list[str]:
        """列出模型的所有文件

        参数：
            model_id: 模型ID

        返回：
            文件名列表
        """
        prefix = self._strategy.model_prefix(model_id)
        keys = self.backend.list_objects(prefix)
        return [self._strategy.extract_filename(k) for k in keys]