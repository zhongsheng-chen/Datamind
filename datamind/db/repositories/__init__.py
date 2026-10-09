"""数据库仓储模块.

提供统一的数据仓储入口，
封装数据库模型的查询和变更操作。

核心功能：
  - BaseRepository: 数据库仓储基类
  - SystemStateRepository: 系统初始化状态仓储
  - UserPatch: 用户更新字段
  - UserRepository: 用户仓储
  - RolePatch: 角色更新字段
  - RoleRepository: 角色仓储
  - GrantRepository: 角色授予仓储
  - TokenRepository: 认证令牌仓储
  - MetadataPatch: 模型元数据更新字段
  - MetadataRepository: 模型元数据仓储
  - VersionPatch: 模型版本更新字段
  - VersionRepository: 模型版本仓储
  - ScorecardRepository: 评分卡仓储
  - DeploymentPatch: 部署更新字段
  - DeploymentRepository: 部署仓储
  - DashboardRepository: 管理控制台统计仓储
  - ControlRepository: 模型运行控制仓储
  - RuntimePatch: 模型运行更新字段
  - RuntimeRepository: 模型运行仓储
  - RoutingPatch: 路由更新字段
  - RoutingRepository: 路由仓储
  - ExperimentPatch: 实验更新字段
  - ExperimentRepository: 实验仓储
  - VariantPatch: 实验分组更新字段
  - VariantRepository: 实验分组仓储
  - AssignmentRepository: 实验分配仓储
  - RequestRepository: 请求仓储
  - BatchRepository: 异步预测批次仓储
  - AttemptRepository: 批次执行尝试仓储
  - DecisionRepository: 请求决策仓储
  - ExecutionRepository: 模型执行仓储
  - AuditRepository: 审计日志仓储
  - ArtifactRepository: 模型制品仓储
  - OutboxRepository: 控制台事件仓储

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import (
      MetadataRepository,
      UserRepository,
  )

  async with UnitOfWork() as uow:
      user_repo = UserRepository(
          uow.session
      )
      metadata_repo = MetadataRepository(
          uow.session
      )
"""

from datamind.db.repositories.assignment import AssignmentRepository
from datamind.db.repositories.audit import AuditRepository
from datamind.db.repositories.artifact import ArtifactRepository
from datamind.db.repositories.base import BaseRepository
from datamind.db.repositories.control import ControlRepository
from datamind.db.repositories.decision import DecisionRepository
from datamind.db.repositories.execution import ExecutionRepository
from datamind.db.repositories.deployment import (
    DeploymentPatch,
    DeploymentRepository,
)
from datamind.db.repositories.experiment import (
    ExperimentPatch,
    ExperimentRepository,
)
from datamind.db.repositories.grant import GrantRepository
from datamind.db.repositories.metadata import (
    MetadataPatch,
    MetadataRepository,
)

from datamind.db.repositories.request import RequestRepository
from datamind.db.repositories.batch import BatchRepository
from datamind.db.repositories.attempt import AttemptRepository
from datamind.db.repositories.shard import ShardRepository
from datamind.db.repositories.role import (
    RolePatch,
    RoleRepository,
)
from datamind.db.repositories.routing import (
    RoutingPatch,
    RoutingRepository,
)
from datamind.db.repositories.runtime import (
    RuntimePatch,
    RuntimeRepository,
)
from datamind.db.repositories.dashboard import DashboardRepository
from datamind.db.repositories.outbox import OutboxRepository
from datamind.db.repositories.system import SystemStateRepository
from datamind.db.repositories.token import TokenRepository
from datamind.db.repositories.user import (
    UserPatch,
    UserRepository,
)
from datamind.db.repositories.variant import (
    VariantPatch,
    VariantRepository,
)
from datamind.db.repositories.version import (
    VersionPatch,
    VersionRepository,
)
from datamind.db.repositories.scorecard import ScorecardRepository


__all__ = [
    "BaseRepository",
    "SystemStateRepository",
    "UserPatch",
    "UserRepository",
    "RolePatch",
    "RoleRepository",
    "GrantRepository",
    "TokenRepository",
    "MetadataPatch",
    "MetadataRepository",
    "VersionPatch",
    "VersionRepository",
    "ScorecardRepository",
    "DeploymentPatch",
    "DeploymentRepository",
    "DashboardRepository",
    "ControlRepository",
    "RuntimePatch",
    "RuntimeRepository",
    "RoutingPatch",
    "RoutingRepository",
    "ExperimentPatch",
    "ExperimentRepository",
    "VariantPatch",
    "VariantRepository",
    "AssignmentRepository",
    "RequestRepository",
    "BatchRepository",
    "AttemptRepository",
    "ShardRepository",
    "DecisionRepository",
    "ExecutionRepository",
    "AuditRepository",
    "ArtifactRepository",
    "OutboxRepository",
]
