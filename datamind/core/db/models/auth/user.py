# datamind/core/db/models/auth/user.py

"""用户表定义
"""

from datetime import timedelta
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import UserStatus, UserRole


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_user_email', 'email', unique=True),
        Index('idx_user_username', 'username', unique=True),
        Index('idx_user_status', 'status'),
        Index('idx_user_role', 'role'),
        Index('idx_user_created_at', 'created_at'),
        Index('idx_user_last_login', 'last_login_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True)

    # 基本信息
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    # 个人信息
    full_name = Column(String(100), nullable=True)
    avatar = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)

    # 角色权限
    role = Column(
        SQLEnum(
            UserRole,
            name="user_role_enum",
            values_callable=enum_values
        ),
        default=UserRole.API_USER,
        nullable=False
    )
    permissions = Column(JSONB, default=list, nullable=True)  # 额外权限列表

    # 账户状态
    status = Column(
        SQLEnum(
            UserStatus,
            name="user_status_enum",
            values_callable=enum_values
        ),
        default=UserStatus.ACTIVE,
        nullable=False
    )

    # 安全信息
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(INET, nullable=True)
    last_password_change = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String(100), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    email_verification_token = Column(String(100), nullable=True)
    email_verification_expires = Column(DateTime(timezone=True), nullable=True)

    # 登录统计
    login_attempts = Column(BigInteger, default=0)
    failed_login_attempts = Column(BigInteger, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # API Key 关联
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")

    # 审计日志关联
    audit_logs = relationship(
        "AuditLog",
        foreign_keys="AuditLog.operator",
        primaryjoin="User.username == AuditLog.operator"
    )

    # 扩展元数据
    extra_metadata = Column(JSONB, nullable=True)
    created_by = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User(user_id='{self.user_id}', username='{self.username}', strategy='{self.role}')>"

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """转换为字典

        参数:
            include_sensitive: 是否包含敏感信息（密码哈希、token等）

        返回:
            用户信息字典
        """
        data = {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'avatar': self.avatar,
            'phone': self.phone,
            'strategy': self.role.value if self.role else None,
            'permissions': self.permissions,
            'status': self.status.value if self.status else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_sensitive:
            data.update({
                'password_hash': self.password_hash,
                'password_reset_token': self.password_reset_token,
                'email_verification_token': self.email_verification_token,
            })

        return data

    def is_active(self) -> bool:
        """检查账户是否可用"""
        if self.status != UserStatus.ACTIVE:
            return False
        if self.locked_until and self.locked_until > func.now():
            return False
        return True

    def is_locked(self) -> bool:
        """检查账户是否被锁定"""
        if self.locked_until and self.locked_until > func.now():
            return True
        return False

    def increment_failed_login(self) -> None:
        """增加失败登录计数"""
        self.failed_login_attempts += 1
        # 5次失败后锁定15分钟
        if self.failed_login_attempts >= 5:
            self.locked_until = func.now() + timedelta(minutes=15)
            self.status = UserStatus.LOCKED

    def reset_failed_login(self) -> None:
        """重置失败登录计数"""
        self.failed_login_attempts = 0
        self.locked_until = None

    def record_login(self, ip_address: str = None) -> None:
        """记录登录成功"""
        self.last_login_at = func.now()
        self.last_login_ip = ip_address
        self.login_attempts += 1
        self.reset_failed_login()
        if self.status == UserStatus.LOCKED:
            self.status = UserStatus.ACTIVE


class ApiKey(Base):
    """API密钥表"""
    __tablename__ = 'api_keys'
    __table_args__ = (
        Index('idx_api_key_key', 'key', unique=True),
        Index('idx_api_key_user', 'user_id'),
        Index('idx_api_key_active', 'is_active'),
        Index('idx_api_key_expires', 'expires_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    api_key_id = Column(String(50), unique=True, nullable=False, index=True)

    user_id = Column(String(50), ForeignKey('public.users.user_id', ondelete='CASCADE'),
                     nullable=False, index=True)

    name = Column(String(100), nullable=False)
    key = Column(String(255), unique=True, nullable=False)
    key_prefix = Column(String(10), nullable=True)  # 用于显示，如 "dm_"

    # 权限（覆盖用户权限或额外权限）
    permissions = Column(JSONB, default=list, nullable=True)
    roles = Column(JSONB, default=list, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # 安全限制
    allowed_ips = Column(JSONB, default=list, nullable=True)  # IP白名单
    allowed_origins = Column(JSONB, default=list, nullable=True)  # 域名白名单
    rate_limit = Column(JSONB, nullable=True)  # 自定义限流配置 {"requests": 100, "period": 60}

    # 元数据
    extra_metadata = Column(JSONB, nullable=True)
    description = Column(Text, nullable=True)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<ApiKey(api_key_id='{self.api_key_id}', name='{self.name}', user='{self.user_id}')>"

    def is_valid(self) -> bool:
        """检查API密钥是否有效"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < func.now():
            return False
        return True

    def update_last_used(self) -> None:
        """更新最后使用时间"""
        self.last_used_at = func.now()

    def to_dict(self) -> dict:
        """转换为字典（不含完整密钥）"""
        return {
            'api_key_id': self.api_key_id,
            'name': self.name,
            'key_prefix': self.key_prefix,
            'permissions': self.permissions,
            'roles': self.roles,
            'is_active': self.is_active,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }