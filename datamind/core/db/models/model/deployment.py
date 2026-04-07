# datamind/core/db/models/model/deployment.py

"""模型部署表定义
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, DateTime, Boolean, Integer, BigInteger,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import DeploymentEnvironment


class ModelDeployment(Base):
    """模型部署表"""
    __tablename__ = 'model_deployments'
    __table_args__ = (
        Index('idx_deployment_active', 'is_active'),
        Index('idx_deployment_env', 'environment'),
        Index('idx_deployment_model_env', 'model_id', 'environment'),
        Index('idx_deployment_health', 'health_status'),
        Index('idx_deployment_deployed_at', 'deployed_at'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    deployment_id = Column(String(50), unique=True, nullable=False, index=True)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    environment = Column(
        SQLEnum(
            DeploymentEnvironment,
            name="deployment_env_enum",
            values_callable=enum_values
        ),
        nullable=False
    )
    endpoint_url = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)

    deployment_config = Column(JSONB, nullable=True)
    resources = Column(JSONB, nullable=True)

    deployed_by = Column(String(50), nullable=False)
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), nullable=True)
    health_check_details = Column(JSONB, nullable=True)

    traffic_weight = Column(Integer, default=100)
    canary_config = Column(JSONB, nullable=True)

    # 关系
    model = relationship("ModelMetadata", back_populates="deployments")

    def __repr__(self):
        return f"<ModelDeployment(deployment_id='{self.deployment_id}', model='{self.model_id}', env='{self.environment}')>"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'deployment_id': self.deployment_id,
            'model_id': self.model_id,
            'model_version': self.model_version,
            'environment': self.environment.value if self.environment else None,
            'endpoint_url': self.endpoint_url,
            'is_active': self.is_active,
            'deployment_config': self.deployment_config,
            'resources': self.resources,
            'deployed_by': self.deployed_by,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'health_status': self.health_status,
            'health_check_details': self.health_check_details,
            'traffic_weight': self.traffic_weight,
            'canary_config': self.canary_config,
        }

    def is_healthy(self) -> bool:
        """检查部署是否健康

        返回:
            True 表示健康，False 表示不健康
        """
        return self.health_status == 'healthy'

    def is_unhealthy(self) -> bool:
        """检查部署是否不健康

        返回:
            True 表示不健康，False 表示健康或未知
        """
        return self.health_status in ['unhealthy', 'failed']

    def is_degraded(self) -> bool:
        """检查部署是否降级

        返回:
            True 表示降级，False 表示正常或未知
        """
        return self.health_status == 'degraded'

    def can_serve_traffic(self) -> bool:
        """检查是否可以服务流量

        返回:
            True 表示可以，False 表示不可以
        """
        return self.is_active and self.is_healthy()

    def activate(self) -> None:
        """激活部署"""
        self.is_active = True

    def deactivate(self) -> None:
        """停用部署"""
        self.is_active = False

    def update_health_status(
        self,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """更新健康状态

        参数:
            status: 健康状态（healthy/unhealthy/degraded/unknown）
            details: 健康检查详情（可选）
        """
        self.health_status = status
        self.last_health_check = func.now()

        if details:
            if self.health_check_details is None:
                self.health_check_details = {}
            self.health_check_details.update(details)

    def update_traffic_weight(self, weight: int) -> None:
        """更新流量权重

        参数:
            weight: 流量权重（0-100）
        """
        if weight < 0:
            weight = 0
        if weight > 100:
            weight = 100
        self.traffic_weight = weight

        # 权重为0时自动停用
        if weight == 0:
            self.is_active = False
        elif weight > 0 and not self.is_active:
            self.is_active = True

    def get_endpoint(self) -> Optional[str]:
        """获取完整端点URL

        返回:
            端点URL，如果未配置则返回 None
        """
        return self.endpoint_url

    def get_deployment_age_hours(self, current_time: Optional[datetime] = None) -> Optional[float]:
        """获取部署时长（小时）

        参数:
            current_time: 当前时间，默认为 None

        返回:
            部署时长（小时），如果 deployed_at 为空返回 None
        """
        if not self.deployed_at:
            return None

        if current_time is None:
            current_time = datetime.now()

        if self.deployed_at.tzinfo and not current_time.tzinfo:
            from datetime import timezone
            current_time = current_time.replace(tzinfo=timezone.utc)

        duration = current_time - self.deployed_at
        return duration.total_seconds() / 3600

    def is_recent_deployment(self, hours: int = 24) -> bool:
        """检查是否为最近部署

        参数:
            hours: 小时数，默认24小时

        返回:
            True 表示是最近部署，False 表示不是
        """
        age_hours = self.get_deployment_age_hours()
        if age_hours is None:
            return False
        return age_hours <= hours

    @classmethod
    def create(
        cls,
        deployment_id: str,
        model_id: str,
        model_version: str,
        environment: DeploymentEnvironment,
        deployed_by: str,
        endpoint_url: Optional[str] = None,
        deployment_config: Optional[Dict[str, Any]] = None,
        resources: Optional[Dict[str, Any]] = None,
        traffic_weight: int = 100,
        canary_config: Optional[Dict[str, Any]] = None
    ) -> 'ModelDeployment':
        """创建部署实例

        参数:
            deployment_id: 部署ID
            model_id: 模型ID
            model_version: 模型版本
            environment: 部署环境
            deployed_by: 部署人
            endpoint_url: 端点URL（可选）
            deployment_config: 部署配置（可选）
            resources: 资源配置（可选）
            traffic_weight: 流量权重，默认100
            canary_config: 金丝雀配置（可选）

        返回:
            ModelDeployment 实例
        """
        return cls(
            deployment_id=deployment_id,
            model_id=model_id,
            model_version=model_version,
            environment=environment,
            endpoint_url=endpoint_url,
            deployed_by=deployed_by,
            deployment_config=deployment_config,
            resources=resources,
            traffic_weight=traffic_weight,
            canary_config=canary_config,
            is_active=True,
            health_status='unknown'
        )

    def to_summary(self) -> Dict[str, Any]:
        """获取部署摘要（用于监控展示）

        返回:
            部署摘要字典
        """
        return {
            'deployment_id': self.deployment_id,
            'model_id': self.model_id,
            'model_version': self.model_version,
            'environment': self.environment.value if self.environment else None,
            'is_active': self.is_active,
            'health_status': self.health_status,
            'traffic_weight': self.traffic_weight,
            'deployed_at': self.deployed_at.isoformat() if self.deployed_at else None,
            'deployment_age_hours': round(self.get_deployment_age_hours() or 0, 2),
            'can_serve_traffic': self.can_serve_traffic(),
        }

    def get_canary_percentage(self) -> int:
        """获取金丝雀发布百分比

        返回:
            金丝雀百分比，0-100，未配置时返回0
        """
        if not self.canary_config:
            return 0
        return self.canary_config.get('percentage', 0)

    def is_canary(self) -> bool:
        """检查是否为金丝雀部署

        返回:
            True 表示是金丝雀部署，False 表示不是
        """
        return self.get_canary_percentage() > 0

    def can_promote_canary(self) -> bool:
        """检查金丝雀是否可以提升为全量

        返回:
            True 表示可以提升，False 表示不可以
        """
        if not self.is_canary():
            return False

        if not self.is_healthy():
            return False

        # 金丝雀需要运行一段时间才能提升
        age_hours = self.get_deployment_age_hours()
        if age_hours is None:
            return False

        min_runtime_hours = self.canary_config.get('min_runtime_hours', 1) if self.canary_config else 1
        return age_hours >= min_runtime_hours

    def promote_canary(self) -> None:
        """提升金丝雀为全量部署"""
        if self.canary_config:
            self.canary_config['promoted_at'] = func.now()
        self.traffic_weight = 100

    def rollback_canary(self) -> None:
        """回滚金丝雀部署"""
        if self.canary_config:
            self.canary_config['rolled_back_at'] = func.now()
        self.is_active = False
        self.traffic_weight = 0