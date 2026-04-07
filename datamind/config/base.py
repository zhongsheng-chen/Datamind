# datamind/config/base.py

"""配置基类模块

提供统一的配置加载机制，支持自定义环境变量前缀和类型转换。

核心功能：
  - from_env: 从环境变量创建配置实例
  - to_env_dict: 转换为环境变量字典（用于调试）
  - reload_from_env: 从环境变量重新加载配置

特性：
  - 自定义前缀：每个配置类可独立设置环境变量前缀
  - 类型转换：自动将字符串转换为 bool、int、float、Enum 等类型
  - JSON 支持：支持从环境变量加载 JSON 格式的复杂配置
  - 热重载支持：支持运行时重新加载配置

使用示例：
    class LoggingConfig(BaseConfig):
        __env_prefix__ = "DATAMIND_LOG_"

        name: str = "datamind"
        level: int = 20

    # 自动读取 DATAMIND_LOG_NAME、DATAMIND_LOG_LEVEL 等环境变量
    config = LoggingConfig.from_env()
"""

import os
import sys
import re
import json
from typing import Dict, Any, Optional, Type, TypeVar, get_origin, get_args, Set, Union
from types import UnionType
from enum import Enum
from pydantic import BaseModel

T = TypeVar('T', bound='BaseConfig')

# 配置模块调试开关
_CONFIG_DEBUG = os.environ.get('DATAMIND_CONFIG_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')

# 遮蔽常量
_MASK_PREFIX_LEN = 3
_MASK_SUFFIX_LEN = 3

# URL 密码匹配正则
_URL_PASSWORD_PATTERN = re.compile(r'://[^:]+:([^@]+)@')

# 默认敏感字段集合
_DEFAULT_SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
    "dsn",
    "jwt_secret_key",
    "encryption_key",
    "secret_key",
    "access_key_id",
    "secret_access_key",
    "credential",
    "auth_token",
    "refresh_token",
}


def _debug(msg: str, *args) -> None:
    """配置模块内部调试输出"""
    if _CONFIG_DEBUG:
        if args:
            print(f"[Config] {msg % args}", file=sys.stderr)
        else:
            print(f"[Config] {msg}", file=sys.stderr)


def _mask_sensitive(
    value: Any,
    field_name: str = "",
    sensitive_keys: Optional[Set[str]] = None,
    mask_char: str = '*'
) -> Any:
    """遮蔽敏感值

    参数:
        value: 原始值
        field_name: 字段名
        sensitive_keys: 敏感字段集合（由调用方提供，已包含默认值）
        mask_char: 遮蔽字符

    返回:
        遮蔽后的值
    """
    if value is None:
        return value

    keys_to_check = sensitive_keys if sensitive_keys is not None else _DEFAULT_SENSITIVE_KEYS

    # 字符串
    if isinstance(value, str):
        if field_name and ('url' in field_name.lower() or 'uri' in field_name.lower()):
            match = _URL_PASSWORD_PATTERN.search(value)
            if match:
                start, end = match.span(1)
                value = value[:start] + '***' + value[end:]

        if field_name:
            name_lower = field_name.lower()
            if any(kw in name_lower for kw in keys_to_check):
                if len(value) <= _MASK_PREFIX_LEN + _MASK_SUFFIX_LEN:
                    return mask_char * len(value)

                middle_len = len(value) - _MASK_PREFIX_LEN - _MASK_SUFFIX_LEN
                return (
                    f"{value[:_MASK_PREFIX_LEN]}"
                    f"{mask_char * middle_len}"
                    f"{value[-_MASK_SUFFIX_LEN:]}"
                )

        return value

    # 字典递归遮蔽
    if isinstance(value, dict):
        return {
            k: _mask_sensitive(v, k, keys_to_check, mask_char)
            for k, v in value.items()
        }

    # 列表、元组、集合递归遮蔽
    if isinstance(value, (list, tuple, set)):
        result = (
            _mask_sensitive(item, field_name, keys_to_check, mask_char)
            for item in value
        )

        if isinstance(value, list):
            return list(result)
        elif isinstance(value, tuple):
            return tuple(result)
        else:
            return set(result)

    return value


class BaseConfig(BaseModel):
    """配置基类

    所有配置类继承此类，获得统一的环境变量加载能力。

    子类可定义：
        __env_prefix__: 环境变量前缀（如 "DATAMIND_LOG_"）
        __enum_mappings__: 字段名到枚举类的映射
        __sensitive_keys__: 敏感字段名称集合（用于遮蔽，会与默认集合合并）
    """

    # 子类需要定义的环境变量前缀
    __env_prefix__: Optional[str] = None

    # 枚举类型映射：字段名 -> 枚举类
    __enum_mappings__: Dict[str, Type[Enum]] = {}

    # 敏感字段名称集合（子类可覆盖，会与默认集合合并）
    __sensitive_keys__: Set[str] = set()

    model_config = {"validate_assignment": True}

    @classmethod
    def from_env(cls: Type[T], **overrides) -> T:
        """从环境变量创建配置实例

        扫描所有以 __env_prefix__ 开头的环境变量，
        自动映射到配置类的字段，并进行类型转换。

        优先使用 Field 的 validation_alias，其次 alias，最后字段名大写。

        参数:
            **overrides: 手动覆盖的配置项（优先级高于环境变量）

        返回:
            配置实例

        示例:
            config = LoggingConfig.from_env()
            config = LoggingConfig.from_env(level=20)
        """
        fields = cls.model_fields
        env_values = {}
        prefix = cls.__env_prefix__

        # 合并敏感字段集合
        sensitive_keys = _DEFAULT_SENSITIVE_KEYS | cls.__sensitive_keys__

        if prefix:
            for field_name, field_info in fields.items():
                alias = field_info.validation_alias
                if isinstance(alias, str):
                    env_key = alias
                elif isinstance(field_info.alias, str):
                    env_key = field_info.alias
                else:
                    env_key = field_name.upper()

                env_name = f"{prefix}{env_key}"
                env_value = os.environ.get(env_name)

                if env_value is not None:
                    converted = cls._convert(env_value, field_info, field_name)
                    if converted is not None:
                        env_values[field_name] = converted
                        masked = _mask_sensitive(converted, field_name, sensitive_keys)
                        _debug("从环境变量加载配置: %s = %s", env_name, masked)

        env_values.update(overrides)
        return cls(**env_values)

    @classmethod
    def _convert(cls, value: str, field_info, field_name: str) -> Any:
        """转换环境变量值到目标类型

        参数:
            value: 环境变量字符串值
            field_info: 字段信息
            field_name: 字段名

        返回:
            转换后的值，如果转换失败则返回原始字符串
        """
        annotation = field_info.annotation

        origin = get_origin(annotation)
        args = get_args(annotation)

        # 处理 Optional 类型
        if origin in (Union, UnionType) and type(None) in args:
            annotation = next(a for a in args if a is not type(None))
            origin = get_origin(annotation)

        # 如果目标类型已经是字符串，直接返回
        if annotation is str:
            return value

        # 处理枚举类型
        if field_name in cls.__enum_mappings__:
            enum_cls = cls.__enum_mappings__[field_name]
            try:
                return enum_cls(value)
            except ValueError:
                # 尝试按枚举成员名查找
                try:
                    return enum_cls[value.upper()]
                except (KeyError, AttributeError):
                    _debug("无效的枚举值: %s 不是 %s 的有效选项，使用默认值", value, enum_cls.__name__)
                    return value

        # 自动枚举识别
        try:
            if isinstance(annotation, type) and issubclass(annotation, Enum):
                try:
                    return annotation(value)
                except ValueError:
                    try:
                        return annotation[value.upper()]
                    except (KeyError, AttributeError):
                        _debug("无效的枚举值: %s 不是 %s 的有效选项，使用默认值", value, annotation.__name__)
                        return value
        except TypeError:
            pass

        # 处理 Dict 类型
        if origin is dict:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                _debug("JSON 解析失败，使用原始字符串: %s", value)
                return value

        # 处理 List 类型
        if origin is list:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return [v.strip() for v in value.split(',')]

        # 基本类型转换
        if annotation is bool:
            if value == "":
                return None
            v = value.lower()
            if v in ('true', '1', 'yes', 'on'):
                return True
            if v in ('false', '0', 'no', 'off'):
                return False
            _debug("布尔值解析失败: %s，使用默认值 False", value)
            return False

        if annotation is int:
            try:
                return int(value)
            except ValueError:
                _debug("整数转换失败: %s，保留原始值让验证器处理", value)
                return value

        if annotation is float:
            try:
                return float(value)
            except ValueError:
                _debug("浮点数转换失败: %s，使用原始字符串", value)
                return value

        return value

    @classmethod
    def reload_from_env(cls: Type[T], **overrides) -> T:
        """从环境变量重新加载配置（用于热重载）

        参数:
            **overrides: 手动覆盖的配置项

        返回:
            新的配置实例

        示例:
            new_config = LoggingConfig.reload_from_env()
            new_config = LoggingConfig.reload_from_env(level=10)
        """
        _debug("从环境变量重新加载配置: %s", cls.__name__)
        return cls.from_env(**overrides)

    def to_env_dict(self) -> Dict[str, str]:
        """转换为环境变量字典（用于调试和导出）

        与 from_env() 保持对称，使用相同的解析逻辑。

        返回:
            环境变量名到值的映射字典

        示例:
            config = LoggingConfig.from_env()
            env_dict = config.to_env_dict()
            # {'DATAMIND_LOG_NAME': 'datamind', 'DATAMIND_LOG_LEVEL': '20'}
        """
        if not self.__env_prefix__:
            return {}

        result = {}
        fields = type(self).model_fields

        for field_name, field_info in fields.items():
            value = getattr(self, field_name)

            alias = field_info.validation_alias
            if isinstance(alias, str):
                env_key = alias
            elif isinstance(field_info.alias, str):
                env_key = field_info.alias
            else:
                env_key = field_name.upper()

            env_name = f"{self.__env_prefix__}{env_key}"

            if isinstance(value, dict):
                result[env_name] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, list):
                result[env_name] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, tuple):
                result[env_name] = json.dumps(list(value), ensure_ascii=False)
            elif isinstance(value, set):
                result[env_name] = json.dumps(sorted(value), ensure_ascii=False)
            elif isinstance(value, Enum):
                result[env_name] = str(value.value)
            else:
                result[env_name] = str(value)

        return result

    def to_summary_dict(self) -> Dict[str, Any]:
        """获取配置摘要（子类应重写此方法）

        返回:
            配置摘要字典
        """
        return self.model_dump()


__all__ = ["BaseConfig", "_mask_sensitive", "_debug"]