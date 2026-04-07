# Datamind/datamind/core/db/models/system/config.py

"""系统配置表定义

用于存储运行时可以动态修改的配置项，与core/config/中的静态配置互补。
静态配置：启动时加载，修改需重启（数据库连接、API密钥等）
动态配置：运行时修改，立即生效（功能开关、模型参数、限流阈值等）
"""

from datetime import datetime
from typing import Optional, Dict, Any, Union
from sqlalchemy import (
    Column, String, DateTime, Text, Boolean, Integer, BigInteger, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from datamind.core.db.base import Base


class SystemConfig(Base):
    """系统配置表

    存储系统级别的动态配置项，支持：
    - 功能开关控制
    - 业务参数动态调整
    - 多租户配置隔离
    - 配置版本追踪

    属性:
        id: 主键ID
        config_key: 配置键名，唯一标识
        config_value: 配置值，JSONB格式支持复杂数据结构
        description: 配置说明
        category: 配置分类（feature/model/api/abtest等）
        is_encrypted: 是否加密（虽然建议敏感信息放在静态配置，但保留此字段）
        version: 配置版本号，用于乐观锁和变更追踪
        tenant_id: 租户ID，支持多租户隔离
        effective_from: 生效开始时间（支持定时配置）
        effective_to: 生效结束时间
        updated_by: 最后更新人
        updated_at: 最后更新时间
        created_at: 创建时间
    """
    __tablename__ = 'system_configs'
    __table_args__ = (
        Index('idx_config_key', 'config_key', unique=True),
        Index('idx_config_category', 'category'),
        Index('idx_config_tenant', 'tenant_id'),
        Index('idx_config_updated_at', 'updated_at'),
        Index('idx_config_tenant_key', 'tenant_id', 'config_key', unique=True),
        Index('idx_config_effective', 'effective_from', 'effective_to'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 配置标识
    config_key = Column(
        String(100),
        nullable=False,
        comment="配置键名，格式：category.name，如：feature.ab_test.enabled"
    )

    # 配置值
    config_value = Column(
        JSONB,
        nullable=False,
        comment="配置值，支持字符串、数字、布尔、数组、对象等任意JSON类型"
    )

    # 配置元信息
    description = Column(
        Text,
        nullable=True,
        comment="配置说明"
    )

    category = Column(
        String(50),
        nullable=False,
        server_default='general',
        comment="配置分类：feature/model/api/abtest/general等"
    )

    # 安全控制（可选，但建议敏感信息放在静态配置）
    is_encrypted = Column(
        Boolean,
        default=False,
        comment="是否加密存储（建议敏感信息放在静态配置）"
    )

    # 版本控制
    version = Column(
        Integer,
        default=1,
        nullable=False,
        comment="配置版本号，每次更新递增"
    )

    # 多租户支持（可选）
    tenant_id = Column(
        String(50),
        nullable=True,
        comment="租户ID，为空表示全局配置"
    )

    # 有效期控制（可选）
    effective_from = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效开始时间，为空表示立即生效"
    )

    effective_to = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="生效结束时间，为空表示永久有效"
    )

    # 审计信息
    updated_by = Column(
        String(50),
        nullable=False,
        comment="最后更新人用户名"
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        server_default=func.now(),
        comment="最后更新时间"
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间"
    )

    def __repr__(self):
        tenant = f", tenant='{self.tenant_id}'" if self.tenant_id else ""
        return f"<SystemConfig(key='{self.config_key}', category='{self.category}', version={self.version}{tenant})>"

    def to_dict(self, include_value: bool = False) -> Dict[str, Any]:
        """转换为字典（用于API响应）

        参数:
            include_value: 是否包含配置值，默认False（避免敏感信息泄露）

        返回:
            配置信息字典
        """
        data = {
            'config_key': self.config_key,
            'category': self.category,
            'description': self.description,
            'is_encrypted': self.is_encrypted,
            'version': self.version,
            'tenant_id': self.tenant_id,
            'effective_from': self.effective_from.isoformat() if self.effective_from else None,
            'effective_to': self.effective_to.isoformat() if self.effective_to else None,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if include_value:
            data['config_value'] = self.config_value

        return data

    def to_summary(self) -> Dict[str, Any]:
        """获取配置摘要（用于监控展示）"""
        return {
            'config_key': self.config_key,
            'category': self.category,
            'version': self.version,
            'tenant_id': self.tenant_id,
            'is_effective': self.is_effective(),
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_effective(self, check_time: Optional[datetime] = None) -> bool:
        """检查配置是否在有效期内

        参数:
            check_time: 检查的时间点，默认为当前时间

        返回:
            True表示在有效期内，False表示已过期或尚未生效
        """
        if check_time is None:
            from datetime import datetime, timezone
            check_time = datetime.now(timezone.utc)

        if self.effective_from and check_time < self.effective_from:
            return False

        if self.effective_to and check_time > self.effective_to:
            return False

        return True

    def is_expired(self, check_time: Optional[datetime] = None) -> bool:
        """检查配置是否已过期

        参数:
            check_time: 检查的时间点，默认为当前时间

        返回:
            True表示已过期，False表示未过期或永不过期
        """
        if self.effective_to is None:
            return False

        if check_time is None:
            from datetime import datetime, timezone
            check_time = datetime.now(timezone.utc)

        return check_time > self.effective_to

    def is_pending(self, check_time: Optional[datetime] = None) -> bool:
        """检查配置是否尚未生效

        参数:
            check_time: 检查的时间点，默认为当前时间

        返回:
            True表示尚未生效，False表示已生效或无生效时间限制
        """
        if self.effective_from is None:
            return False

        if check_time is None:
            from datetime import datetime, timezone
            check_time = datetime.now(timezone.utc)

        return check_time < self.effective_from

    def get_value(self) -> Any:
        """获取配置值"""
        return self.config_value

    def get_value_as_bool(self, default: bool = False) -> bool:
        """获取布尔类型的配置值

        参数:
            default: 默认值

        返回:
            布尔值
        """
        if self.config_value is None:
            return default

        if isinstance(self.config_value, bool):
            return self.config_value

        if isinstance(self.config_value, (int, float)):
            return bool(self.config_value)

        if isinstance(self.config_value, str):
            return self.config_value.lower() in ('true', '1', 'yes', 'on')

        return default

    def get_value_as_int(self, default: int = 0) -> int:
        """获取整数类型的配置值

        参数:
            default: 默认值

        返回:
            整数值
        """
        if self.config_value is None:
            return default

        if isinstance(self.config_value, int):
            return self.config_value

        if isinstance(self.config_value, (float, str)):
            try:
                return int(self.config_value)
            except (ValueError, TypeError):
                return default

        return default

    def get_value_as_float(self, default: float = 0.0) -> float:
        """获取浮点数类型的配置值

        参数:
            default: 默认值

        返回:
            浮点数值
        """
        if self.config_value is None:
            return default

        if isinstance(self.config_value, (int, float)):
            return float(self.config_value)

        if isinstance(self.config_value, str):
            try:
                return float(self.config_value)
            except (ValueError, TypeError):
                return default

        return default

    def get_value_as_str(self, default: str = "") -> str:
        """获取字符串类型的配置值

        参数:
            default: 默认值

        返回:
            字符串值
        """
        if self.config_value is None:
            return default

        if isinstance(self.config_value, str):
            return self.config_value

        return str(self.config_value)

    def get_value_as_list(self, default: Optional[list] = None) -> list:
        """获取列表类型的配置值

        参数:
            default: 默认值

        返回:
            列表值
        """
        if default is None:
            default = []

        if self.config_value is None:
            return default

        if isinstance(self.config_value, list):
            return self.config_value

        return default

    def get_value_as_dict(self, default: Optional[dict] = None) -> dict:
        """获取字典类型的配置值

        参数:
            default: 默认值

        返回:
            字典值
        """
        if default is None:
            default = {}

        if self.config_value is None:
            return default

        if isinstance(self.config_value, dict):
            return self.config_value

        return default

    def get_nested_value(self, path: str, default: Any = None) -> Any:
        """获取嵌套配置值（支持点号分隔的路径）

        参数:
            path: 路径，如 "server.port" 或 "features.ab_test.enabled"
            default: 默认值

        返回:
            嵌套配置值
        """
        if not isinstance(self.config_value, dict):
            return default

        keys = path.split('.')
        value = self.config_value

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def is_feature_flag(self) -> bool:
        """检查是否为功能开关配置"""
        return self.category == 'feature' and isinstance(self.config_value, bool)

    def is_enabled(self) -> bool:
        """检查功能开关是否启用（仅适用于功能开关配置）"""
        if not self.is_feature_flag():
            return False
        return self.get_value_as_bool(False)

    def is_disabled(self) -> bool:
        """检查功能开关是否禁用（仅适用于功能开关配置）"""
        return not self.is_enabled()

    def is_global_config(self) -> bool:
        """检查是否为全局配置（无租户）"""
        return self.tenant_id is None

    def has_tenant(self) -> bool:
        """检查是否有关联租户"""
        return self.tenant_id is not None

    def increment_version(self) -> None:
        """增加版本号"""
        self.version += 1

    def get_version(self) -> int:
        """获取版本号"""
        return self.version

    def update(self, updated_by: str, **kwargs) -> 'SystemConfig':
        """更新多个字段

        参数:
            updated_by: 更新人
            **kwargs: 要更新的字段和值，支持以下字段：
                - config_value: 配置值
                - description: 配置说明
                - category: 配置分类
                - is_encrypted: 是否加密
                - tenant_id: 租户ID
                - effective_from: 生效开始时间
                - effective_to: 生效结束时间

        返回:
            更新后的自身实例
        """
        updatable_fields = {
            'config_value', 'description', 'category', 'is_encrypted',
            'tenant_id', 'effective_from', 'effective_to'
        }

        updated = False
        for field, value in kwargs.items():
            if field in updatable_fields:
                if getattr(self, field) != value:
                    setattr(self, field, value)
                    updated = True

        if updated:
            self.version += 1
            self.updated_by = updated_by

        return self

    def update_value(self, new_value: Any, updated_by: str) -> 'SystemConfig':
        """仅更新配置值

        参数:
            new_value: 新的配置值
            updated_by: 更新人

        返回:
            更新后的自身实例
        """
        return self.update(updated_by=updated_by, config_value=new_value)

    def update_effective_period(
        self,
        effective_from: Optional[datetime],
        effective_to: Optional[datetime],
        updated_by: str
    ) -> 'SystemConfig':
        """更新生效周期

        参数:
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            updated_by: 更新人

        返回:
            更新后的自身实例
        """
        return self.update(
            updated_by=updated_by,
            effective_from=effective_from,
            effective_to=effective_to
        )

    def extend_expiry(self, days: int, updated_by: str) -> 'SystemConfig':
        """延长过期时间

        参数:
            days: 延长的天数
            updated_by: 更新人

        返回:
            更新后的自身实例
        """
        from datetime import datetime, timedelta, timezone

        if self.effective_to is None:
            new_expiry = datetime.now(timezone.utc) + timedelta(days=days)
        else:
            new_expiry = self.effective_to + timedelta(days=days)

        return self.update(
            updated_by=updated_by,
            effective_to=new_expiry
        )

    @classmethod
    def create(
        cls,
        config_key: str,
        config_value: Any,
        updated_by: str,
        category: str = 'general',
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> 'SystemConfig':
        """创建配置实例

        参数:
            config_key: 配置键名
            config_value: 配置值
            updated_by: 创建人
            category: 配置分类，默认为 'general'
            description: 配置说明，可选
            tenant_id: 租户ID，可选
            **kwargs: 其他字段（如effective_from, effective_to等）

        返回:
            创建的SystemConfig实例
        """
        return cls(
            config_key=config_key,
            config_value=config_value,
            category=category,
            description=description,
            tenant_id=tenant_id,
            updated_by=updated_by,
            **kwargs
        )

    @classmethod
    def create_feature_flag(
        cls,
        feature_name: str,
        enabled: bool,
        updated_by: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> 'SystemConfig':
        """创建功能开关配置

        参数:
            feature_name: 功能名称
            enabled: 是否启用
            updated_by: 创建人
            description: 配置说明
            tenant_id: 租户ID
            **kwargs: 其他字段

        返回:
            SystemConfig实例
        """
        config_key = f"feature.{feature_name}"
        return cls.create(
            config_key=config_key,
            config_value=enabled,
            updated_by=updated_by,
            category='feature',
            description=description or f"功能开关: {feature_name}",
            tenant_id=tenant_id,
            **kwargs
        )

    @classmethod
    def create_threshold(
        cls,
        threshold_name: str,
        value: Union[int, float],
        updated_by: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> 'SystemConfig':
        """创建阈值配置

        参数:
            threshold_name: 阈值名称
            value: 阈值数值
            updated_by: 创建人
            description: 配置说明
            tenant_id: 租户ID
            **kwargs: 其他字段

        返回:
            SystemConfig实例
        """
        config_key = f"threshold.{threshold_name}"
        return cls.create(
            config_key=config_key,
            config_value=value,
            updated_by=updated_by,
            category='threshold',
            description=description or f"阈值配置: {threshold_name}",
            tenant_id=tenant_id,
            **kwargs
        )