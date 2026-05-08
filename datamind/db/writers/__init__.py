# datamind/db/writer/__init__.py

"""数据库写入器模块

提供各数据表的统一写入接口。

写入器列表：
  - AuditWriter: 审计日志写入器
  - RequestWriter: 请求记录写入器
  - AssignmentWriter: 分配记录写入器
  - RoutingWriter: 路由规则写入器
  - DeploymentWriter: 模型部署写入器
  - ExperimentWriter: AB实验写入器
  - MetadataWriter: 模型元数据写入器
  - VersionWriter: 模型版本写入器

使用示例：
  from datamind.db.writer import MetadataWriter, VersionWriter

  writer = MetadataWriter(session)
  metadata = writer.create(
      model_id="mdl_a1b2c3d4",
      name="信用评分卡",
      model_type="logistic_regression",
      task_type="scoring",
      framework="sklearn",
  )
"""

from datamind.db.writers.base_writer import BaseWriter
from datamind.db.writers.audit_writer import AuditWriter
from datamind.db.writers.request_writer import RequestWriter
from datamind.db.writers.assignment_writer import AssignmentWriter
from datamind.db.writers.routing_writer import RoutingWriter
from datamind.db.writers.deployment_writer import DeploymentWriter
from datamind.db.writers.experiment_writer import ExperimentWriter
from datamind.db.writers.metadata_writer import MetadataWriter
from datamind.db.writers.version_writer import VersionWriter

__all__ = [
    "BaseWriter",
    "AuditWriter",
    "RequestWriter",
    "AssignmentWriter",
    "RoutingWriter",
    "DeploymentWriter",
    "ExperimentWriter",
    "MetadataWriter",
    "VersionWriter",
]