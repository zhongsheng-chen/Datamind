# Datamind/datamind/core/db/models/experiment/assignment.py

"""A/B测试分配记录表定义
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, DateTime, BigInteger,
    ForeignKey, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base


class ABTestAssignment(Base):
    """A/B测试分配记录表"""
    __tablename__ = 'ab_test_assignments'
    __table_args__ = (
        Index('idx_ab_assign_test_user', 'test_id', 'user_id'),
        Index('idx_ab_assign_time', 'assigned_at'),
        Index('idx_ab_assign_model', 'model_id'),
        Index('idx_ab_assign_expires', 'expires_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), ForeignKey('public.ab_test_configs.test_id', ondelete='CASCADE'),
                    nullable=False, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    group_name = Column(String(50), nullable=False)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assignment_hash = Column(String(64), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)

    # 关系
    test = relationship("ABTestConfig", back_populates="assignments")
    model = relationship("ModelMetadata", back_populates="ab_test_assignments")

    def __repr__(self):
        return f"<ABTestAssignment(test='{self.test_id}', user='{self.user_id}', group='{self.group_name}')>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_id': self.test_id,
            'user_id': self.user_id,
            'group_name': self.group_name,
            'model_id': self.model_id,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'assignment_hash': self.assignment_hash,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    def is_valid(self, current_time: Optional[datetime] = None) -> bool:
        """检查分配记录是否有效（未过期）

        参数:
            current_time: 当前时间，默认为 None

        返回:
            True 表示有效，False 表示已过期
        """
        if self.expires_at is None:
            return True

        if current_time is None:
            return True

        return current_time <= self.expires_at

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """检查分配记录是否已过期

        参数:
            current_time: 当前时间，默认为 None

        返回:
            True 表示已过期，False 表示未过期
        """
        if self.expires_at is None:
            return False

        if current_time is None:
            return False

        return current_time > self.expires_at

    def get_remaining_seconds(self, current_time: Optional[datetime] = None) -> int:
        """获取剩余有效秒数

        参数:
            current_time: 当前时间，默认为 None

        返回:
            剩余秒数，-1 表示永不过期，0 表示已过期
        """
        if self.expires_at is None:
            return -1

        if current_time is None:
            current_time = datetime.now()

        if current_time >= self.expires_at:
            return 0

        remaining = self.expires_at - current_time
        return int(remaining.total_seconds())

    @classmethod
    def create(
        cls,
        test_id: str,
        user_id: str,
        group_name: str,
        model_id: str,
        assignment_hash: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> 'ABTestAssignment':
        """创建分配记录实例

        参数:
            test_id: 测试ID
            user_id: 用户ID
            group_name: 组名称
            model_id: 模型ID
            assignment_hash: 分配哈希值（可选）
            expires_at: 过期时间（可选）

        返回:
            ABTestAssignment 实例
        """
        return cls(
            test_id=test_id,
            user_id=user_id,
            group_name=group_name,
            model_id=model_id,
            assignment_hash=assignment_hash,
            expires_at=expires_at
        )

    def update_expiry(self, expires_at: Optional[datetime]) -> None:
        """更新过期时间

        参数:
            expires_at: 新的过期时间，None 表示永不过期
        """
        self.expires_at = expires_at

    def get_cache_key(self) -> str:
        """获取Redis缓存键

        返回:
            缓存键字符串
        """
        return f"ab_test:assignment:{self.test_id}:{self.user_id}"