# datamind/config/storage_config.py
"""
存储配置模块

用于管理不同存储类型的配置和客户端初始化
"""
import os
import json
import logging
import threading
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union, Literal, ClassVar, List, Callable
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from pydantic import BaseModel, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator, model_validator, ConfigDict

# 基础应用名称
APP_NAME = os.getenv("DATAMIND_APP_NAME", "datamind").lower()

# 设置日志层级
logger = logging.getLogger(f"{APP_NAME}.storage")

BASE_DIR = Path(
    os.getenv(
        "DATAMIND_HOME",
        Path(__file__).resolve().parent.parent
    )
).resolve()


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


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    old_config: 'StorageConfig'
    new_config: 'StorageConfig'
    changes: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class StorageConfig(BaseSettings):
    """存储配置"""

    _env: Optional[str] = PrivateAttr(default=None)
    _base_dir: Optional[Path] = PrivateAttr(default=None)
    _last_modified: Optional[datetime] = PrivateAttr(default=None)
    _config_source: Optional[str] = PrivateAttr(default=None)
    _change_listeners: ClassVar[List[Callable[[ConfigChangeEvent], None]]] = []
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _instance_cache: ClassVar[Dict[str, 'StorageConfig']] = {}

    _local_config: Optional[LocalStorageConfig] = PrivateAttr(default=None)
    _minio_config: Optional[MinIOStorageConfig] = PrivateAttr(default=None)
    _s3_config: Optional[S3StorageConfig] = PrivateAttr(default=None)

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra="ignore"
    )

    # 存储类型
    storage_type: StorageType = Field(
        default=StorageType.LOCAL,
        validation_alias="DATAMIND_STORAGE_TYPE",
        description="存储类型: local/minio/s3"
    )

    # 本地存储配置
    local_storage_path: str = Field(
        default="./models",
        validation_alias="DATAMIND_LOCAL_STORAGE_PATH",
        description="本地存储路径（仅当storage_type=local时使用）"
    )

    # MinIO存储配置
    minio_endpoint: str = Field(
        default="localhost:9000",
        validation_alias="MINIO_ENDPOINT",
        description="MinIO服务端点"
    )
    minio_access_key: str = Field(
        default="",
        validation_alias="MINIO_ACCESS_KEY",
        description="MinIO访问密钥"
    )
    minio_secret_key: str = Field(
        default="",
        validation_alias="MINIO_SECRET_KEY",
        description="MinIO秘密密钥"
    )
    minio_bucket: str = Field(
        default="datamind-storage",
        validation_alias="MINIO_BUCKET",
        description="MinIO存储桶名称"
    )
    minio_secure: bool = Field(
        default=False,
        validation_alias="MINIO_SECURE",
        description="是否使用HTTPS连接MinIO"
    )
    minio_region: Optional[str] = Field(
        default=None,
        validation_alias="MINIO_REGION",
        description="MinIO区域"
    )
    minio_location: str = Field(
        default="us-east-1",
        validation_alias="MINIO_LOCATION",
        description="MinIO存储桶位置"
    )

    # AWS S3存储配置
    s3_endpoint: Optional[str] = Field(
        default=None,
        validation_alias="S3_ENDPOINT",
        description="S3自定义端点（用于兼容S3的其他服务，如OSS、COS等）"
    )
    s3_access_key_id: str = Field(
        default="",
        validation_alias="AWS_ACCESS_KEY_ID",
        description="AWS访问密钥ID"
    )
    s3_secret_access_key: str = Field(
        default="",
        validation_alias="AWS_SECRET_ACCESS_KEY",
        description="AWS秘密访问密钥"
    )
    s3_bucket: str = Field(
        default="datamind-storage",
        validation_alias="S3_BUCKET",
        description="S3存储桶名称"
    )
    s3_region: str = Field(
        default="us-east-1",
        validation_alias="AWS_REGION",
        description="AWS区域"
    )
    s3_prefix: str = Field(
        default="models/",
        validation_alias="S3_PREFIX",
        description="S3对象键前缀"
    )
    s3_acl: Optional[str] = Field(
        default=None,
        validation_alias="S3_ACL",
        description="S3对象ACL（如 'private', 'public-read'）"
    )
    s3_use_ssl: bool = Field(
        default=True,
        validation_alias="S3_USE_SSL",
        description="是否使用SSL连接S3"
    )
    s3_verify_ssl: bool = Field(
        default=True,
        validation_alias="S3_VERIFY_SSL",
        description="是否验证SSL证书"
    )
    s3_addressing_style: Literal["auto", "virtual", "path"] = Field(
        default="auto",
        validation_alias="S3_ADDRESSING_STYLE",
        description="S3寻址风格"
    )
    s3_max_pool_connections: int = Field(
        default=10,
        validation_alias="S3_MAX_POOL_CONNECTIONS",
        description="S3连接池最大连接数"
    )
    s3_timeout: int = Field(
        default=30,
        validation_alias="S3_TIMEOUT",
        description="S3请求超时时间（秒）"
    )
    s3_retries: int = Field(
        default=3,
        validation_alias="S3_RETRIES",
        description="S3请求重试次数"
    )

    # 存储通用配置
    storage_default_ttl: int = Field(
        default=86400,
        validation_alias="DATAMIND_STORAGE_DEFAULT_TTL",
        description="存储对象默认过期时间（秒）"
    )
    storage_enable_cache: bool = Field(
        default=True,
        validation_alias="DATAMIND_STORAGE_ENABLE_CACHE",
        description="是否启用存储缓存"
    )
    storage_cache_size: int = Field(
        default=100,
        validation_alias="DATAMIND_STORAGE_CACHE_SIZE",
        description="存储缓存大小（对象数量）"
    )
    storage_cache_ttl: int = Field(
        default=300,
        validation_alias="DATAMIND_STORAGE_CACHE_TTL",
        description="存储缓存过期时间（秒）"
    )
    storage_enable_compression: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_COMPRESSION",
        description="是否启用存储压缩"
    )
    storage_compression_level: int = Field(
        default=6,
        validation_alias="DATAMIND_STORAGE_COMPRESSION_LEVEL",
        description="存储压缩级别 (1-9)"
    )
    storage_enable_encryption: bool = Field(
        default=False,
        validation_alias="DATAMIND_STORAGE_ENABLE_ENCRYPTION",
        description="是否启用存储加密"
    )
    storage_encryption_key: Optional[str] = Field(
        default=None,
        validation_alias="DATAMIND_STORAGE_ENCRYPTION_KEY",
        description="存储加密密钥"
    )
    storage_max_file_size: int = Field(
        default=1024 * 1024 * 1024,
        validation_alias="DATAMIND_STORAGE_MAX_FILE_SIZE",
        description="存储最大文件大小（字节）"
    )
    storage_allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        validation_alias="DATAMIND_STORAGE_ALLOWED_EXTENSIONS",
        description="允许存储的文件扩展名"
    )
    storage_chunk_size: int = Field(
        default=1024 * 1024 * 8,
        validation_alias="DATAMIND_STORAGE_CHUNK_SIZE",
        description="存储分块大小（用于大文件上传）"
    )
    storage_multipart_threshold: int = Field(
        default=1024 * 1024 * 100,
        validation_alias="DATAMIND_STORAGE_MULTIPART_THRESHOLD",
        description="启用分片上传的阈值"
    )

    @field_validator("storage_compression_level")
    @classmethod
    def validate_compression_level(cls, v):
        """验证压缩级别"""
        if v < 1 or v > 9:
            raise ValueError("storage_compression_level 必须在 1 到 9 之间")
        return v

    @field_validator("storage_max_file_size")
    @classmethod
    def validate_max_file_size(cls, v):
        """验证最大文件大小"""
        if v < 1024 * 1024:
            raise ValueError("storage_max_file_size 不能小于1MB")
        return v

    @field_validator("storage_allowed_extensions")
    @classmethod
    def validate_allowed_extensions(cls, v):
        """验证允许的文件扩展名"""
        for ext in v:
            if not ext.startswith('.'):
                raise ValueError(f"文件扩展名必须以点开头: {ext}")
        return v

    @model_validator()
    def validate_storage_config(self):
        """验证存储配置的一致性"""
        # 根据存储类型验证必要配置
        if self.storage_type == StorageType.MINIO:
            if not self.minio_endpoint:
                raise ValueError("使用MinIO存储时必须提供 minio_endpoint")
            if not self.minio_access_key:
                raise ValueError("使用MinIO存储时必须提供 minio_access_key")
            if not self.minio_secret_key:
                raise ValueError("使用MinIO存储时必须提供 minio_secret_key")
            if not self.minio_bucket:
                raise ValueError("使用MinIO存储时必须提供 minio_bucket")

        elif self.storage_type == StorageType.S3:
            if not self.s3_access_key_id:
                raise ValueError("使用S3存储时必须提供 s3_access_key_id")
            if not self.s3_secret_access_key:
                raise ValueError("使用S3存储时必须提供 s3_secret_access_key")
            if not self.s3_bucket:
                raise ValueError("使用S3存储时必须提供 s3_bucket")

        # 验证加密配置
        if self.storage_enable_encryption and not self.storage_encryption_key:
            raise ValueError("启用加密时必须提供 storage_encryption_key")

        return self

    @property
    def local_config(self) -> LocalStorageConfig:
        """获取本地存储配置"""
        if self._local_config is None:
            self._local_config = LocalStorageConfig(
                base_path=Path(self.local_storage_path),
                models_subpath="models"
            )
        return self._local_config

    @property
    def minio_config(self) -> MinIOStorageConfig:
        """获取MinIO存储配置"""
        if self._minio_config is None:
            self._minio_config = MinIOStorageConfig(
                endpoint=self.minio_endpoint,
                access_key=self.minio_access_key,
                secret_key=self.minio_secret_key,
                bucket=self.minio_bucket,
                secure=self.minio_secure,
                region=self.minio_region,
                location=self.minio_location,
                models_prefix="models/",
                timeout=self.s3_timeout,
                max_connections=self.s3_max_pool_connections
            )
        return self._minio_config

    @property
    def s3_config(self) -> S3StorageConfig:
        """获取S3存储配置"""
        if self._s3_config is None:
            self._s3_config = S3StorageConfig(
                endpoint=self.s3_endpoint,
                access_key_id=self.s3_access_key_id,
                secret_access_key=self.s3_secret_access_key,
                bucket=self.s3_bucket,
                region=self.s3_region,
                prefix=self.s3_prefix,
                acl=self.s3_acl,
                use_ssl=self.s3_use_ssl,
                verify_ssl=self.s3_verify_ssl,
                addressing_style=self.s3_addressing_style,
                max_pool_connections=self.s3_max_pool_connections,
                timeout=self.s3_timeout,
                retries=self.s3_retries
            )
        return self._s3_config

    @property
    def active_config(self) -> Union[LocalStorageConfig, MinIOStorageConfig, S3StorageConfig]:
        """获取当前激活的存储配置"""
        if self.storage_type == StorageType.LOCAL:
            return self.local_config
        elif self.storage_type == StorageType.MINIO:
            return self.minio_config
        elif self.storage_type == StorageType.S3:
            return self.s3_config
        else:
            raise ValueError(f"不支持的存储类型: {self.storage_type}")

    @property
    def models_path(self) -> str:
        """获取模型存储路径"""
        return self.active_config.models_path

    @property
    def models_path_local(self) -> Path:
        """获取本地缓存路径"""
        if self.storage_type == StorageType.LOCAL:
            return self.active_config.models_path
        else:
            cache_dir = Path("/tmp/datamind/models_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            return cache_dir

    @classmethod
    def get_cached(cls, env: Optional[str] = None, base_dir: Optional[Path] = None) -> 'StorageConfig':
        """获取缓存的配置实例"""
        cache_key = f"{env or 'default'}_{str(base_dir or '')}"

        with cls._cache_lock:
            if cache_key not in cls._instance_cache:
                cls._instance_cache[cache_key] = cls.load(env=env, base_dir=base_dir)
            return cls._instance_cache[cache_key]

    def invalidate_cache(self):
        """使配置缓存失效"""
        with self.__class__._cache_lock:
            cache_key = f"{self._env or 'default'}_{str(self._base_dir or '')}"
            if cache_key in self.__class__._instance_cache:
                del self.__class__._instance_cache[cache_key]

    @classmethod
    def add_change_listener(cls, listener: Callable[[ConfigChangeEvent], None]):
        """添加配置变更监听器"""
        if listener not in cls._change_listeners:
            cls._change_listeners.append(listener)

    @classmethod
    def remove_change_listener(cls, listener: Callable[[ConfigChangeEvent], None]):
        """移除配置变更监听器"""
        if listener in cls._change_listeners:
            cls._change_listeners.remove(listener)

    def _notify_change(self, old_config: 'StorageConfig'):
        """通知配置变更"""
        changes = self._get_changes(old_config)
        if not changes:
            return

        event = ConfigChangeEvent(
            old_config=old_config,
            new_config=self,
            changes=changes
        )

        for listener in self.__class__._change_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"配置变更监听器执行失败: {e}")

    def _get_changes(self, old_config: 'StorageConfig') -> Dict[str, Any]:
        """获取配置变更详情"""
        changes = {}
        old_dict = old_config.model_dump()
        new_dict = self.model_dump()

        for key in set(old_dict.keys()) | set(new_dict.keys()):
            if key.startswith('_'):  # 忽略私有属性
                continue
            old_value = old_dict.get(key)
            new_value = new_dict.get(key)
            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value
                }

        return changes

    def reload(self) -> 'StorageConfig':
        """
        重新加载配置

        Returns:
            StorageConfig: 新的存储配置对象
        """
        old_config = self.model_copy()

        # 实例化新配置
        new_config = self.__class__()
        new_config._env = self._env
        new_config._base_dir = self._base_dir
        new_config._last_modified = datetime.now()
        new_config._config_source = "reloaded"
        new_config.ensure_directories()

        self._notify_change(old_config)
        return new_config

    def get_config_digest(self) -> str:
        """
        获取配置摘要，用于判断配置是否变化
        """
        config_str = self.model_dump_json(
            exclude={
                '_env', '_base_dir', '_last_modified', '_config_source',
                '_local_config', '_minio_config', '_s3_config'
            },
            sort_keys=True
        )
        return hashlib.md5(config_str.encode()).hexdigest()

    def get_config_metadata(self) -> Dict[str, Any]:
        """获取配置元数据"""
        return {
            'env': self._env,
            'base_dir': str(self._base_dir) if self._base_dir else None,
            'last_modified': self._last_modified.isoformat() if self._last_modified else None,
            'source': self._config_source,
            'digest': self.get_config_digest()[:8]
        }

    async def validate_connection(self) -> Dict[str, Any]:
        """验证存储连接是否可用"""
        result = {'success': False, 'details': {}, 'error': None}

        try:
            if self.storage_type == StorageType.LOCAL:
                # 测试本地写入
                test_file = self.models_path_local / '.connection_test'
                test_file.write_text('test')
                test_file.unlink()
                result['success'] = True
                result['details']['path'] = str(self.models_path_local)

            elif self.storage_type == StorageType.MINIO:
                # 测试 MinIO 连接
                from minio import Minio
                client = Minio(**self.active_config.connection_params)
                result['success'] = client.bucket_exists(self.active_config.bucket)
                result['details']['bucket'] = self.active_config.bucket
                result['details']['endpoint'] = self.active_config.endpoint

            elif self.storage_type == StorageType.S3:
                # 测试 S3 连接
                import boto3
                from botocore.config import Config

                config = Config(**self.active_config.connection_params['config'])
                session = boto3.Session(
                    aws_access_key_id=self.active_config.access_key_id,
                    aws_secret_access_key=self.active_config.secret_access_key,
                    region_name=self.active_config.region
                )
                s3 = session.client('s3', config=config,
                                    endpoint_url=self.active_config.endpoint)
                # 尝试列出桶中的对象来验证连接
                s3.list_objects_v2(Bucket=self.active_config.bucket, MaxKeys=1)
                result['success'] = True
                result['details']['bucket'] = self.active_config.bucket
                result['details']['region'] = self.active_config.region

        except ImportError as e:
            result['error'] = f"缺少必要的库: {e}"
        except Exception as e:
            result['error'] = str(e)

        return result

    def validate_all(self) -> Dict[str, Any]:
        """
        全面验证配置，返回验证报告
        """
        report = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {
                'type': self.storage_type.value,
                'models_path': self.models_path,
                'config_digest': self.get_config_digest()[:8],
                'metadata': self.get_config_metadata()
            }
        }

        # 检查目录权限
        try:
            if self.storage_type == StorageType.LOCAL:
                if not os.access(self.models_path_local, os.W_OK):
                    report['errors'].append(f"存储目录不可写: {self.models_path_local}")
                    report['valid'] = False
        except Exception as e:
            report['errors'].append(f"检查存储目录失败: {e}")
            report['valid'] = False

        # 检查加密配置
        if self.storage_enable_encryption and not self.storage_encryption_key:
            report['errors'].append("启用加密时必须提供 storage_encryption_key")
            report['valid'] = False

        # 检查压缩级别
        if self.storage_compression_level < 1 or self.storage_compression_level > 9:
            report['errors'].append("storage_compression_level 必须在 1-9 之间")
            report['valid'] = False

        # 检查文件大小
        if self.storage_max_file_size < 1024 * 1024:
            report['warnings'].append(
                f"storage_max_file_size 设置过小 ({self.storage_max_file_size} < 1MB)"
            )

        return report

    def to_dict(self, exclude_sensitive: bool = True) -> Dict[str, Any]:
        """
        导出配置为字典
        """
        data = self.model_dump(
            exclude={
                '_local_config', '_minio_config', '_s3_config'
            }
        )

        if exclude_sensitive:
            sensitive_keys = [
                'minio_access_key', 'minio_secret_key',
                's3_access_key_id', 's3_secret_access_key',
                'storage_encryption_key'
            ]

            def mask_sensitive_values(d):
                if isinstance(d, dict):
                    for key, value in list(d.items()):
                        if key in sensitive_keys and value:
                            d[key] = '***'
                        elif isinstance(value, (dict, list)):
                            mask_sensitive_values(value)
                elif isinstance(d, list):
                    for item in d:
                        mask_sensitive_values(item)
                return d

            data = mask_sensitive_values(data)

        return data

    def is_equivalent_to(self, other: 'StorageConfig') -> bool:
        """
        判断两个配置是否等效
        """
        return self.get_config_digest() == other.get_config_digest()

    def get_client_config(self) -> Dict[str, Any]:
        """获取客户端配置"""
        config = {
            "type": self.storage_type.value,
            "default_ttl": self.storage_default_ttl,
            "enable_cache": self.storage_enable_cache,
            "cache_size": self.storage_cache_size,
            "cache_ttl": self.storage_cache_ttl,
            "enable_compression": self.storage_enable_compression,
            "compression_level": self.storage_compression_level,
            "enable_encryption": self.storage_enable_encryption,
            "encryption_key": self.storage_encryption_key,
            "max_file_size": self.storage_max_file_size,
            "allowed_extensions": self.storage_allowed_extensions,
            "chunk_size": self.storage_chunk_size,
            "multipart_threshold": self.storage_multipart_threshold,
        }

        if hasattr(self.active_config, 'connection_params'):
            config.update(self.active_config.connection_params)

        return config

    def ensure_directories(self):
        """确保必要的目录存在"""
        if self.storage_type == StorageType.LOCAL:
            self.active_config.ensure_directories()
        else:
            self.models_path_local.mkdir(parents=True, exist_ok=True)
        return self

    def to_readable(self, as_string: bool = False) -> Union[Dict[str, Any], str]:
        """返回人类可读的配置信息

        Args:
            as_string: 是否返回JSON字符串格式

        Returns:
            Union[Dict[str, Any], str]: 字典或JSON字符串
        """
        data = {
            "type": self.storage_type.value,
            "models_path": self.models_path,
            "models_path_local": str(self.models_path_local),
            "config": self.get_client_config(),
            "metadata": self.get_config_metadata()
        }

        if as_string:
            return json.dumps(data, indent=2, default=str, ensure_ascii=False)
        return data

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return self.model_dump_json(
            indent=2,
            exclude={
                '_local_config', '_minio_config', '_s3_config'
            }
        )

    def export_to_file(self, filepath: Union[str, Path], format: Literal['json', 'yaml'] = 'json'):
        """导出配置到文件"""
        filepath = Path(filepath)
        data = self.to_dict(exclude_sensitive=True)

        if format == 'json':
            filepath.write_text(json.dumps(data, indent=2, default=str))
        elif format == 'yaml':
            try:
                import yaml
                filepath.write_text(yaml.dump(data, default_flow_style=False))
            except ImportError:
                raise ImportError("导出YAML格式需要安装PyYAML: pip install pyyaml")
        else:
            raise ValueError(f"不支持的格式: {format}")

        logger.info(f"配置已导出到: {filepath}")

    @classmethod
    def import_from_file(cls, filepath: Union[str, Path]) -> 'StorageConfig':
        """从文件导入配置"""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        if filepath.suffix == '.json':
            data = json.loads(filepath.read_text())
        elif filepath.suffix in ['.yaml', '.yml']:
            try:
                import yaml
                data = yaml.safe_load(filepath.read_text())
            except ImportError:
                raise ImportError("导入YAML格式需要安装PyYAML: pip install pyyaml")
        else:
            raise ValueError(f"不支持的文件格式: {filepath.suffix}")

        # 从字典创建配置实例
        config_dict = {}
        for key, value in data.items():
            if key in cls.model_fields:
                config_dict[key] = value

        config = cls(**config_dict)
        config._config_source = str(filepath)
        config._last_modified = datetime.fromtimestamp(filepath.stat().st_mtime)

        return config


# 便捷函数
def get_storage_config(use_cache: bool = True) -> StorageConfig:
    """
    获取存储配置的便捷函数

    Args:
        use_cache: 是否使用缓存

    Returns:
        StorageConfig: 存储配置对象
    """
    if use_cache:
        return StorageConfig.get_cached()
    else:
        # 直接实例化
        config = StorageConfig()
        config._env = os.getenv("ENV") or os.getenv("ENVIRONMENT") or "production"
        config._base_dir = BASE_DIR
        config._last_modified = datetime.now()
        config._config_source = "environment"
        config.ensure_directories()
        return config


def get_storage_client_config(use_cache: bool = True) -> Dict[str, Any]:
    """
    获取存储客户端配置的便捷函数

    Args:
        settings: settings模块的实例（可选）
        use_cache: 是否使用缓存

    Returns:
        Dict[str, Any]: 客户端配置字典
    """
    storage_config = get_storage_config(use_cache)
    return storage_config.get_client_config()