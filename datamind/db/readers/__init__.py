# datamind/db/reader/__init__.py

"""数据库读取器模块

提供各数据表的统一读取接口。

读取器列表：
  - AuditReader: 审计日志读取器
  - RequestReader: 请求记录读取器
  - AssignmentReader: 分配记录读取器
  - RoutingReader: 路由规则读取器
  - DeploymentReader: 模型部署读取器
  - ExperimentReader: AB实验读取器
  - MetadataReader: 模型元数据读取器
  - VersionReader: 模型版本读取器

使用示例：
  from datamind.db.reader import MetadataReader, VersionReader

  reader = MetadataReader(session)
  metadata = await reader.get_model("scorecard")
"""

from datamind.db.readers.base_reader import BaseReader
from datamind.db.readers.audit_reader import AuditReader
from datamind.db.readers.request_reader import RequestReader
from datamind.db.readers.assignment_reader import AssignmentReader
from datamind.db.readers.routing_reader import RoutingReader
from datamind.db.readers.deployment_reader import DeploymentReader
from datamind.db.readers.experiment_reader import ExperimentReader
from datamind.db.readers.metadata_reader import MetadataReader
from datamind.db.readers.version_reader import VersionReader

__all__ = [
    "BaseReader",
    "AuditReader",
    "RequestReader",
    "AssignmentReader",
    "RoutingReader",
    "DeploymentReader",
    "ExperimentReader",
    "MetadataReader",
    "VersionReader",
]