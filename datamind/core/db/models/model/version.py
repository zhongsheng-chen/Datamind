# datamind/core/db/models/model/version.py

"""模型版本历史表定义
"""

from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, DateTime, Text, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import AuditAction


class ModelVersionHistory(Base):
    """模型版本历史表"""
    __tablename__ = 'model_version_history'
    __table_args__ = (
        Index('idx_history_model_time', 'model_id', 'operation_time'),
        Index('idx_history_operator', 'operator'),
        Index('idx_history_operation', 'operation'),
        Index('idx_history_version', 'model_version'),
        Index('idx_history_time', 'operation_time'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    model_version = Column(String(20), nullable=False, index=True)

    operation = Column(
        SQLEnum(
            AuditAction,
            name="audit_action_enum",
            values_callable=enum_values
        ),
        nullable=False
    )

    operator = Column(String(50), nullable=False, index=True)
    operator_ip = Column(INET, nullable=True)
    operation_time = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    reason = Column(Text, nullable=True)
    metadata_snapshot = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)

    # 关系
    model = relationship("ModelMetadata", back_populates="versions")

    def __repr__(self):
        return f"<ModelVersionHistory(model_id='{self.model_id}', version='{self.model_version}', operation='{self.operation}')>"

    # ==================== 转换方法 ====================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'model_id': self.model_id,
            'model_version': self.model_version,
            'operation': self.operation.value if self.operation else None,
            'operator': self.operator,
            'operator_ip': str(self.operator_ip) if self.operator_ip else None,
            'operation_time': self.operation_time.isoformat() if self.operation_time else None,
            'reason': self.reason,
            'metadata_snapshot': self.metadata_snapshot,
            'details': self.details,
        }

    def to_summary(self) -> Dict[str, Any]:
        """获取历史记录摘要"""
        return {
            'version': self.model_version,
            'operation': self.operation.value if self.operation else None,
            'operator': self.operator,
            'time': self.operation_time.isoformat() if self.operation_time else None,
            'reason': self.reason,
        }

    def to_timeline_entry(self) -> Dict[str, Any]:
        """转换为时间线条目（用于展示版本历史）"""
        return {
            'version': self.model_version,
            'operation': self.operation.value if self.operation else None,
            'operator': self.operator,
            'time': self.operation_time.isoformat() if self.operation_time else None,
            'reason': self.reason,
            'summary': self._get_operation_summary(),
        }

    # ==================== 操作类型检查 ====================

    def is_create_operation(self) -> bool:
        """检查是否为创建操作"""
        return self.operation == AuditAction.MODEL_CREATE

    def is_update_operation(self) -> bool:
        """检查是否为更新操作"""
        return self.operation == AuditAction.MODEL_UPDATE

    def is_delete_operation(self) -> bool:
        """检查是否为删除操作"""
        return self.operation == AuditAction.MODEL_DELETE

    def is_activate_operation(self) -> bool:
        """检查是否为激活操作"""
        return self.operation == AuditAction.MODEL_ACTIVATE

    def is_deactivate_operation(self) -> bool:
        """检查是否为停用操作"""
        return self.operation == AuditAction.MODEL_DEACTIVATE

    def is_deprecate_operation(self) -> bool:
        """检查是否为弃用操作"""
        return self.operation == AuditAction.MODEL_DEPRECATE

    def is_archive_operation(self) -> bool:
        """检查是否为归档操作"""
        return self.operation == AuditAction.MODEL_ARCHIVE

    def is_restore_operation(self) -> bool:
        """检查是否为恢复操作"""
        return self.operation == AuditAction.MODEL_RESTORE

    def is_promote_operation(self) -> bool:
        """检查是否为提升操作"""
        return self.operation == AuditAction.MODEL_PROMOTE

    def is_rollback_operation(self) -> bool:
        """检查是否为回滚操作"""
        return self.operation == AuditAction.MODEL_ROLLBACK

    def is_version_switch_operation(self) -> bool:
        """检查是否为版本切换操作"""
        return self.operation == AuditAction.MODEL_VERSION_SWITCH

    def is_version_add_operation(self) -> bool:
        """检查是否为添加版本操作"""
        return self.operation == AuditAction.MODEL_VERSION_ADD

    def is_version_delete_operation(self) -> bool:
        """检查是否为删除版本操作"""
        return self.operation == AuditAction.MODEL_VERSION_DELETE

    # ==================== 数据访问方法 ====================

    def get_snapshot_value(self, key: str, default: Any = None) -> Any:
        """从快照中获取值

        参数:
            key: 键名
            default: 默认值

        返回:
            快照中的值，不存在时返回默认值
        """
        if not self.metadata_snapshot:
            return default
        return self.metadata_snapshot.get(key, default)

    def get_field_before_change(self, field: str) -> Any:
        """获取变更前的字段值

        参数:
            field: 字段名

        返回:
            变更前的值，不存在时返回 None
        """
        if not self.details:
            return None
        before = self.details.get('before', {})
        return before.get(field)

    def get_field_after_change(self, field: str) -> Any:
        """获取变更后的字段值

        参数:
            field: 字段名

        返回:
            变更后的值，不存在时返回 None
        """
        if not self.details:
            return None
        after = self.details.get('after', {})
        return after.get(field)

    def get_changed_fields(self) -> List[str]:
        """获取变更的字段列表

        返回:
            变更的字段名列表
        """
        if not self.details:
            return []
        changes = self.details.get('changes', {})
        return list(changes.keys()) if isinstance(changes, dict) else []

    def get_previous_version(self) -> Optional[str]:
        """获取上一个版本号

        返回:
            上一个版本号，不存在时返回 None
        """
        return self.get_snapshot_value('previous_version')

    def get_next_version(self) -> Optional[str]:
        """获取下一个版本号

        返回:
            下一个版本号，不存在时返回 None
        """
        return self.get_snapshot_value('next_version')

    def get_old_version(self) -> Optional[str]:
        """获取旧版本号（版本切换时）"""
        if not self.details:
            return None
        return self.details.get('old_version')

    def get_new_version(self) -> Optional[str]:
        """获取新版本号（版本切换时）"""
        if not self.details:
            return None
        return self.details.get('new_version')

    # ==================== 工厂方法 ====================

    @classmethod
    def create(
        cls,
        model_id: str,
        model_version: str,
        operation: AuditAction,
        operator: str,
        reason: Optional[str] = None,
        metadata_snapshot: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None,
        operator_ip: Optional[str] = None
    ) -> 'ModelVersionHistory':
        """创建版本历史记录实例

        参数:
            model_id: 模型ID
            model_version: 模型版本
            operation: 操作类型
            operator: 操作人
            reason: 操作原因（可选）
            metadata_snapshot: 元数据快照（可选）
            details: 操作详情（可选）
            operator_ip: 操作人IP（可选）

        返回:
            ModelVersionHistory 实例
        """
        return cls(
            model_id=model_id,
            model_version=model_version,
            operation=operation,
            operator=operator,
            reason=reason,
            metadata_snapshot=metadata_snapshot,
            details=details,
            operator_ip=operator_ip
        )

    @classmethod
    def from_change(
        cls,
        model_id: str,
        model_version: str,
        operation: AuditAction,
        operator: str,
        before_state: Dict[str, Any],
        after_state: Dict[str, Any],
        reason: Optional[str] = None,
        operator_ip: Optional[str] = None
    ) -> 'ModelVersionHistory':
        """从变更前后状态创建历史记录

        参数:
            model_id: 模型ID
            model_version: 模型版本
            operation: 操作类型
            operator: 操作人
            before_state: 变更前状态
            after_state: 变更后状态
            reason: 操作原因（可选）
            operator_ip: 操作人IP（可选）

        返回:
            ModelVersionHistory 实例
        """
        # 计算变更的字段
        changes = {}
        all_keys = set(before_state.keys()) | set(after_state.keys())

        for key in all_keys:
            before_value = before_state.get(key)
            after_value = after_state.get(key)
            if before_value != after_value:
                changes[key] = {
                    'before': before_value,
                    'after': after_value
                }

        details = {
            'before': before_state,
            'after': after_state,
            'changes': changes
        }

        return cls(
            model_id=model_id,
            model_version=model_version,
            operation=operation,
            operator=operator,
            reason=reason,
            metadata_snapshot=after_state,
            details=details,
            operator_ip=operator_ip
        )

    @classmethod
    def from_version_change(
        cls,
        model_id: str,
        old_version: str,
        new_version: str,
        operator: str,
        reason: Optional[str] = None,
        operator_ip: Optional[str] = None
    ) -> 'ModelVersionHistory':
        """从版本变更创建历史记录

        参数:
            model_id: 模型ID
            old_version: 旧版本号
            new_version: 新版本号
            operator: 操作人
            reason: 操作原因（可选）
            operator_ip: 操作人IP（可选）

        返回:
            ModelVersionHistory 实例
        """
        details = {
            'old_version': old_version,
            'new_version': new_version
        }

        snapshot = {
            'version': new_version,
            'previous_version': old_version
        }

        return cls(
            model_id=model_id,
            model_version=new_version,
            operation=AuditAction.MODEL_VERSION_SWITCH,
            operator=operator,
            reason=reason,
            metadata_snapshot=snapshot,
            details=details,
            operator_ip=operator_ip
        )

    @classmethod
    def from_promote(
        cls,
        model_id: str,
        model_version: str,
        operator: str,
        reason: Optional[str] = None,
        operator_ip: Optional[str] = None
    ) -> 'ModelVersionHistory':
        """从版本提升创建历史记录

        参数:
            model_id: 模型ID
            model_version: 模型版本
            operator: 操作人
            reason: 操作原因（可选）
            operator_ip: 操作人IP（可选）

        返回:
            ModelVersionHistory 实例
        """
        snapshot = {
            'version': model_version,
            'promoted': True
        }

        return cls(
            model_id=model_id,
            model_version=model_version,
            operation=AuditAction.MODEL_PROMOTE,
            operator=operator,
            reason=reason,
            metadata_snapshot=snapshot,
            operator_ip=operator_ip
        )

    @classmethod
    def from_rollback(
        cls,
        model_id: str,
        from_version: str,
        to_version: str,
        operator: str,
        reason: Optional[str] = None,
        operator_ip: Optional[str] = None
    ) -> 'ModelVersionHistory':
        """从版本回滚创建历史记录

        参数:
            model_id: 模型ID
            from_version: 回滚前版本
            to_version: 回滚后版本
            operator: 操作人
            reason: 操作原因（可选）
            operator_ip: 操作人IP（可选）

        返回:
            ModelVersionHistory 实例
        """
        details = {
            'from_version': from_version,
            'to_version': to_version,
            'rollback': True
        }

        snapshot = {
            'version': to_version,
            'rolled_back_from': from_version
        }

        return cls(
            model_id=model_id,
            model_version=to_version,
            operation=AuditAction.MODEL_ROLLBACK,
            operator=operator,
            reason=reason,
            metadata_snapshot=snapshot,
            details=details,
            operator_ip=operator_ip
        )

    # ==================== 私有方法 ====================

    def _get_operation_summary(self) -> str:
        """获取操作摘要描述"""
        summaries = {
            AuditAction.MODEL_CREATE: "创建模型",
            AuditAction.MODEL_UPDATE: "更新模型",
            AuditAction.MODEL_DELETE: "删除模型",
            AuditAction.MODEL_ACTIVATE: "激活模型",
            AuditAction.MODEL_DEACTIVATE: "停用模型",
            AuditAction.MODEL_DEPRECATE: "弃用模型",
            AuditAction.MODEL_ARCHIVE: "归档模型",
            AuditAction.MODEL_RESTORE: "恢复模型",
            AuditAction.MODEL_VERSION_ADD: "添加版本",
            AuditAction.MODEL_VERSION_DELETE: "删除版本",
            AuditAction.MODEL_VERSION_SWITCH: "切换版本",
            AuditAction.MODEL_PROMOTE: "提升为生产版本",
            AuditAction.MODEL_ROLLBACK: "回滚版本",
        }
        return summaries.get(self.operation, f"执行 {self.operation.value} 操作")