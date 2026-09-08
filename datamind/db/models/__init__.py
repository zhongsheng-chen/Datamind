"""数据库模型模块

定义所有数据表模型，提供统一的模型导入入口。

核心功能：
  - SystemState: 系统初始化状态表
  - User: 用户表
  - Role: 角色表
  - Grant: 角色授予表
  - Token: 认证令牌表
  - Metadata: 模型元数据表
  - Version: 模型版本表
  - Scorecard: 评分卡详情表
  - Artifact: 模型制品修订表
  - Deployment: 模型部署表
  - Control: 模型运行控制表
  - Runtime: 模型运行表
  - Routing: 路由规则表
  - Experiment: 实验表
  - Variant: 实验分组表
  - Assignment: 实验分配表
  - Request: 请求记录表
  - Decision: 请求决策表
  - Execution: 模型执行表
  - Outcome: 实验结果表
  - Audit: 审计日志表
  - OutboxEvent: 控制台变更事件表

使用示例：
  from datamind.db.models import (
      Control,
      Deployment,
      Metadata,
      Runtime,
      Version,
  )

  model_classes = (
      Metadata,
      Version,
      Deployment,
      Control,
      Runtime,
  )
"""

from datamind.db.models.system import SystemState
from datamind.db.models.users import User
from datamind.db.models.roles import Role
from datamind.db.models.grants import Grant
from datamind.db.models.tokens import Token
from datamind.db.models.metadata import Metadata
from datamind.db.models.versions import Version
from datamind.db.models.scorecards import Scorecard
from datamind.db.models.artifacts import Artifact
from datamind.db.models.deployments import Deployment
from datamind.db.models.controls import Control
from datamind.db.models.runtimes import Runtime
from datamind.db.models.routing import Routing
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.db.models.assignments import Assignment
from datamind.db.models.requests import Request
from datamind.db.models.decisions import Decision
from datamind.db.models.executions import Execution
from datamind.db.models.outcomes import Outcome
from datamind.db.models.audit import Audit
from datamind.db.models.outbox import OutboxEvent


__all__ = [
    "SystemState",
    "User",
    "Role",
    "Grant",
    "Token",
    "Metadata",
    "Version",
    "Scorecard",
    "Artifact",
    "Deployment",
    "Control",
    "Runtime",
    "Routing",
    "Experiment",
    "Variant",
    "Assignment",
    "Request",
    "Decision",
    "Execution",
    "Outcome",
    "Audit",
    "OutboxEvent",
]
