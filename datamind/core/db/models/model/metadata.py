# Datamind/datamind/core/db/models/model/metadata.py

"""模型元数据表定义
"""

from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, DateTime, Boolean, Text,
    BigInteger, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import (
    TaskType, ModelType, Framework, ModelStatus
)


class ModelMetadata(Base):
    """模型元数据表"""
    __tablename__ = 'model_metadata'
    __table_args__ = (
        Index('idx_model_status', 'status', 'is_production'),
        Index('idx_model_abtest', 'ab_test_group', 'status'),
        Index('idx_model_name_version', 'model_name', 'model_version', unique=True),
        Index('idx_model_created_at', 'created_at'),
        Index('idx_model_task_type', 'task_type'),
        Index('idx_model_type_framework', 'model_type', 'framework'),
        Index('idx_model_updated_at', 'updated_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)

    task_type = Column(
        SQLEnum(
            TaskType,
            name="task_type_enum",
            values_callable=enum_values
        ),
        nullable=False
    )
    model_type = Column(
        SQLEnum(
            ModelType,
            name="model_type_enum",
            values_callable=enum_values
        ),
        nullable=False
    )
    framework = Column(
        SQLEnum(
            Framework,
            name="framework_enum",
            values_callable=enum_values
        ),
        nullable=False
    )

    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(BigInteger, nullable=False)

    input_features = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=False)

    model_params = Column(JSONB, nullable=True)
    feature_importance = Column(JSONB, nullable=True)
    performance_metrics = Column(JSONB, nullable=True)

    status = Column(
        SQLEnum(
            ModelStatus,
            name="model_status_enum",
            values_callable=enum_values
        ),
        default=ModelStatus.INACTIVE
    )
    is_production = Column(Boolean, default=False)
    ab_test_group = Column(String(50), nullable=True)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)

    tags = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    # 关系
    versions = relationship("ModelVersionHistory", back_populates="model", cascade="all, delete-orphan")
    deployments = relationship("ModelDeployment", back_populates="model", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="model")
    performance_records = relationship("ModelPerformanceMetrics", back_populates="model")
    ab_test_assignments = relationship("ABTestAssignment", back_populates="model")

    def __repr__(self):
        return f"<ModelMetadata(model_id='{self.model_id}', name='{self.model_name}', version='{self.model_version}')>"

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """转换为字典

        参数:
            include_sensitive: 是否包含敏感信息（文件路径等）

        返回:
            模型元数据字典
        """
        data = {
            'model_id': self.model_id,
            'model_name': self.model_name,
            'model_version': self.model_version,
            'task_type': self.task_type.value if self.task_type else None,
            'model_type': self.model_type.value if self.model_type else None,
            'framework': self.framework.value if self.framework else None,
            'file_hash': self.file_hash,
            'file_size': self.file_size,
            'input_features': self.input_features,
            'output_schema': self.output_schema,
            'model_params': self.model_params,
            'feature_importance': self.feature_importance,
            'performance_metrics': self.performance_metrics,
            'status': self.status.value if self.status else None,
            'is_production': self.is_production,
            'ab_test_group': self.ab_test_group,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'deprecated_at': self.deprecated_at.isoformat() if self.deprecated_at else None,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'description': self.description,
            'tags': self.tags,
        }

        if include_sensitive:
            data['file_path'] = self.file_path

        return data

    def is_active(self) -> bool:
        """检查模型是否活跃"""
        return self.status == ModelStatus.ACTIVE

    def is_production_model(self) -> bool:
        """检查是否为生产模型"""
        return self.is_production and self.status == ModelStatus.ACTIVE

    def can_deploy(self) -> bool:
        """检查模型是否可以部署

        返回:
            True 表示可以部署，False 表示不能部署
        """
        return self.status == ModelStatus.ACTIVE

    def can_promote_to_production(self) -> bool:
        """检查模型是否可以提升为生产版本

        返回:
            True 表示可以提升，False 表示不能提升
        """
        return self.status == ModelStatus.ACTIVE and not self.is_production

    def can_deprecate(self) -> bool:
        """检查模型是否可以弃用

        返回:
            True 表示可以弃用，False 表示不能弃用
        """
        return self.status == ModelStatus.ACTIVE

    def can_archive(self) -> bool:
        """检查模型是否可以归档

        返回:
            True 表示可以归档，False 表示不能归档
        """
        return self.status in [ModelStatus.ACTIVE, ModelStatus.DEPRECATED]

    def can_restore(self) -> bool:
        """检查模型是否可以从归档恢复

        返回:
            True 表示可以恢复，False 表示不能恢复
        """
        return self.status == ModelStatus.ARCHIVED

    def activate(self) -> None:
        """激活模型"""
        self.status = ModelStatus.ACTIVE
        self.deprecated_at = None
        self.archived_at = None

    def deactivate(self) -> None:
        """停用模型"""
        self.status = ModelStatus.INACTIVE

    def deprecate(self) -> None:
        """弃用模型"""
        self.status = ModelStatus.DEPRECATED
        self.deprecated_at = func.now()
        self.is_production = False

    def archive(self) -> None:
        """归档模型"""
        self.status = ModelStatus.ARCHIVED
        self.archived_at = func.now()
        self.is_production = False

    def restore(self) -> None:
        """恢复模型（从归档）"""
        self.status = ModelStatus.ACTIVE
        self.archived_at = None

    def promote_to_production(self) -> None:
        """提升为生产模型"""
        self.is_production = True
        self.deployed_at = func.now()

    def demote_from_production(self) -> None:
        """降级为非生产模型"""
        self.is_production = False

    def get_full_name(self) -> str:
        """获取模型完整名称（名称:版本）"""
        return f"{self.model_name}:{self.model_version}"

    def get_unique_key(self) -> str:
        """获取唯一标识键"""
        return f"{self.model_name}:{self.model_version}"

    def update_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """更新性能指标

        参数:
            metrics: 性能指标字典
        """
        if self.performance_metrics is None:
            self.performance_metrics = {}

        self.performance_metrics.update(metrics)
        self.updated_at = func.now()

    def add_tag(self, key: str, value: str) -> None:
        """添加标签

        参数:
            key: 标签键
            value: 标签值
        """
        if self.tags is None:
            self.tags = {}

        self.tags[key] = value

    def remove_tag(self, key: str) -> None:
        """移除标签

        参数:
            key: 标签键
        """
        if self.tags and key in self.tags:
            del self.tags[key]

    def get_tag(self, key: str) -> Optional[str]:
        """获取标签值

        参数:
            key: 标签键

        返回:
            标签值，不存在时返回 None
        """
        if self.tags:
            return self.tags.get(key)
        return None

    def get_feature_names(self) -> List[str]:
        """获取特征名称列表

        返回:
            特征名称列表
        """
        if not self.input_features:
            return []

        if isinstance(self.input_features, list):
            return [f.get('name') if isinstance(f, dict) else f for f in self.input_features]
        elif isinstance(self.input_features, dict):
            return list(self.input_features.keys())

        return []

    def get_feature_count(self) -> int:
        """获取特征数量

        返回:
            特征数量
        """
        return len(self.get_feature_names())

    def validate_file_integrity(self, actual_hash: str) -> bool:
        """验证文件完整性

        参数:
            actual_hash: 实际文件哈希值

        返回:
            True 表示完整，False 表示已损坏
        """
        return self.file_hash == actual_hash

    @classmethod
    def create(
        cls,
        model_id: str,
        model_name: str,
        model_version: str,
        task_type: TaskType,
        model_type: ModelType,
        framework: Framework,
        file_path: str,
        file_hash: str,
        file_size: int,
        input_features: Dict[str, Any],
        output_schema: Dict[str, Any],
        created_by: str,
        description: Optional[str] = None,
        model_params: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> 'ModelMetadata':
        """创建模型元数据实例

        参数:
            model_id: 模型ID
            model_name: 模型名称
            model_version: 模型版本
            task_type: 任务类型
            model_type: 模型类型
            framework: 框架
            file_path: 文件路径
            file_hash: 文件哈希
            file_size: 文件大小
            input_features: 输入特征
            output_schema: 输出模式
            created_by: 创建人
            description: 描述（可选）
            model_params: 模型参数（可选）
            tags: 标签（可选）

        返回:
            ModelMetadata 实例
        """
        return cls(
            model_id=model_id,
            model_name=model_name,
            model_version=model_version,
            task_type=task_type,
            model_type=model_type,
            framework=framework,
            file_path=file_path,
            file_hash=file_hash,
            file_size=file_size,
            input_features=input_features,
            output_schema=output_schema,
            created_by=created_by,
            description=description,
            model_params=model_params,
            tags=tags,
            status=ModelStatus.INACTIVE,
            is_production=False
        )