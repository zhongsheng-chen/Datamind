"""存储配置.

定义模型文件的存储后端和连接参数，支持本地存储和 MinIO 对象存储。

本地存储和 MinIO 配置同时存在，通过 type 选择当前生效的存储后端。

核心功能：
  - LocalStorageConfig: 读取本地存储配置
  - MinIOStorageConfig: 读取 MinIO 对象存储配置
  - StorageConfig: 选择存储后端并校验通用配置

属性：

通用属性：
  - type: 存储类型，local 或 minio
  - max_file_size: 单个模型文件最大字节数，默认 200 MB
  - model_dir: 模型存放的相对子目录，默认 models

本地存储：
  - base_dir: 本地基础目录

MinIO 存储：
  - endpoint: MinIO 服务地址
  - bucket: 存储桶名称
  - access_key: 访问密钥
  - secret_key: 秘密密钥
  - secure: 是否启用 TLS/SSL
  - region: S3 兼容区域，可选
  - base_prefix: 对象存储基础前缀

环境变量：

通用：
  - DATAMIND_STORAGE_TYPE:
    存储类型，默认 local
  - DATAMIND_STORAGE_MAX_FILE_SIZE:
    文件大小上限，默认 209715200
  - DATAMIND_STORAGE_MODEL_DIR:
    模型目录，默认 models

本地存储：
  - DATAMIND_STORAGE_LOCAL_BASE_DIR:
    本地基础目录，默认 ./data

MinIO 存储：
  - DATAMIND_STORAGE_MINIO_ENDPOINT:
    服务端点，默认 localhost:9000
  - DATAMIND_STORAGE_MINIO_BUCKET:
    存储桶，默认 datamind
  - DATAMIND_STORAGE_MINIO_ACCESS_KEY:
    访问密钥，默认空
  - DATAMIND_STORAGE_MINIO_SECRET_KEY:
    秘密密钥，默认空
  - DATAMIND_STORAGE_MINIO_SECURE:
    是否启用 TLS，默认 false
  - DATAMIND_STORAGE_MINIO_REGION:
    区域，默认 None
  - DATAMIND_STORAGE_MINIO_BASE_PREFIX:
    基础前缀，默认 datamind

使用示例：
  from datamind.config.storage import StorageConfig

  config = StorageConfig()

  print(config.type)
  print(config.model_dir)
"""

from pathlib import (
    Path,
    PurePosixPath,
    PureWindowsPath,
)

from pydantic import (
    Field,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)

from datamind.constants import (
    MB,
    StorageType,
)


class LocalStorageConfig(BaseSettings):
    """本地存储配置."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_LOCAL_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    base_dir: Path = Path("./data")


class MinIOStorageConfig(BaseSettings):
    """MinIO 存储配置."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_MINIO_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    endpoint: str = "localhost:9000"
    bucket: str = "datamind"
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False
    region: str | None = None
    base_prefix: str = "datamind"


class StorageConfig(BaseSettings):
    """存储配置类."""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    type: StorageType = StorageType.LOCAL
    max_file_size: int = 200 * MB
    model_dir: str = "models"

    local: LocalStorageConfig = Field(
        default_factory=LocalStorageConfig
    )
    minio: MinIOStorageConfig = Field(
        default_factory=MinIOStorageConfig
    )

    @model_validator(mode="after")
    def validate_config(self) -> "StorageConfig":
        """校验存储配置参数."""
        if self.max_file_size <= 0:
            raise ValueError(
                "max_file_size 必须大于 0，"
                f"当前值：{self.max_file_size}"
            )

        model_dir = self.model_dir.strip()

        if not model_dir:
            raise ValueError(
                "model_dir 不能为空"
            )

        posix_path = PurePosixPath(
            model_dir.replace("\\", "/")
        )
        windows_path = PureWindowsPath(model_dir)

        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or windows_path.drive
        ):
            raise ValueError(
                "model_dir 必须是相对目录，"
                f"当前值：{self.model_dir}"
            )

        if (
            ".." in posix_path.parts
            or ".." in windows_path.parts
        ):
            raise ValueError(
                "model_dir 不能包含上级目录引用，"
                f"当前值：{self.model_dir}"
            )

        if self.type == StorageType.MINIO:
            if not self.minio.endpoint.strip():
                raise ValueError(
                    "使用 minio 存储时，"
                    "endpoint 不能为空"
                )

            if not self.minio.bucket.strip():
                raise ValueError(
                    "使用 minio 存储时，"
                    "bucket 不能为空"
                )

            if not self.minio.access_key.strip():
                raise ValueError(
                    "使用 minio 存储时，"
                    "access_key 不能为空"
                )

            if not self.minio.secret_key.strip():
                raise ValueError(
                    "使用 minio 存储时，"
                    "secret_key 不能为空"
                )

        return self
