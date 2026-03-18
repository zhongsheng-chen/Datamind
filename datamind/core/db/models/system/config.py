# Datamind/datamind/core/db/models/system/config.py
"""系统配置表定义

用于存储运行时可以动态修改的配置项，与core/config/中的静态配置互补。
静态配置：启动时加载，修改需重启（数据库连接、API密钥等）
动态配置：运行时修改，立即生效（功能开关、模型参数、限流阈值等）
"""

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
        # 配置键名唯一索引
        Index('idx_config_key', 'config_key', unique=True),
        # 按分类查询
        Index('idx_config_category', 'category'),
        # 多租户查询
        Index('idx_config_tenant', 'tenant_id'),
        # 按更新时间查询
        Index('idx_config_updated_at', 'updated_at'),
        # 联合唯一约束：租户内配置键名唯一
        Index('idx_config_tenant_key', 'tenant_id', 'config_key', unique=True),
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
        """字符串表示"""
        tenant = f", tenant='{self.tenant_id}'" if self.tenant_id else ""
        return f"<SystemConfig(key='{self.config_key}', category='{self.category}', version={self.version}{tenant})>"

    def to_dict(self) -> dict:
        """转换为字典（用于API响应）

        返回:
            包含配置元信息的字典，不包含config_value避免敏感信息泄露
        """
        return {
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

    def is_effective(self, check_time=None) -> bool:
        """检查配置是否在有效期内

        参数:
            check_time: 检查的时间点，默认为当前时间

        返回:
            是否有效：True表示在有效期内，False表示已过期或尚未生效
        """
        from datetime import datetime
        now = check_time or datetime.utcnow()

        if self.effective_from and now < self.effective_from:
            return False

        if self.effective_to and now > self.effective_to:
            return False

        return True

    @classmethod
    def create(cls, config_key: str, config_value, updated_by: str,
               category: str = 'general', description: str = None,
               tenant_id: str = None, **kwargs):
        """创建配置实例的工厂方法

        参数:
            config_key: 配置键名
            config_value: 配置值
            updated_by: 创建人
            category: 配置分类，默认为'general'
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

    def update(self, updated_by: str, **kwargs) -> 'SystemConfig':
        """可更新多个字段

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

        示例:
            >>> # 只更新值
            >>> config.update('admin', config_value=False)

            >>> # 只更新说明
            >>> config.update('admin', description='新说明')

            >>> # 同时更新多个字段
            >>> config.update(
            ...     updated_by='admin',
            ...     config_value=False,
            ...     description='关闭旧功能',
            ...     category='feature',
            ...     effective_from=datetime(2024, 1, 1)
            ... )
        """
        # 可更新字段列表
        updatable_fields = {
            'config_value', 'description', 'category', 'is_encrypted',
            'tenant_id', 'effective_from', 'effective_to'
        }

        updated = False
        for field, value in kwargs.items():
            if field in updatable_fields:
                # 检查值是否有变化
                if getattr(self, field) != value:
                    setattr(self, field, value)
                    updated = True

        if updated:
            self.version += 1
            self.updated_by = updated_by

        return self

    def update_value(self, new_value, updated_by: str) -> 'SystemConfig':
        """仅更新配置值

        参数:
            new_value: 新的配置值
            updated_by: 更新人

        返回:
            更新后的自身实例

        示例:
            >>> config.update_value(False, 'admin')
        """
        return self.update(updated_by=updated_by, config_value=new_value)