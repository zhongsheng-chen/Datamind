# datamind/storage/admin.py

"""存储管理API

提供业务级别的存储操作接口，是唯一业务入口。

支持两种访问方式：
  - 结构化方式：基于模型信息进行访问
  - key方式：基于存储键直接访问

核心功能：
  - save: 保存模型文件
  - load: 加载模型文件
  - delete: 删除模型文件
  - exists: 检查模型文件是否存在
  - list: 列出模型的所有文件
  - save_by_key: 通过存储键保存文件
  - load_by_key: 通过存储键加载文件
  - delete_by_key: 通过存储键删除文件
  - exists_by_key: 通过存储键检查文件是否存在

使用示例：
  from datamind.storage import get_storage

  storage = get_storage()

  # 基于模型信息
  storage_key = storage.save(
      model_id="scorecard",
      version="1.0.0",
      filename="model.pkl",
      data=data,
  )

  # 基于存储键
  storage.delete_by_key(storage_key)
"""

from datamind.config.storage import StorageConfig
from datamind.storage.base import BaseStorageBackend
from datamind.storage.factory import get_backend
from datamind.storage.strategy import StorageKeyStrategy
from datamind.storage.observability import observe_storage


class StorageAdmin:
    """存储管理类"""

    def __init__(self, config: StorageConfig):
        """初始化存储管理

        参数：
            config: 存储配置对象
        """
        self.config = config
        self.backend: BaseStorageBackend = get_backend(config)
        self._strategy = StorageKeyStrategy(config.model_dir)

    def _resolve_key(
        self,
        *,
        key: str | None = None,
        model_id: str | None = None,
        version: str | None = None,
        filename: str | None = None,
    ) -> str:
        """解析存储键

        参数：
            key: 存储键（优先使用）
            model_id: 模型ID
            version: 模型版本号
            filename: 文件名

        返回：
            存储键

        异常：
            ValueError: 参数不完整或不合法
        """
        if key is not None:
            return key

        if model_id is not None and version is not None and filename is not None:
            return self._strategy.model_key(model_id, version, filename)

        raise ValueError("必须提供 key 或 (model_id, version, filename) 三参数")

    @observe_storage("save")
    def save(
        self,
        *,
        data: bytes,
        key: str | None = None,
        model_id: str | None = None,
        version: str | None = None,
        filename: str | None = None,
    ) -> str:
        """保存模型文件

        参数：
            data: 二进制数据
            key: 存储键（可选）
            model_id: 模型ID（可选）
            version: 模型版本号（可选）
            filename: 文件名（可选）

        返回：
            存储键
        """
        resolved_key = self._resolve_key(
            key=key,
            model_id=model_id,
            version=version,
            filename=filename,
        )

        self.backend.put_object(resolved_key, data)
        return resolved_key

    @observe_storage("load")
    def load(
        self,
        *,
        key: str | None = None,
        model_id: str | None = None,
        version: str | None = None,
        filename: str | None = None,
    ) -> bytes:
        """加载模型文件

        参数：
            key: 存储键（可选）
            model_id: 模型ID（可选）
            version: 模型版本号（可选）
            filename: 文件名（可选）

        返回：
            二进制数据
        """
        resolved_key = self._resolve_key(
            key=key,
            model_id=model_id,
            version=version,
            filename=filename,
        )

        return self.backend.get_object(resolved_key)

    @observe_storage("delete")
    def delete(
        self,
        *,
        key: str | None = None,
        model_id: str | None = None,
        version: str | None = None,
        filename: str | None = None,
        strict: bool = False,
    ) -> bool:
        """删除模型文件

        参数：
            key: 存储键（可选）
            model_id: 模型ID（可选）
            version: 模型版本号（可选）
            filename: 文件名（可选）
            strict: 是否严格模式，开启时文件不存在则抛出异常

        返回：
            删除成功返回 True

        异常：
            FileNotFoundError: strict 模式下文件不存在时抛出
        """
        resolved_key = self._resolve_key(
            key=key,
            model_id=model_id,
            version=version,
            filename=filename,
        )

        exists = self.backend.object_exists(resolved_key)
        if strict and not exists:
            raise FileNotFoundError(f"文件不存在: {resolved_key}")

        self.backend.delete_object(resolved_key)
        return True

    @observe_storage("exists")
    def exists(
        self,
        *,
        key: str | None = None,
        model_id: str | None = None,
        version: str | None = None,
        filename: str | None = None,
    ) -> bool:
        """检查模型文件是否存在

        参数：
            key: 存储键（可选）
            model_id: 模型ID（可选）
            version: 模型版本号（可选）
            filename: 文件名（可选）

        返回：
            是否存在
        """
        resolved_key = self._resolve_key(
            key=key,
            model_id=model_id,
            version=version,
            filename=filename,
        )

        return self.backend.object_exists(resolved_key)

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

    # ==================== 基于存储键的操作 ====================

    @observe_storage("save_by_key")
    def save_by_key(self, key: str, data: bytes) -> str:
        """通过存储键保存文件

        参数：
            key: 存储键
            data: 二进制数据

        返回：
            存储键
        """
        self.backend.put_object(key, data)
        return key

    @observe_storage("load_by_key")
    def load_by_key(self, key: str) -> bytes:
        """通过存储键加载文件

        参数：
            key: 存储键

        返回：
            二进制数据
        """
        return self.backend.get_object(key)

    @observe_storage("delete_by_key")
    def delete_by_key(self, key: str, strict: bool = False) -> bool:
        """通过存储键删除文件

        参数：
            key: 存储键
            strict: 是否严格模式，开启时文件不存在则抛出异常

        返回：
            删除成功返回 True

        异常：
            FileNotFoundError: strict 模式下文件不存在时抛出
        """
        exists = self.backend.object_exists(key)
        if strict and not exists:
            raise FileNotFoundError(f"文件不存在: {key}")

        self.backend.delete_object(key)
        return True

    @observe_storage("exists_by_key")
    def exists_by_key(self, key: str) -> bool:
        """通过存储键检查文件是否存在

        参数：
            key: 存储键

        返回：
            是否存在
        """
        return self.backend.object_exists(key)