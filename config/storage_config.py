# datamind/config/storage_config.py
"""
存储配置模块
用于管理不同存储类型的配置和客户端初始化
"""
from pathlib import Path
from typing import Dict, Any, Optional, Union, Literal
from enum import Enum
import json
import logging

from pydantic import BaseModel, Field, field_validator, ConfigDict


class StorageType(str, Enum):
    """存储类型枚举"""
    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"


class LocalStorageConfig(BaseModel):
    """本地存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    base_path: Path = Field(..., description="本地存储基础路径")
    models_subpath: str = Field(default="models", description="模型子路径")

    @property
    def models_path(self) -> Path:
        """获取模型存储路径"""
        return self.base_path / self.models_subpath

    def ensure_directories(self):
        """确保目录存在"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)
        return self


class MinIOStorageConfig(BaseModel):
    """MinIO存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint: str = Field(..., description="MinIO服务端点")
    access_key: str = Field(..., description="访问密钥")
    secret_key: str = Field(..., description="秘密密钥")
    bucket: str = Field(..., description="存储桶名称")
    secure: bool = Field(default=False, description="是否使用HTTPS")
    region: Optional[str] = Field(default=None, description="区域")
    location: str = Field(default="us-east-1", description="存储桶位置")
    models_prefix: str = Field(default="models/", description="模型对象前缀")

    # 客户端配置
    timeout: int = Field(default=30, description="超时时间（秒）")
    max_connections: int = Field(default=10, description="最大连接数")

    @property
    def models_path(self) -> str:
        """获取模型存储路径（bucket/prefix格式）"""
        return f"{self.bucket}/{self.models_prefix.rstrip('/')}"

    @property
    def connection_params(self) -> Dict[str, Any]:
        """获取连接参数"""
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "secure": self.secure,
            "region": self.region,
            "timeout": self.timeout,
            "max_connections": self.max_connections,
        }


class S3StorageConfig(BaseModel):
    """AWS S3存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint: Optional[str] = Field(default=None, description="自定义端点")
    access_key_id: str = Field(..., description="访问密钥ID")
    secret_access_key: str = Field(..., description="秘密访问密钥")
    bucket: str = Field(..., description="存储桶名称")
    region: str = Field(default="us-east-1", description="区域")
    prefix: str = Field(default="models/", description="对象键前缀")
    acl: Optional[str] = Field(default=None, description="对象ACL")

    # 连接配置
    use_ssl: bool = Field(default=True, description="是否使用SSL")
    verify_ssl: bool = Field(default=True, description="是否验证SSL证书")
    addressing_style: Literal["auto", "virtual", "path"] = Field(default="auto", description="寻址风格")
    max_pool_connections: int = Field(default=10, description="连接池最大连接数")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    retries: int = Field(default=3, description="重试次数")

    @property
    def models_path(self) -> str:
        """获取模型存储路径（bucket/prefix格式）"""
        return f"{self.bucket}/{self.prefix.rstrip('/')}"

    @property
    def connection_params(self) -> Dict[str, Any]:
        """获取连接参数"""
        return {
            "endpoint_url": self.endpoint,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "region_name": self.region,
            "use_ssl": self.use_ssl,
            "verify": self.verify_ssl,
            "config": {
                "addressing_style": self.addressing_style,
                "max_pool_connections": self.max_pool_connections,
                "connect_timeout": self.timeout,
                "read_timeout": self.timeout,
                "retries": {"max_attempts": self.retries},
            }
        }


class StorageConfig(BaseModel):
    """统一存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 存储类型
    type: StorageType = Field(default=StorageType.LOCAL, description="存储类型")

    # 具体存储配置（根据type选择）
    local: Optional[LocalStorageConfig] = Field(default=None, description="本地存储配置")
    minio: Optional[MinIOStorageConfig] = Field(default=None, description="MinIO存储配置")
    s3: Optional[S3StorageConfig] = Field(default=None, description="S3存储配置")

    # 通用配置
    default_ttl: int = Field(default=86400, description="默认过期时间（秒）")
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    cache_size: int = Field(default=100, description="缓存大小（对象数量）")
    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")
    enable_compression: bool = Field(default=False, description="是否启用压缩")
    compression_level: int = Field(default=6, description="压缩级别 (1-9)")
    enable_encryption: bool = Field(default=False, description="是否启用加密")
    encryption_key: Optional[str] = Field(default=None, description="加密密钥")
    max_file_size: int = Field(default=1024 * 1024 * 1024, description="最大文件大小（字节）")
    allowed_extensions: list[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        description="允许的文件扩展名"
    )
    chunk_size: int = Field(default=1024 * 1024 * 8, description="分块大小（字节）")
    multipart_threshold: int = Field(default=1024 * 1024 * 100, description="分片上传阈值（字节）")

    @field_validator("compression_level")
    def validate_compression_level(cls, v):
        """验证压缩级别"""
        if v < 1 or v > 9:
            raise ValueError("压缩级别必须在 1 到 9 之间")
        return v

    @field_validator("max_file_size")
    def validate_max_file_size(cls, v):
        """验证最大文件大小"""
        if v < 1024 * 1024:  # 小于1MB
            raise ValueError("文件大小不能小于1MB")
        return v

    @property
    def active_config(self) -> Union[LocalStorageConfig, MinIOStorageConfig, S3StorageConfig]:
        """获取当前激活的存储配置"""
        if self.type == StorageType.LOCAL:
            if self.local is None:
                raise ValueError("本地存储配置未设置")
            return self.local
        elif self.type == StorageType.MINIO:
            if self.minio is None:
                raise ValueError("MinIO存储配置未设置")
            return self.minio
        elif self.type == StorageType.S3:
            if self.s3 is None:
                raise ValueError("S3存储配置未设置")
            return self.s3
        else:
            raise ValueError(f"不支持的存储类型: {self.type}")

    @property
    def models_path(self) -> str:
        """获取模型存储路径"""
        return self.active_config.models_path

    @property
    def models_path_local(self) -> Path:
        """获取本地缓存路径"""
        if self.type == StorageType.LOCAL:
            return self.active_config.models_path
        else:
            # 为远程存储创建本地缓存目录
            cache_dir = Path("/tmp/datamind/models_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            return cache_dir

    def get_client_config(self) -> Dict[str, Any]:
        """获取客户端配置"""
        config = {
            "type": self.type.value,
            "default_ttl": self.default_ttl,
            "enable_cache": self.enable_cache,
            "cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "enable_compression": self.enable_compression,
            "compression_level": self.compression_level,
            "enable_encryption": self.enable_encryption,
            "encryption_key": self.encryption_key,
            "max_file_size": self.max_file_size,
            "allowed_extensions": self.allowed_extensions,
            "chunk_size": self.chunk_size,
            "multipart_threshold": self.multipart_threshold,
        }

        # 添加存储特定的连接参数
        if hasattr(self.active_config, 'connection_params'):
            config.update(self.active_config.connection_params)

        return config

    def ensure_directories(self):
        """确保必要的目录存在"""
        if self.type == StorageType.LOCAL:
            self.active_config.ensure_directories()
        else:
            # 确保缓存目录存在
            self.models_path_local.mkdir(parents=True, exist_ok=True)
        return self

    def dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.type.value,
            "models_path": self.models_path,
            "models_path_local": str(self.models_path_local),
            "config": self.get_client_config(),
        }

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.dict(), indent=2, default=str)


class StorageConfigFactory:
    """存储配置工厂类"""

    @staticmethod
    def create_from_settings(settings) -> StorageConfig:
        """
        从settings创建存储配置

        Args:
            settings: settings模块的实例

        Returns:
            StorageConfig: 存储配置对象
        """
        storage_type = StorageType(settings.STORAGE_TYPE)

        # 创建具体的存储配置
        if storage_type == StorageType.LOCAL:
            local_config = LocalStorageConfig(
                base_path=Path(settings.LOCAL_STORAGE_PATH),
                models_subpath="models"
            )
            minio_config = None
            s3_config = None

        elif storage_type == StorageType.MINIO:
            local_config = None
            minio_config = MinIOStorageConfig(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                bucket=settings.MINIO_BUCKET,
                secure=settings.MINIO_SECURE,
                region=settings.MINIO_REGION,
                location=settings.MINIO_LOCATION,
                models_prefix="models/",
                timeout=settings.STORAGE_TIMEOUT if hasattr(settings, 'STORAGE_TIMEOUT') else 30,
                max_connections=settings.S3_MAX_POOL_CONNECTIONS if hasattr(settings, 'S3_MAX_POOL_CONNECTIONS') else 10
            )
            s3_config = None

        elif storage_type == StorageType.S3:
            local_config = None
            minio_config = None
            s3_config = S3StorageConfig(
                endpoint=settings.S3_ENDPOINT,
                access_key_id=settings.S3_ACCESS_KEY_ID,
                secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                bucket=settings.S3_BUCKET,
                region=settings.S3_REGION,
                prefix=settings.S3_PREFIX,
                acl=settings.S3_ACL,
                use_ssl=settings.S3_USE_SSL,
                verify_ssl=settings.S3_VERIFY_SSL,
                addressing_style=settings.S3_ADDRESSING_STYLE,
                max_pool_connections=settings.S3_MAX_POOL_CONNECTIONS,
                timeout=settings.S3_TIMEOUT,
                retries=settings.S3_RETRIES
            )

        else:
            raise ValueError(f"不支持的存储类型: {storage_type}")

        # 创建统一配置
        storage_config = StorageConfig(
            type=storage_type,
            local=local_config,
            minio=minio_config,
            s3=s3_config,
            default_ttl=settings.STORAGE_DEFAULT_TTL,
            enable_cache=settings.STORAGE_ENABLE_CACHE,
            cache_size=settings.STORAGE_CACHE_SIZE,
            cache_ttl=settings.STORAGE_CACHE_TTL,
            enable_compression=settings.STORAGE_ENABLE_COMPRESSION,
            compression_level=settings.STORAGE_COMPRESSION_LEVEL,
            enable_encryption=settings.STORAGE_ENABLE_ENCRYPTION,
            encryption_key=settings.STORAGE_ENCRYPTION_KEY,
            max_file_size=settings.STORAGE_MAX_FILE_SIZE,
            allowed_extensions=settings.STORAGE_ALLOWED_EXTENSIONS,
            chunk_size=settings.STORAGE_CHUNK_SIZE,
            multipart_threshold=settings.STORAGE_MULTIPART_THRESHOLD
        )

        # 确保目录存在
        storage_config.ensure_directories()

        return storage_config

    @staticmethod
    def create_from_dict(config_dict: Dict[str, Any]) -> StorageConfig:
        """
        从字典创建存储配置

        Args:
            config_dict: 配置字典

        Returns:
            StorageConfig: 存储配置对象
        """
        storage_type = StorageType(config_dict.get("type", "local"))

        # 创建具体的存储配置
        local_config = None
        minio_config = None
        s3_config = None

        if storage_type == StorageType.LOCAL:
            local_config = LocalStorageConfig(
                base_path=Path(config_dict.get("local", {}).get("base_path", "./models")),
                models_subpath=config_dict.get("local", {}).get("models_subpath", "models")
            )
        elif storage_type == StorageType.MINIO:
            minio_config_dict = config_dict.get("minio", {})
            minio_config = MinIOStorageConfig(
                endpoint=minio_config_dict.get("endpoint", "localhost:9000"),
                access_key=minio_config_dict.get("access_key", "minioadmin"),
                secret_key=minio_config_dict.get("secret_key", "minioadmin"),
                bucket=minio_config_dict.get("bucket", "datamind-storage"),
                secure=minio_config_dict.get("secure", False),
                region=minio_config_dict.get("region"),
                location=minio_config_dict.get("location", "us-east-1"),
                models_prefix=minio_config_dict.get("models_prefix", "models/"),
                timeout=minio_config_dict.get("timeout", 30),
                max_connections=minio_config_dict.get("max_connections", 10)
            )
        elif storage_type == StorageType.S3:
            s3_config_dict = config_dict.get("s3", {})
            s3_config = S3StorageConfig(
                endpoint=s3_config_dict.get("endpoint"),
                access_key_id=s3_config_dict.get("access_key_id", ""),
                secret_access_key=s3_config_dict.get("secret_access_key", ""),
                bucket=s3_config_dict.get("bucket", "datamind-storage"),
                region=s3_config_dict.get("region", "us-east-1"),
                prefix=s3_config_dict.get("prefix", "models/"),
                acl=s3_config_dict.get("acl"),
                use_ssl=s3_config_dict.get("use_ssl", True),
                verify_ssl=s3_config_dict.get("verify_ssl", True),
                addressing_style=s3_config_dict.get("addressing_style", "auto"),
                max_pool_connections=s3_config_dict.get("max_pool_connections", 10),
                timeout=s3_config_dict.get("timeout", 30),
                retries=s3_config_dict.get("retries", 3)
            )

        # 创建统一配置
        storage_config = StorageConfig(
            type=storage_type,
            local=local_config,
            minio=minio_config,
            s3=s3_config,
            default_ttl=config_dict.get("default_ttl", 86400),
            enable_cache=config_dict.get("enable_cache", True),
            cache_size=config_dict.get("cache_size", 100),
            cache_ttl=config_dict.get("cache_ttl", 300),
            enable_compression=config_dict.get("enable_compression", False),
            compression_level=config_dict.get("compression_level", 6),
            enable_encryption=config_dict.get("enable_encryption", False),
            encryption_key=config_dict.get("encryption_key"),
            max_file_size=config_dict.get("max_file_size", 1024 * 1024 * 1024),
            allowed_extensions=config_dict.get("allowed_extensions",
                                               [".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin",
                                                ".joblib", ".npy"]),
            chunk_size=config_dict.get("chunk_size", 1024 * 1024 * 8),
            multipart_threshold=config_dict.get("multipart_threshold", 1024 * 1024 * 100)
        )

        # 确保目录存在
        storage_config.ensure_directories()

        return storage_config


# 便捷函数
def get_storage_config(settings=None) -> StorageConfig:
    """
    获取存储配置的便捷函数

    Args:
        settings: settings模块的实例（可选）

    Returns:
        StorageConfig: 存储配置对象
    """
    if settings is None:
        from config.settings import settings as app_settings
        settings = app_settings

    return StorageConfigFactory.create_from_settings(settings)


def get_storage_client_config(settings=None) -> Dict[str, Any]:
    """
    获取存储客户端配置的便捷函数

    Args:
        settings: settings模块的实例（可选）

    Returns:
        Dict[str, Any]: 客户端配置字典
    """
    storage_config = get_storage_config(settings)
    return storage_config.get_client_config()


logger = logging.getLogger(__name__)