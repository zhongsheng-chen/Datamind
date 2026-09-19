"""存储路径解析器

根据存储类型将存储键解析为完整路径。

核心功能：
  - resolve: 解析存储键为完整路径

使用示例：
  from datamind.storage.resolver import StorageResolver

  resolver = StorageResolver()

  path = resolver.resolve(
      "models/mdl_0123456789abcdef/1.0.0/"
      "artifacts/art_0123456789abcdef/model.pkl"
  )
"""

from pathlib import Path

from datamind.config.providers import get_storage_config
from datamind.constants import StorageType
from datamind.storage.errors import StorageKeyError


class StorageResolver:
    """存储路径解析器"""

    def __init__(self) -> None:
        """初始化存储路径解析器"""
        self.config = get_storage_config()

    def resolve(
        self,
        key: str,
    ) -> str:
        """解析存储键为完整路径

        参数：
            key: 存储键

        返回：
            本地文件系统绝对路径或 S3 兼容路径

        异常：
            StorageKeyError: 存储键格式非法或发生路径越界
            ValueError: 不支持的存储类型
        """
        normalized_key = self._normalize_key(key)
        storage_type = self.config.type

        if storage_type == StorageType.LOCAL:
            return self._resolve_local(normalized_key)

        if storage_type == StorageType.MINIO:
            return self._resolve_minio(normalized_key)

        raise ValueError(
            f"不支持的存储类型: {storage_type}"
        )

    def _resolve_local(
        self,
        key: str,
    ) -> str:
        """解析本地存储路径

        参数：
            key: 已标准化的存储键

        返回：
            本地文件系统绝对路径

        异常：
            StorageKeyError: 存储键越过本地基础目录
        """
        base_dir = (
            Path(
                self.config.local.base_dir
            )
            .expanduser()
            .resolve()
        )

        path = (
            base_dir
            / Path(key)
        ).resolve()

        if not path.is_relative_to(base_dir):
            raise StorageKeyError(
                f"非法的存储键，检测到路径遍历: {key}"
            )

        return str(path)

    def _resolve_minio(
        self,
        key: str,
    ) -> str:
        """解析 MinIO 存储路径

        参数：
            key: 已标准化的存储键

        返回：
            S3 兼容路径，格式为：
            s3://{bucket}/{base_prefix}/{key}

        异常：
            StorageKeyError: 存储桶或基础前缀格式非法
        """
        config = self.config.minio

        bucket = config.bucket.strip()

        if (
            not bucket
            or "/" in bucket
            or "\\" in bucket
        ):
            raise StorageKeyError(
                f"非法的 MinIO 存储桶名称: {config.bucket}"
            )

        base_prefix = (
            config.base_prefix
            .strip()
            .strip("/\\")
        )

        if base_prefix:
            normalized_prefix = self._normalize_key(
                base_prefix
            )
            object_path = (
                f"{normalized_prefix}/{key}"
            )
        else:
            object_path = key

        return f"s3://{bucket}/{object_path}"

    @staticmethod
    def _normalize_key(
        key: str,
    ) -> str:
        """标准化并校验存储键

        参数：
            key: 原始存储键

        返回：
            使用正斜杠分隔的标准存储键

        异常：
            StorageKeyError: 存储键为空、包含空字符、
                使用绝对路径或包含非法路径段
        """
        if not isinstance(key, str):
            raise StorageKeyError(
                "存储键必须是字符串"
            )

        if "\x00" in key:
            raise StorageKeyError(
                "存储键不能包含空字符"
            )

        normalized_key = key.replace(
            "\\",
            "/",
        )

        if not normalized_key:
            raise StorageKeyError(
                "存储键不能为空"
            )

        if normalized_key.startswith("/"):
            raise StorageKeyError(
                f"存储键不能使用绝对路径: {key}"
            )

        parts = normalized_key.split("/")

        if any(
            part in {"", ".", ".."}
            for part in parts
        ):
            raise StorageKeyError(
                f"非法的存储键: {key}"
            )

        return "/".join(parts)
