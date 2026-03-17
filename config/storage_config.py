# datamind/config/storage_config.py
"""
存储配置模块

用于管理不同存储类型的配置
"""

from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageType(str, Enum):
    """存储类型枚举"""
    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"


class LocalStorageConfig(BaseSettings):
    """本地存储配置"""
    model_config = SettingsConfigDict(extra="ignore")

    base_path: str = Field(
        default="./models",
        validation_alias="DATAMIND_LOCAL_STORAGE_PATH",
        description="本地存储基础路径"
    )
    models_subpath: str = Field(
        default="models",
        validation_alias="DATAMIND_LOCAL_MODELS_SUBPATH",
        description="模型子路径"
    )


class MinIOStorageConfig(BaseSettings):
    """MinIO存储配置"""
    model_config = SettingsConfigDict(extra="ignore")

    endpoint: str = Field(
        default="localhost:9000",
        validation_alias="MINIO_ENDPOINT",
        description="MinIO服务端点"
    )
    access_key: str = Field(
        default="",
        validation_alias="MINIO_ACCESS_KEY",
        description="MinIO访问密钥"
    )
    secret_key: str = Field(
        default="",
        validation_alias="MINIO_SECRET_KEY",
        description="MinIO秘密密钥"
    )
    bucket: str = Field(
        default="datamind-storage",
        validation_alias="MINIO_BUCKET",
        description="MinIO存储桶名称"
    )
    secure: bool = Field(
        default=False,
        validation_alias="MINIO_SECURE",
        description="是否使用HTTPS连接MinIO"
    )
    region: Optional[str] = Field(
        default=None,
        validation_alias="MINIO_REGION",
        description="MinIO区域"
    )
    location: str = Field(
        default="us-east-1",
        validation_alias="MINIO_LOCATION",
        description="MinIO存储桶位置"
    )
    models_prefix: str = Field(
        default="models/",
        validation_alias="MINIO_MODELS_PREFIX",
        description="模型对象前缀"
    )
    timeout: int = Field(
        default=30,
        validation_alias="MINIO_TIMEOUT",
        description="超时时间（秒）"
    )
    max_connections: int = Field(
        default=10,
        validation_alias="MINIO_MAX_CONNECTIONS",
        description="最大连接数"
    )


class S3StorageConfig(BaseSettings):
    """AWS S3存储配置"""
    model_config = SettingsConfigDict(extra="ignore")

    endpoint: Optional[str] = Field(
        default=None,
        validation_alias="S3_ENDPOINT",
        description="S3自定义端点（用于兼容S3的其他服务）"
    )
    access_key_id: str = Field(
        default="",
        validation_alias="AWS_ACCESS_KEY_ID",
        description="AWS访问密钥ID"
    )
    secret_access_key: str = Field(
        default="",
        validation_alias="AWS_SECRET_ACCESS_KEY",
        description="AWS秘密访问密钥"
    )
    bucket: str = Field(
        default="datamind-storage",
        validation_alias="S3_BUCKET",
        description="S3存储桶名称"
    )
    region: str = Field(
        default="us-east-1",
        validation_alias="AWS_REGION",
        description="AWS区域"
    )
    prefix: str = Field(
        default="models/",
        validation_alias="S3_PREFIX",
        description="S3对象键前缀"
    )
    acl: Optional[str] = Field(
        default=None,
        validation_alias="S3_ACL",
        description="S3对象ACL（如 'private', 'public-read'）"
    )
    use_ssl: bool = Field(
        default=True,
        validation_alias="S3_USE_SSL",
        description="是否使用SSL连接S3"
    )
    verify_ssl: bool = Field(
        default=True,
        validation_alias="S3_VERIFY_SSL",
        description="是否验证SSL证书"
    )
    addressing_style: Literal["auto", "virtual", "path"] = Field(
        default="auto",
        validation_alias="S3_ADDRESSING_STYLE",
        description="S3寻址风格"
    )
    max_pool_connections: int = Field(
        default=10,
        validation_alias="S3_MAX_POOL_CONNECTIONS",
        description="S3连接池最大连接数"
    )
    timeout: int = Field(
        default=30,
        validation_alias="S3_TIMEOUT",
        description="S3请求超时时间（秒）"
    )
    retries: int = Field(
        default=3,
        validation_alias="S3_RETRIES",
        description="S3请求重试次数"
    )


class StorageConfig(BaseSettings):
    """存储配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # 存储类型
    storage_type: StorageType = Field(
        default=StorageType.LOCAL,
        validation_alias="DATAMIND_STORAGE_TYPE",
        description="存储类型: local/minio/s3"
    )

    # 存储通用配置
    default_ttl: int = Field(
        default=86400,
        validation_alias="DATAMIND_STORAGE_DEFAULT_TTL",
        description="存储对象默认过期时间（秒）"
    )
    enable_cache: bool = Field(
        default=True,
        validation_alias="DATAMIND_STORAGE_ENABLE_CACHE",
        description="是否启用存储缓存"
    )
    cache_size: int = Field(
        default=100,
        validation_alias="DATAMIND_STORAGE_CACHE_SIZE",
        description="存储缓存大小（对象数量）"
    )
    cache_ttl: int = Field(
        default=300,
        validation_alias="DATAMIND_STORAGE_CACHE_TTL",
        description="存储缓存过期时间（秒）"
    )
    enable_compression: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_COMPRESSION",
        description="是否启用存储压缩"
    )
    compression_level: int = Field(
        default=6,
        validation_alias="DATAMIND_STORAGE_COMPRESSION_LEVEL",
        description="存储压缩级别 (1-9)"
    )
    enable_encryption: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_ENCRYPTION",
        description="是否启用存储加密"
    )
    encryption_key: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_STORAGE_ENCRYPTION_KEY",
        description="存储加密密钥"
    )
    max_file_size: int = Field(
        default=1024 * 1024 * 1024,
        validation_alias="DATAMIND_STORAGE_MAX_FILE_SIZE",
        description="存储最大文件大小（字节）"
    )
    allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        validation_alias="DATAMIND_STORAGE_ALLOWED_EXTENSIONS",
        description="允许存储的文件扩展名"
    )
    chunk_size: int = Field(
        default=1024 * 1024 * 8,
        validation_alias="DATAMIND_STORAGE_CHUNK_SIZE",
        description="存储分块大小（用于大文件上传）"
    )
    multipart_threshold: int = Field(
        default=1024 * 1024 * 100,
        validation_alias="DATAMIND_STORAGE_MULTIPART_THRESHOLD",
        description="启用分片上传的阈值"
    )

    # 本地存储配置
    local: LocalStorageConfig = Field(
        default_factory=LocalStorageConfig,
        description="本地存储配置"
    )

    # MinIO存储配置
    minio: MinIOStorageConfig = Field(
        default_factory=MinIOStorageConfig,
        description="MinIO存储配置"
    )

    # S3存储配置
    s3: S3StorageConfig = Field(
        default_factory=S3StorageConfig,
        description="S3存储配置"
    )


    @field_validator("compression_level")
    @classmethod
    def validate_compression_level(cls, v):
        """验证压缩级别"""
        if v < 1 or v > 9:
            raise ValueError("compression_level 必须在 1 到 9 之间")
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v):
        """验证最大文件大小"""
        if v < 1024 * 1024:
            raise ValueError("max_file_size 不能小于1MB")
        if v > 1024 * 1024 * 1024 * 10:  # 10GB
            raise ValueError("max_file_size 不能大于10GB")
        return v

    @field_validator("allowed_extensions")
    @classmethod
    def validate_allowed_extensions(cls, v):
        """验证允许的文件扩展名"""
        for ext in v:
            if not ext.startswith('.'):
                raise ValueError(f"文件扩展名必须以点开头: {ext}")
        return v

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, v):
        """验证分块大小"""
        if v < 1024 * 1024:  # 小于1MB
            raise ValueError("chunk_size 不能小于1MB")
        if v > 1024 * 1024 * 100:  # 大于100MB
            raise ValueError("chunk_size 不能大于100MB")
        return v

    @model_validator(mode='after')
    def validate_storage_config(self):
        """验证存储配置的一致性"""
        storage_type = self.storage_type
        minio = self.minio
        s3 = self.s3

        # 根据存储类型验证必要配置
        if storage_type == StorageType.MINIO:
            if not minio.endpoint:
                raise ValueError("使用MinIO存储时必须提供 minio.endpoint")
            if not minio.access_key:
                raise ValueError("使用MinIO存储时必须提供 minio.access_key")
            if not minio.secret_key:
                raise ValueError("使用MinIO存储时必须提供 minio.secret_key")
            if not minio.bucket:
                raise ValueError("使用MinIO存储时必须提供 minio.bucket")

        elif storage_type == StorageType.S3:
            if not s3.access_key_id:
                raise ValueError("使用S3存储时必须提供 s3.access_key_id")
            if not s3.secret_access_key:
                raise ValueError("使用S3存储时必须提供 s3.secret_access_key")
            if not s3.bucket:
                raise ValueError("使用S3存储时必须提供 s3.bucket")

        # 验证加密配置
        if self.enable_encryption and not self.encryption_key:
            raise ValueError("启用加密时必须提供 encryption_key")

        return self

    @model_validator(mode='after')
    def validate_cache_config(self):
        """验证缓存配置"""
        if self.enable_cache:
            if self.cache_size < 1:
                raise ValueError("enable_cache=True 时 cache_size 必须大于0")
            if self.cache_ttl < 1:
                raise ValueError("enable_cache=True 时 cache_ttl 必须大于0")
        return self


__all__ = [
    "StorageConfig",
    "StorageType",
    "LocalStorageConfig",
    "MinIOStorageConfig",
    "S3StorageConfig"
]