# datamind/db/models/__init__.py

"""数据库模型模块

定义所有数据表模型，统一导入点。

模型列表：
  - Audit: 审计日志表
  - Request: 请求记录表
  - Assignment: 分配记录表
  - Routing: 路由规则表
  - Deployment: 模型部署表
  - Experiment: AB实验表
  - Metadata: 模型元数据表
  - Version: 模型版本表

使用示例：
  from datamind.db.models import Metadata, Version, Experiment
"""

from datamind.db.models.audit import Audit
from datamind.db.models.requests import Request
from datamind.db.models.assignments import Assignment
from datamind.db.models.routing import Routing
from datamind.db.models.deployments import Deployment
from datamind.db.models.experiments import Experiment
from datamind.db.models.metadata import Metadata
from datamind.db.models.versions import Version

__all__ = [
    "Audit",
    "Request",
    "Assignment",
    "Routing",
    "Deployment",
    "Experiment",
    "Metadata",
    "Version",
]