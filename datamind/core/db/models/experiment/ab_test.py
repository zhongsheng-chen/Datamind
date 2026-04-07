# datamind/core/db/models/experiment/ab_test.py

"""A/B测试配置表定义
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, DateTime, Text, Float, BigInteger,
    Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import TaskType, ABTestStatus


class ABTestConfig(Base):
    """A/B测试配置表"""
    __tablename__ = 'ab_test_configs'
    __table_args__ = (
        Index('idx_abtest_status', 'status'),
        Index('idx_abtest_dates', 'start_date', 'end_date'),
        Index('idx_abtest_task_type', 'task_type'),
        Index('idx_abtest_created_at', 'created_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), unique=True, nullable=False, index=True)
    test_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    task_type = Column(
        SQLEnum(
            TaskType,
            name="task_type_enum",
            values_callable=enum_values
        ),
        nullable=False
    )

    groups = Column(JSONB, nullable=False)

    traffic_allocation = Column(Float, default=100.0)
    assignment_strategy = Column(String(20), default='random')

    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        SQLEnum(
            ABTestStatus,
            name="abtest_status_enum",
            values_callable=enum_values
        ),
        default=ABTestStatus.DRAFT
    )

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    metrics = Column(JSONB, nullable=True)
    winning_criteria = Column(JSONB, nullable=True)

    results = Column(JSONB, nullable=True)
    winning_group = Column(String(50), nullable=True)

    # 关系
    assignments = relationship("ABTestAssignment", back_populates="test")

    def __repr__(self):
        return f"<ABTestConfig(test_id='{self.test_id}', name='{self.test_name}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'test_id': self.test_id,
            'test_name': self.test_name,
            'description': self.description,
            'task_type': self.task_type.value if self.task_type else None,
            'groups': self.groups,
            'traffic_allocation': self.traffic_allocation,
            'assignment_strategy': self.assignment_strategy,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status.value if self.status else None,
            'metrics': self.metrics,
            'winning_criteria': self.winning_criteria,
            'winning_group': self.winning_group,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def is_running(self) -> bool:
        """检查测试是否正在运行"""
        return self.status == ABTestStatus.RUNNING

    def is_active(self, current_time: Optional[datetime] = None) -> bool:
        """检查测试是否在有效期内

        参数:
            current_time: 当前时间，默认为 None（使用 func.now()）

        返回:
            True 表示在有效期内，False 表示已过期或未开始
        """
        if self.status != ABTestStatus.RUNNING:
            return False

        if current_time is None:
            # 需要在数据库会话中调用
            return True

        if current_time < self.start_date:
            return False

        if self.end_date and current_time > self.end_date:
            return False

        return True

    def get_group(self, name: str) -> Optional[Dict[str, Any]]:
        """根据组名获取组配置

        参数:
            name: 组名称

        返回:
            组配置字典，不存在时返回 None
        """
        if not self.groups:
            return None

        for group in self.groups:
            if group.get('name') == name:
                return group

        return None

    def get_model_id(self, group_name: str) -> Optional[str]:
        """获取指定组的模型ID

        参数:
            group_name: 组名称

        返回:
            模型ID，不存在时返回 None
        """
        group = self.get_group(group_name)
        return group.get('model_id') if group else None

    def get_all_model_ids(self) -> List[str]:
        """获取所有组的模型ID列表

        返回:
            模型ID列表
        """
        if not self.groups:
            return []

        return [group.get('model_id') for group in self.groups if group.get('model_id')]

    def get_group_names(self) -> List[str]:
        """获取所有组名称列表

        返回:
            组名称列表
        """
        if not self.groups:
            return []

        return [group.get('name') for group in self.groups if group.get('name')]

    def get_traffic_distribution(self) -> Dict[str, float]:
        """获取流量分配映射

        返回:
            组名到权重的映射字典
        """
        if not self.groups:
            return {}

        return {
            group.get('name'): group.get('weight', 0)
            for group in self.groups
            if group.get('name')
        }

    def validate_groups(self) -> bool:
        """验证组配置是否有效

        检查：
            - 组列表不为空
            - 权重总和为100
            - 每个组都有名称和模型ID

        返回:
            True 表示有效，False 表示无效
        """
        if not self.groups:
            return False

        total_weight = 0
        for group in self.groups:
            if not group.get('name'):
                return False
            if not group.get('model_id'):
                return False
            weight = group.get('weight', 0)
            if weight < 0 or weight > 100:
                return False
            total_weight += weight

        return abs(total_weight - 100) < 0.01

    def can_start(self) -> bool:
        """检查测试是否可以启动

        返回:
            True 表示可以启动，False 表示不能启动
        """
        if self.status != ABTestStatus.DRAFT:
            return False

        if not self.validate_groups():
            return False

        return True

    def can_pause(self) -> bool:
        """检查测试是否可以暂停

        返回:
            True 表示可以暂停，False 表示不能暂停
        """
        return self.status == ABTestStatus.RUNNING

    def can_resume(self) -> bool:
        """检查测试是否可以恢复

        返回:
            True 表示可以恢复，False 表示不能恢复
        """
        return self.status == ABTestStatus.PAUSED

    def can_complete(self) -> bool:
        """检查测试是否可以完成

        返回:
            True 表示可以完成，False 表示不能完成
        """
        return self.status in [ABTestStatus.RUNNING, ABTestStatus.PAUSED]

    def can_terminate(self) -> bool:
        """检查测试是否可以终止

        返回:
            True 表示可以终止，False 表示不能终止
        """
        return self.status in [ABTestStatus.DRAFT, ABTestStatus.RUNNING, ABTestStatus.PAUSED]

    def get_duration_days(self) -> Optional[float]:
        """获取测试持续天数

        返回:
            持续天数，如果没有结束日期返回 None
        """
        if not self.end_date:
            return None

        duration = self.end_date - self.start_date
        return duration.total_seconds() / (24 * 3600)

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """检查测试是否已过期

        参数:
            current_time: 当前时间，默认为 None

        返回:
            True 表示已过期，False 表示未过期
        """
        if not self.end_date:
            return False

        if current_time is None:
            return False

        return current_time > self.end_date