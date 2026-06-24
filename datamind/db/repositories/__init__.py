# datamind/db/repositories/__init__.py

"""数据库仓储模块

提供统一的数据仓储接口，封装数据库操作。

仓储列表：
  - BaseRepository: 数据库仓储基类
  - AssignmentRepository: 实验分配仓储
  - AuditRepository: 审计日志仓储
  - DecisionRepository: 请求决策仓储
  - DeploymentRepository: 部署仓储
  - ExperimentRepository: 实验仓储
  - MetadataRepository: 模型元数据仓储
  - OutcomeRepository: 实验结果仓储
  - RequestRepository: 请求仓储
  - RoutingRepository: 路由仓储
  - VariantRepository: 实验分组仓储
  - VersionRepository: 模型版本仓储
"""

from datamind.db.repositories.assignment import AssignmentRepository
from datamind.db.repositories.audit import AuditRepository
from datamind.db.repositories.base import BaseRepository
from datamind.db.repositories.decision import DecisionRepository
from datamind.db.repositories.deployment import DeploymentPatch, DeploymentRepository
from datamind.db.repositories.experiment import ExperimentPatch, ExperimentRepository
from datamind.db.repositories.metadata import MetadataPatch, MetadataRepository
from datamind.db.repositories.outcome import OutcomePatch, OutcomeRepository
from datamind.db.repositories.request import RequestRepository
from datamind.db.repositories.routing import RoutingPatch, RoutingRepository
from datamind.db.repositories.variant import VariantPatch, VariantRepository
from datamind.db.repositories.version import VersionPatch, VersionRepository

__all__ = [
    "BaseRepository",
    "AssignmentRepository",
    "AuditRepository",
    "DecisionRepository",
    "DeploymentPatch",
    "DeploymentRepository",
    "ExperimentPatch",
    "ExperimentRepository",
    "MetadataPatch",
    "MetadataRepository",
    "OutcomePatch",
    "OutcomeRepository",
    "RequestRepository",
    "RoutingPatch",
    "RoutingRepository",
    "VariantPatch",
    "VariantRepository",
    "VersionPatch",
    "VersionRepository",
]