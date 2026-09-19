"""MinIO 对象存储后端

将数据存储在 MinIO 或 S3 兼容的对象存储中。

核心功能：
  - put_object: 上传对象到存储桶
  - get_object: 下载对象内容
  - delete_object: 删除对象
  - object_exists: 检查对象是否存在
  - list_objects: 列出指定前缀下的所有对象

使用示例：
  from datamind.storage.minio import MinIOStorageBackend

  storage = MinIOStorageBackend(
      endpoint="127.0.0.1:9000",
      access_key="accessKey",
      secret_key="secretKey",
      bucket="datamind",
      base_prefix="artifacts",
      secure=False,
  )

  storage.put_object(
      key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      ),
      data=b"model data",
  )

  data = storage.get_object(
      key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      )
  )

  keys = storage.list_objects(
      prefix="models/mdl_0123456789abcdef"
  )
"""

from contextlib import suppress
from io import BytesIO

from minio import Minio, S3Error

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import (
    StorageBackendError,
    StorageConnectionError,
    StorageKeyError,
    StorageNotFoundError,
    StoragePermissionError,
)


class MinIOStorageBackend(BaseStorageBackend):
    """MinIO 对象存储后端"""

    _OBJECT_NOT_FOUND_ERROR_CODES = {
        "NoSuchKey",
        "NoSuchObject",
        "NotFound",
    }

    _RESOURCE_NOT_FOUND_ERROR_CODES = {
        *_OBJECT_NOT_FOUND_ERROR_CODES,
        "NoSuchBucket",
    }

    _PERMISSION_ERROR_CODES = {
        "AccessDenied",
        "ExpiredToken",
        "InvalidAccessKeyId",
        "InvalidToken",
        "SignatureDoesNotMatch",
    }

    def __init__(
            self,
            endpoint: str,
            access_key: str,
            secret_key: str,
            bucket: str,
            secure: bool,
            base_prefix: str = "",
            region: str | None = None,
    ) -> None:
        """初始化 MinIO 存储后端

        参数：
            endpoint: MinIO 服务端点
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket: 存储桶名称
            secure: 是否启用 TLS
            base_prefix: 对象基础前缀，默认为空
            region: 区域（可选）
        """
        normalized_bucket = bucket.strip()

        if (
                not normalized_bucket
                or "/" in normalized_bucket
                or "\\" in normalized_bucket
        ):
            raise ValueError(
                f"非法的 MinIO 存储桶名称: {bucket}"
            )

        self.bucket = normalized_bucket
        self.base_prefix = self._normalize_key(
            base_prefix.strip("/\\"),
            allow_empty=True,
        )

        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region=region,
            )

        except Exception as exc:
            raise StorageConnectionError(
                f"初始化 MinIO 客户端失败: {exc}"
            ) from exc

        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)

        except S3Error as exc:
            raise self._map_s3_error(
                action="访问或创建存储桶",
                error=exc,
            ) from exc

        except Exception as exc:
            raise StorageConnectionError(
                f"访问或创建存储桶失败: {exc}"
            ) from exc

    def put_object(
            self,
            key: str,
            data: bytes,
    ) -> None:
        """上传对象到存储桶

        参数：
            key: 逻辑对象键
            data: 二进制数据
        """
        object_name = self._object_name(key)

        try:
            self.client.put_object(
                self.bucket,
                object_name,
                BytesIO(data),
                length=len(data),
            )

        except S3Error as exc:
            raise self._map_s3_error(
                action="上传对象",
                error=exc,
                key=key,
            ) from exc

        except Exception as exc:
            raise StorageConnectionError(
                f"上传对象失败: key={key}, error={exc}"
            ) from exc

    def get_object(
            self,
            key: str,
    ) -> bytes:
        """下载对象内容

        参数：
            key: 逻辑对象键

        返回：
            对象二进制内容

        异常：
            StorageNotFoundError: 对象不存在
            StoragePermissionError: 没有对象读取权限
            StorageConnectionError: 无法连接对象存储
            StorageBackendError: 其他对象存储错误
        """
        object_name = self._object_name(key)
        response = None

        try:
            response = self.client.get_object(
                self.bucket,
                object_name,
            )

            data = response.read()

            if isinstance(data, bytes):
                return data

            raise StorageBackendError(
                f"读取对象失败，响应内容为空: key={key}"
            )

        except S3Error as exc:
            raise self._map_s3_error(
                action="读取对象",
                error=exc,
                key=key,
            ) from exc

        except StorageBackendError:
            raise

        except Exception as exc:
            raise StorageConnectionError(
                f"读取对象失败: key={key}, error={exc}"
            ) from exc

        finally:
            if response is not None:
                with suppress(Exception):
                    response.close()

                with suppress(Exception):
                    response.release_conn()

    def delete_object(
            self,
            key: str,
    ) -> None:
        """删除对象

        对象不存在时保持幂等，不抛出异常。

        参数：
            key: 逻辑对象键
        """
        object_name = self._object_name(key)

        try:
            self.client.remove_object(
                self.bucket,
                object_name,
            )

        except S3Error as exc:
            if self._is_object_not_found_error(exc):
                return

            raise self._map_s3_error(
                action="删除对象",
                error=exc,
                key=key,
            ) from exc

        except Exception as exc:
            raise StorageConnectionError(
                f"删除对象失败: key={key}, error={exc}"
            ) from exc

    def object_exists(
            self,
            key: str,
    ) -> bool:
        """检查对象是否存在

        参数：
            key: 逻辑对象键

        返回：
            存在返回 True，对象不存在返回 False

        异常：
            StoragePermissionError: 没有对象访问权限
            StorageConnectionError: 无法连接对象存储
            StorageBackendError: 其他对象存储错误
        """
        object_name = self._object_name(key)

        try:
            self.client.stat_object(
                self.bucket,
                object_name,
            )

            return True

        except S3Error as exc:
            if self._is_object_not_found_error(exc):
                return False

            raise self._map_s3_error(
                action="检查对象",
                error=exc,
                key=key,
            ) from exc

        except Exception as exc:
            raise StorageConnectionError(
                f"检查对象失败: key={key}, error={exc}"
            ) from exc

    def list_objects(
            self,
            prefix: str,
    ) -> list[str]:
        """列出指定前缀下的所有对象

        参数：
            prefix: 逻辑对象键前缀；空字符串表示基础前缀下的全部对象

        返回：
            去除 base_prefix 后的逻辑对象键列表

        异常：
            StoragePermissionError: 没有对象列表权限
            StorageConnectionError: 无法连接对象存储
            StorageBackendError: 其他对象存储错误
        """
        normalized_prefix = self._normalize_key(
            prefix,
            allow_empty=True,
        )

        object_prefix = self._object_name(
            normalized_prefix,
            allow_empty=True,
        )

        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=object_prefix,
                recursive=True,
            )

            keys = []

            for item in objects:
                if item.object_name is None:
                    continue

                logical_key = self._logical_key(
                    item.object_name
                )

                if logical_key:
                    keys.append(logical_key)

            return sorted(keys)

        except S3Error as exc:
            raise self._map_s3_error(
                action="列出对象",
                error=exc,
                key=prefix,
            ) from exc

        except StorageBackendError:
            raise

        except Exception as exc:
            raise StorageConnectionError(
                f"列出对象失败: prefix={prefix}, error={exc}"
            ) from exc

    def _object_name(
            self,
            key: str,
            *,
            allow_empty: bool = False,
    ) -> str:
        """将逻辑对象键转换为 MinIO 对象名称"""
        normalized_key = self._normalize_key(
            key,
            allow_empty=allow_empty,
        )

        if not self.base_prefix:
            return normalized_key

        if not normalized_key:
            return f"{self.base_prefix}/"

        return f"{self.base_prefix}/{normalized_key}"

    def _logical_key(
            self,
            object_name: str,
    ) -> str:
        """将 MinIO 对象名称转换为逻辑对象键"""
        normalized_name = self._normalize_key(
            object_name,
            allow_empty=False,
        )

        if not self.base_prefix:
            return normalized_name

        prefix = f"{self.base_prefix}/"

        if not normalized_name.startswith(prefix):
            raise StorageBackendError(
                "对象名称不属于当前基础前缀: "
                f"object_name={object_name}, "
                f"base_prefix={self.base_prefix}"
            )

        return normalized_name[len(prefix):]

    @staticmethod
    def _normalize_key(
            key: str,
            *,
            allow_empty: bool,
    ) -> str:
        """标准化并校验对象键或前缀"""
        if not isinstance(key, str):
            raise StorageKeyError(
                "对象键必须是字符串"
            )

        if "\x00" in key:
            raise StorageKeyError(
                "对象键不能包含空字符"
            )

        normalized_key = key.replace(
            "\\",
            "/",
        )

        if normalized_key.startswith("/"):
            raise StorageKeyError(
                f"对象键不能使用绝对路径: {key}"
            )

        if allow_empty:
            normalized_key = normalized_key.rstrip("/")

        if not normalized_key:
            if allow_empty:
                return ""

            raise StorageKeyError(
                "对象键不能为空"
            )

        parts = normalized_key.split("/")

        if any(
                part in {"", ".", ".."}
                for part in parts
        ):
            raise StorageKeyError(
                f"非法的对象键: {key}"
            )

        return "/".join(parts)

    @classmethod
    def _is_object_not_found_error(
            cls,
            error: S3Error,
    ) -> bool:
        """判断是否为对象不存在错误"""
        return error.code in cls._OBJECT_NOT_FOUND_ERROR_CODES

    @classmethod
    def _is_resource_not_found_error(
            cls,
            error: S3Error,
    ) -> bool:
        """判断是否为对象或存储桶不存在错误"""
        return error.code in cls._RESOURCE_NOT_FOUND_ERROR_CODES

    @classmethod
    def _map_s3_error(
            cls,
            *,
            action: str,
            error: S3Error,
            key: str | None = None,
    ) -> StorageBackendError:
        """将 S3 异常映射为存储层标准异常

        参数：
            action: 当前存储操作
            error: MinIO S3 异常
            key: 逻辑对象键（可选）
        """
        target = (
            f", key={key}"
            if key is not None
            else ""
        )
        error_code = error.code or "Unknown"
        error_message = error.message or "未提供错误信息"

        message = (
            f"{action}失败: "
            f"code={error_code}{target}, "
            f"message={error_message}"
        )

        if cls._is_resource_not_found_error(error):
            return StorageNotFoundError(
                message
            )

        if error.code in cls._PERMISSION_ERROR_CODES:
            return StoragePermissionError(
                message
            )

        return StorageBackendError(
            message
        )
