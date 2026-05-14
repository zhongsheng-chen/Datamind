# datamind/db/repositories/__init__.py

"""数据库仓储模块

提供统一的数据访问接口，封装数据库操作。

仓储列表：
  - BaseRepository: 数据库访问基类
  - AssignmentRepository: 分配记录访问器
  - AuditRepository: 审计日志访问器
  - DeploymentRepository: 部署仓储
  - ExperimentRepository: 实验仓储
  - MetadataRepository: 模型元数据访问器
  - RequestRepository: 请求仓储
  - RoutingRepository: 路由仓储
  - VersionRepository: 模型版本访问器
"""

from datamind.db.repositories.assignment import AssignmentRepository
from datamind.db.repositories.audit import AuditRepository
from datamind.db.repositories.base import BaseRepository
from datamind.db.repositories.deployment import DeploymentPatch, DeploymentRepository
from datamind.db.repositories.experiment import ExperimentPatch, ExperimentRepository
from datamind.db.repositories.metadata import MetadataPatch, MetadataRepository
from datamind.db.repositories.request import RequestRepository
from datamind.db.repositories.routing import RoutingPatch, RoutingRepository
from datamind.db.repositories.version import VersionPatch, VersionRepository

__all__ = [
    "BaseRepository",
    "AssignmentRepository",
    "AuditRepository",
    "DeploymentPatch",
    "DeploymentRepository",
    "ExperimentPatch",
    "ExperimentRepository",
    "MetadataPatch",
    "MetadataRepository",
    "RequestRepository",
    "RoutingPatch",
    "RoutingRepository",
    "VersionPatch",
    "VersionRepository",
]