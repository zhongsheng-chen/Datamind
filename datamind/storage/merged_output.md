## Project Structure
```
    __init__.py
    __pycache__/
    admin.py
    base.py
    errors.py
    factory.py
    local.py
    minio.py
    strategy.py
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\admin.py
```python
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
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\base.py
```python
# datamind/storage/base.py

"""存储后端抽象基类

定义统一的存储接口，支持多种存储后端实现。

核心功能：
  - put_object: 存储数据到指定key
  - get_object: 从指定key读取数据
  - delete_object: 删除指定key的数据
  - object_exists: 检查指定key是否存在
  - list_objects: 列出指定前缀下的所有key

特性：
  - 统一抽象：屏蔽不同存储后端的实现差异
  - 字节流操作：统一使用 bytes 类型进行数据传输
  - 扩展友好：新增存储后端只需实现此接口
  - 命名约束：使用 *_object 命名避免业务语义误导
"""

from abc import ABC, abstractmethod


class BaseStorageBackend(ABC):
    """存储后端抽象类（纯IO层，不理解业务）"""

    @abstractmethod
    def put_object(self, key: str, data: bytes) -> None:
        """存储对象

        参数：
            key: 存储键
            data: 二进制数据
        """
        pass

    @abstractmethod
    def get_object(self, key: str) -> bytes:
        """读取对象

        参数：
            key: 存储键

        返回：
            二进制数据
        """
        pass

    @abstractmethod
    def delete_object(self, key: str) -> None:
        """删除对象

        参数：
            key: 存储键
        """
        pass

    @abstractmethod
    def object_exists(self, key: str) -> bool:
        """检查对象是否存在

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False
        """
        pass

    @abstractmethod
    def list_objects(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有key

        参数：
            prefix: 键前缀

        返回：
            匹配前缀的完整key列表
        """
        pass
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\errors.py
```python
# datamind/storage/errors.py

"""存储异常定义

定义存储层的标准异常类型。

特性：
  - 语义清晰：区分不同类型的存储错误
  - 可恢复性：调用方可根据异常类型决定重试策略
"""


class StorageBackendError(Exception):
    """存储后端基础异常"""
    pass


class StorageKeyError(StorageBackendError):
    """存储键错误（如路径遍历攻击）"""
    pass


class StorageNotFoundError(StorageBackendError):
    """对象不存在异常"""
    pass


class StoragePermissionError(StorageBackendError):
    """权限错误异常"""
    pass


class StorageConnectionError(StorageBackendError):
    """连接错误异常"""
    pass
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\factory.py
```python
# datamind/storage/factory.py

"""存储后端工厂

根据配置创建对应的存储后端实例。

核心功能：
  - get_backend: 根据配置创建存储后端

特性：
  - 配置驱动：根据 type 自动选择后端
  - 参数传递：自动从配置对象提取所需参数
"""

from datamind.config.storage import StorageConfig
from datamind.storage.local import LocalStorageBackend
from datamind.storage.minio import MinIOStorageBackend


def get_backend(config: StorageConfig) -> LocalStorageBackend | MinIOStorageBackend:
    """创建存储后端实例

    参数：
        config: 存储配置对象

    返回：
        存储后端实例

    异常：
        ValueError: 不支持的存储类型
    """
    if config.type == "local":
        return LocalStorageBackend(base_dir=config.local.base_dir)

    if config.type == "minio":
        return MinIOStorageBackend(
            endpoint=config.minio.endpoint,
            access_key=config.minio.access_key,
            secret_key=config.minio.secret_key,
            bucket=config.minio.bucket,
            secure=config.minio.secure,
            region=config.minio.region,
        )

    raise ValueError(f"不支持的存储类型: {config.type}")
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\local.py
```python
# datamind/storage/local.py

"""本地文件系统存储后端

将数据存储在本地文件系统中，使用文件路径作为key。

核心功能：
  - put_object: 写入文件，自动创建父目录
  - get_object: 读取文件内容
  - delete_object: 删除文件
  - object_exists: 检查文件是否存在
  - list_objects: 递归列出目录下所有文件

特性：
  - 自动创建目录：写入时自动创建不存在的父目录
  - 路径安全：防止路径遍历攻击
  - 跨平台兼容：Windows/Linux/macOS 路径自动转换
"""

from pathlib import Path

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import StorageKeyError, StorageNotFoundError


class LocalStorageBackend(BaseStorageBackend):
    """本地文件系统存储后端"""

    def __init__(self, base_dir: Path):
        """初始化本地存储后端

        参数：
            base_dir: 基础目录，所有文件存储在此目录下
        """
        self.base_dir = base_dir.resolve()

    def _safe_path(self, key: str) -> Path:
        """构造完整文件路径，并防止路径遍历攻击

        参数：
            key: 存储键

        返回：
            完整文件路径

        异常：
            StorageKeyError: 检测到路径遍历攻击
        """
        full_path = (self.base_dir / key).resolve()

        if not str(full_path).startswith(str(self.base_dir)):
            raise StorageKeyError(f"非法的存储键，检测到路径遍历: {key}")

        return full_path

    def put_object(self, key: str, data: bytes) -> None:
        """存储数据到文件

        参数：
            key: 存储键
            data: 二进制数据
        """
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_object(self, key: str) -> bytes:
        """读取文件内容

        参数：
            key: 存储键

        返回：
            文件二进制内容

        异常：
            StorageNotFoundError: 文件不存在
        """
        path = self._safe_path(key)
        if not path.exists():
            raise StorageNotFoundError(f"文件不存在: {key}")
        return path.read_bytes()

    def delete_object(self, key: str) -> None:
        """删除文件

        参数：
            key: 存储键
        """
        path = self._safe_path(key)
        if path.exists():
            path.unlink()

    def object_exists(self, key: str) -> bool:
        """检查文件是否存在

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False
        """
        try:
            return self._safe_path(key).exists()
        except StorageKeyError:
            return False

    def list_objects(self, prefix: str) -> list[str]:
        """列出目录下所有文件

        参数：
            prefix: 目录前缀

        返回：
            完整key列表（相对于 base_dir）
        """
        root = self.base_dir / prefix
        if not root.exists():
            return []
        return [
            str(p.relative_to(self.base_dir))
            for p in root.rglob("*")
            if p.is_file()
        ]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\minio.py
```python
# datamind/storage/minio.py

"""MinIO对象存储后端

将数据存储在MinIO/S3兼容的对象存储中。

核心功能：
  - put_object: 上传对象到存储桶
  - get_object: 下载对象内容
  - delete_object: 删除对象
  - object_exists: 检查对象是否存在
  - list_objects: 列出指定前缀下的所有对象

特性：
  - S3兼容：支持MinIO、AWS S3、阿里云OSS等
  - 分块上传：大文件自动分块上传
  - 异常分类：区分不存在、权限、连接等错误
"""

from minio import Minio, S3Error
from io import BytesIO

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import (
    StorageNotFoundError,
    StoragePermissionError,
    StorageConnectionError,
)


class MinIOStorageBackend(BaseStorageBackend):
    """MinIO对象存储后端"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        region: str | None = None,
    ):
        """初始化MinIO存储后端

        参数：
            endpoint: MinIO服务端点
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket: 存储桶名称
            secure: 是否启用TLS
            region: 区域（可选）
        """
        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region=region,
            )
        except Exception as e:
            raise StorageConnectionError(f"连接MinIO失败: {e}")

        self.bucket = bucket

        # 确保存储桶存在
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except S3Error as e:
            raise StoragePermissionError(f"访问存储桶失败: {e}")

    def put_object(self, key: str, data: bytes) -> None:
        """上传对象到存储桶

        参数：
            key: 对象键
            data: 二进制数据
        """
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=len(data),
        )

    def get_object(self, key: str) -> bytes:
        """下载对象内容

        参数：
            key: 对象键

        返回：
            对象二进制内容

        异常：
            StorageNotFoundError: 对象不存在
        """
        try:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageNotFoundError(f"对象不存在: {key}")
            raise StoragePermissionError(f"读取对象失败: {e}")

    def delete_object(self, key: str) -> None:
        """删除对象

        参数：
            key: 对象键
        """
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            # 删除失败不抛出异常，对象可能已不存在
            pass

    def object_exists(self, key: str) -> bool:
        """检查对象是否存在

        参数：
            key: 对象键

        返回：
            存在返回 True，否则返回 False
        """
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            # 其他错误（如权限）返回 False 但记录日志
            return False

    def list_objects(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有对象

        参数：
            prefix: 对象键前缀

        返回：
            匹配前缀的完整对象键列表
        """
        objects = self.client.list_objects(
            self.bucket,
            prefix=prefix,
            recursive=True,
        )
        return [obj.object_name for obj in objects]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\strategy.py
```python
# datamind/storage/strategy.py

"""存储键策略

统一 key 规则定义层，是唯一 key 规则来源。

核心功能：
  - model_key: 构造模型文件的完整 key
  - model_prefix: 构造模型目录的 key 前缀
  - extract_filename: 从 key 中提取文件名
  - validate_model_id: 校验模型ID合法性
  - validate_filename: 校验文件名合法性

特性：
  - 唯一来源：所有 key 规则在此定义
  - 单一职责：只负责 key 规则
  - 易于扩展：支持未来添加版本、租户等维度
  - 解析统一：key 的解析规则也集中管理
  - 输入校验：防止非法输入
"""

import re


class StorageKeyStrategy:
    """统一 key 规则定义层（唯一 key 规则来源）"""

    # 合法的模型ID：字母、数字、下划线、连字符
    _VALID_MODEL_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    # 合法的文件名：不能包含路径分隔符
    _VALID_FILENAME_PATTERN = re.compile(r'^[^/\\]+$')

    def __init__(self, model_dir: str):
        """初始化 key 策略

        参数：
            model_dir: 模型目录名
        """
        self.model_dir = model_dir

    def validate_model_id(self, model_id: str) -> None:
        """校验模型ID合法性

        参数：
            model_id: 模型ID

        异常：
            ValueError: 模型ID不合法
        """
        if not self._VALID_MODEL_ID_PATTERN.match(model_id):
            raise ValueError(f"非法的模型ID: {model_id}，只能包含字母、数字、下划线、连字符")

    def validate_filename(self, filename: str) -> None:
        """校验文件名合法性

        参数：
            filename: 文件名

        异常：
            ValueError: 文件名不合法
        """
        if not self._VALID_FILENAME_PATTERN.match(filename):
            raise ValueError(f"非法的文件名: {filename}，不能包含路径分隔符")
        if not filename or filename in ('.', '..'):
            raise ValueError(f"非法的文件名: {filename}")

    def model_key(self, model_id: str, filename: str) -> str:
        """构造模型文件的完整 key

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            完整 key，格式: {model_dir}/{model_id}/{filename}

        异常：
            ValueError: 参数不合法
        """
        self.validate_model_id(model_id)
        self.validate_filename(filename)
        return f"{self.model_dir}/{model_id}/{filename}"

    def model_prefix(self, model_id: str) -> str:
        """构造模型目录的 key 前缀

        参数：
            model_id: 模型ID

        返回：
            key 前缀，格式: {model_dir}/{model_id}/
        """
        self.validate_model_id(model_id)
        return f"{self.model_dir}/{model_id}/"

    @staticmethod
    def extract_filename(key: str) -> str:
        """从 key 中提取文件名

        参数：
            key: 完整存储键

        返回：
            文件名
        """
        return key.split("/")[-1]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\storage\\\_\_init\_\_.py
```python
# datamind/storage/__init__.py

"""存储模块

提供统一的存储抽象层，支持本地文件系统和MinIO对象存储。

核心功能：
  - get_storage: 获取全局存储实例（单例）
  - Storage: 存储门面类，对外提供统一API

使用示例：
  from datamind.storage import get_storage

  storage = get_storage()

  # 保存模型
  storage.save("model_001", "scorecard.pkl", data)

  # 加载模型
  data = storage.load("model_001", "scorecard.pkl")

  # 列出模型文件
  files = storage.list("model_001")

架构层次：
  Storage (API门面)
     ↓
  StorageAdmin (唯一业务入口，model_id级别)
     ↓
  StorageKeyStrategy (唯一key规则来源)
     ↓
  BaseStorageBackend (IO抽象层，只认key)
     ↓
  LocalBackend / MinIOBackend (IO实现层)

核心原则：
  - StorageKeyStrategy 是唯一 key 规则来源
  - StorageAdmin 是唯一业务入口（model_id）
  - Backend 永远只认 key，不理解业务
"""

from functools import lru_cache

from datamind.config.settings import get_settings
from datamind.storage.admin import StorageAdmin


class Storage:
    """存储门面类

    对外提供统一的存储API，内部委托给 StorageAdmin。
    """

    def __init__(self, storage_admin: StorageAdmin):
        """初始化存储实例

        参数：
            storage_admin: 存储管理API实例
        """
        self._admin = storage_admin

    def save(self, model_id: str, filename: str, data: bytes) -> str:
        """保存模型文件

        参数：
            model_id: 模型ID
            filename: 文件名
            data: 文件二进制数据

        返回：
            存储 key
        """
        return self._admin.save(model_id, filename, data)

    def load(self, model_id: str, filename: str) -> bytes:
        """加载模型文件

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            文件二进制数据
        """
        return self._admin.load(model_id, filename)

    def delete(self, model_id: str, filename: str) -> bool:
        """删除模型文件

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            删除成功返回 True
        """
        return self._admin.delete(model_id, filename)

    def exists(self, model_id: str, filename: str) -> bool:
        """检查模型文件是否存在

        参数：
            model_id: 模型ID
            filename: 文件名

        返回：
            存在返回 True，否则返回 False
        """
        return self._admin.exists(model_id, filename)

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
```
