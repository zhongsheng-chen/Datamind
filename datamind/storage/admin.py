"""存储管理 API.

提供业务级别的存储操作接口，是唯一业务入口。

支持两种访问方式：
  - 结构化方式：基于模型信息进行访问
  - key 方式：基于存储键直接访问

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

  storage_key = storage.save(
      model_name="scorecard",
      version="1.0.0",
      artifact_id="art_0123456789abcdef",
      filename="scorecard.pkl",
      data=data,
  )

  storage.delete_by_key(
      storage_key,
      strict=True,
  )
"""

from datamind.config.storage import StorageConfig
from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import StorageNotFoundError
from datamind.storage.factory import get_backend
from datamind.storage.observability import observe_storage
from datamind.storage.strategy import StorageKeyStrategy


class StorageAdmin:
    """存储管理类."""

    def __init__(
            self,
            config: StorageConfig,
    ) -> None:
        """初始化存储管理.

        参数：
            config: 存储配置对象
        """
        self.config = config
        self.backend: BaseStorageBackend = get_backend(
            config
        )
        self._strategy = StorageKeyStrategy(
            config.model_dir
        )

    @property
    def storage_type(
            self,
    ) -> str:
        """获取当前存储后端类型."""
        return self.backend.__class__.__name__

    def _resolve_key(
            self,
            *,
            key: str | None = None,
            model_name: str | None = None,
            version: str | None = None,
            artifact_id: str | None = None,
            filename: str | None = None,
    ) -> str:
        """解析存储键.

        参数：
            key: 存储键，优先使用
            model_name: 模型名称
            version: 模型版本号
            artifact_id: 模型制品 ID
            filename: 文件名

        返回：
            存储键

        异常：
            ValueError: 参数不完整
        """
        if key is not None:
            return key

        if (
                model_name is not None
                and version is not None
                and artifact_id is not None
                and filename is not None
        ):
            return self._strategy.model_key(
                model_name,
                version,
                artifact_id,
                filename,
            )

        raise ValueError(
            "必须提供 key 或 "
            "(model_name, version, artifact_id, filename) 四参数"
        )

    def _validate_data(
            self,
            data: bytes,
    ) -> None:
        """校验待存储数据.

        参数：
            data: 待存储的二进制数据

        异常：
            TypeError: data 不是 bytes
            ValueError: 数据大小超过配置上限
        """
        if not isinstance(
                data,
                bytes,
        ):
            raise TypeError(
                "存储数据必须是 bytes"
            )

        data_size = len(data)
        max_file_size = self.config.max_file_size

        if data_size > max_file_size:
            raise ValueError(
                "文件大小超过配置上限: "
                f"size={data_size}, "
                f"max_file_size={max_file_size}"
            )

    def _delete_key(
            self,
            key: str,
            *,
            strict: bool,
    ) -> bool:
        """删除指定存储键.

        参数：
            key: 存储键
            strict: 是否严格模式

        返回：
            删除请求执行成功返回 True

        异常：
            StorageNotFoundError: strict 模式下对象不存在
        """
        if (
                strict
                and not self.backend.object_exists(
                    key
                )
        ):
            raise StorageNotFoundError(
                f"对象不存在: {key}"
            )

        self.backend.delete_object(
            key
        )

        return True

    @observe_storage("save")
    def save(
            self,
            *,
            data: bytes,
            key: str | None = None,
            model_name: str | None = None,
            version: str | None = None,
            artifact_id: str | None = None,
            filename: str | None = None,
    ) -> str:
        """保存模型文件.

        参数：
            data: 二进制数据
            key: 存储键（可选）
            model_name: 模型名称（可选）
            version: 模型版本号（可选）
            artifact_id: 模型制品 ID（可选）
            filename: 文件名（可选）

        返回：
            存储键

        异常：
            TypeError: data 不是 bytes
            ValueError: 参数不完整或数据大小超过配置上限
        """
        self._validate_data(
            data
        )

        resolved_key = self._resolve_key(
            key=key,
            model_name=model_name,
            version=version,
            artifact_id=artifact_id,
            filename=filename,
        )

        self.backend.put_object(
            resolved_key,
            data,
        )

        return resolved_key

    @observe_storage("load")
    def load(
            self,
            *,
            key: str | None = None,
            model_name: str | None = None,
            version: str | None = None,
            artifact_id: str | None = None,
            filename: str | None = None,
    ) -> bytes:
        """加载模型文件.

        参数：
            key: 存储键（可选）
            model_name: 模型名称（可选）
            version: 模型版本号（可选）
            artifact_id: 模型制品 ID（可选）
            filename: 文件名（可选）

        返回：
            二进制数据

        异常：
            ValueError: 参数不完整
        """
        resolved_key = self._resolve_key(
            key=key,
            model_name=model_name,
            version=version,
            artifact_id=artifact_id,
            filename=filename,
        )

        return self.backend.get_object(
            resolved_key
        )

    @observe_storage("delete")
    def delete(
            self,
            *,
            key: str | None = None,
            model_name: str | None = None,
            version: str | None = None,
            artifact_id: str | None = None,
            filename: str | None = None,
            strict: bool = False,
    ) -> bool:
        """删除模型文件.

        参数：
            key: 存储键（可选）
            model_name: 模型名称（可选）
            version: 模型版本号（可选）
            artifact_id: 模型制品 ID（可选）
            filename: 文件名（可选）
            strict: 是否严格模式，开启时对象不存在则抛出异常

        返回：
            删除请求执行成功返回 True

        异常：
            ValueError: 参数不完整
            StorageNotFoundError: strict 模式下对象不存在
        """
        resolved_key = self._resolve_key(
            key=key,
            model_name=model_name,
            version=version,
            artifact_id=artifact_id,
            filename=filename,
        )

        return self._delete_key(
            resolved_key,
            strict=strict,
        )

    @observe_storage("exists")
    def exists(
            self,
            *,
            key: str | None = None,
            model_name: str | None = None,
            version: str | None = None,
            artifact_id: str | None = None,
            filename: str | None = None,
    ) -> bool:
        """检查模型文件是否存在.

        参数：
            key: 存储键（可选）
            model_name: 模型名称（可选）
            version: 模型版本号（可选）
            artifact_id: 模型制品 ID（可选）
            filename: 文件名（可选）

        返回：
            是否存在

        异常：
            ValueError: 参数不完整
        """
        resolved_key = self._resolve_key(
            key=key,
            model_name=model_name,
            version=version,
            artifact_id=artifact_id,
            filename=filename,
        )

        return self.backend.object_exists(
            resolved_key
        )

    @observe_storage("list")
    def list(
            self,
            model_name: str,
    ) -> list[str]:
        """列出模型的所有文件.

        参数：
            model_name: 模型名称

        返回：
            相对于模型目录的文件键列表，
            格式为 {version}/artifacts/{artifact_id}/{filename}
        """
        prefix = self._strategy.model_prefix(
            model_name
        )

        keys = self.backend.list_objects(
            prefix
        )

        return [
            key.removeprefix(prefix)
            for key in keys
            if key.startswith(prefix)
        ]

    @observe_storage("save_by_key")
    def save_by_key(
            self,
            key: str,
            data: bytes,
    ) -> str:
        """通过存储键保存文件.

        参数：
            key: 存储键
            data: 二进制数据

        返回：
            存储键

        异常：
            TypeError: data 不是 bytes
            ValueError: 数据大小超过配置上限
        """
        self._validate_data(
            data
        )

        self.backend.put_object(
            key,
            data,
        )

        return key

    @observe_storage("load_by_key")
    def load_by_key(
            self,
            key: str,
    ) -> bytes:
        """通过存储键加载文件.

        参数：
            key: 存储键

        返回：
            二进制数据
        """
        return self.backend.get_object(
            key
        )

    @observe_storage("delete_by_key")
    def delete_by_key(
            self,
            key: str,
            strict: bool = False,
    ) -> bool:
        """通过存储键删除文件.

        参数：
            key: 存储键
            strict: 是否严格模式，开启时对象不存在则抛出异常

        返回：
            删除请求执行成功返回 True

        异常：
            StorageNotFoundError: strict 模式下对象不存在
        """
        return self._delete_key(
            key,
            strict=strict,
        )

    @observe_storage("exists_by_key")
    def exists_by_key(
            self,
            key: str,
    ) -> bool:
        """通过存储键检查文件是否存在.

        参数：
            key: 存储键

        返回：
            是否存在
        """
        return self.backend.object_exists(
            key
        )
