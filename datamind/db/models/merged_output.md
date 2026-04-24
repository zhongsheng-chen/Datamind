## Project Structure
```
    __init__.py
    __pycache__/
    assignments.py
    audit.py
    deployments.py
    experiments.py
    metadata.py
    requests.py
    routing.py
    versions.py
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\assignments.py
```python
# datamind/db/models/assignments.py

"""请求分配表

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """请求分配记录表

    属性：
        request_id: 请求唯一标识
        user_id: 用户标识（可选，用于用户级追踪）
        model_id: 被分配到的模型ID
        version: 被分配到的模型版本
        source: 分配来源（routing/experiment/deployment）
        strategy: 分配策略（random/hash/weighted）
        context: 分配上下文（实验ID、分组、权重等）
        routed_at: 路由分配时间
    """

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_model_id", "model_id"),
        Index("idx_assignments_request_id", "request_id"),
        Index("idx_assignments_user_id", "user_id"),
        Index("idx_assignments_model_version", "model_id", "version"),
        Index("idx_assignments_created_at", "created_at"),
        Index("idx_assignments_source", "source"),
    )

    request_id = Column(String(64), nullable=False)
    user_id = Column(String(64), nullable=True)

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)

    source = Column(String(20), nullable=False)

    strategy = Column(String(20), nullable=True)

    context = Column(JSON, nullable=True)

    routed_at = Column(DateTime, nullable=False)


    def __repr__(self):
        return (
            f"<Assignment("
            f"request_id='{self.request_id}', "
            f"model_id='{self.model_id}', "
            f"version='{self.version}'"
            f")>"
        )
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\audit.py
```python
# datamind/db/models/audit.py

"""审计日志表

记录系统控制平面的所有变更行为，满足金融级审计要求。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表

    属性：
        user_id: 操作者ID
        ip: 操作者IP地址
        action: 操作类型（create/update/delete/deploy/pause/resume/rollback）
        target_type: 目标类型（experiment/deployment/routing/model/version）
        target_id: 目标ID
        before: 变更前数据
        after: 变更后数据
        context: 操作上下文（原因、审批信息等）
        occurred_at: 实际操作发生时间
    """

    __tablename__ = "audit"

    __table_args__ = (
        Index("idx_audit_action", "action"),
        Index("idx_audit_user_id", "user_id"),
        Index("idx_audit_target", "target_type", "target_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
        Index("idx_audit_target_occurred_at", "target_type", "occurred_at"),
        Index("idx_audit_created_at", "created_at"),
    )

    user_id = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)

    action = Column(String(50), nullable=False)

    target_type = Column(String(50), nullable=False)
    target_id = Column(String(64), nullable=False)

    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)

    context = Column(JSON, nullable=True)

    occurred_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Audit(action='{self.action}', target='{self.target_type}', user_id='{self.user_id}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\deployments.py
```python
# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在生产环境中的生效区间与流量分配。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Float, Index, DateTime

from datamind.db.core import Base, IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表

    用于管理某个模型版本在生产环境中的生效状态和流量分配。

    属性：
        model_id: 所属模型ID
        version: 部署的版本号
        status: 部署状态（active/inactive）
        traffic_ratio: 流量占比（0.0 ~ 1.0）
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        deployed_by: 部署操作人
        description: 部署说明
    """

    __tablename__ = "deployments"

    __table_args__ = (
        Index("idx_deployments_model_id", "model_id"),
        Index("idx_deployments_version", "model_id", "version"),
        Index("idx_deployments_status", "status"),
        Index("idx_deployments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("uk_deployments_model_id_version", "model_id", "version", unique=True),
        CheckConstraint("traffic_ratio >= 0 AND traffic_ratio <= 1"),
    )

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False, default="active")

    traffic_ratio = Column(Float, nullable=False, default=1.0)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    deployed_by = Column(String(50))
    description = Column(String(255))

    def __repr__(self):
        return (
            f"<Deployment("
            f"model_id='{self.model_id}', "
            f"version='{self.version}', "
            f"status='{self.status}', "
            f"traffic={self.traffic_ratio}"
            f")>"
        )
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\experiments.py
```python
# datamind/db/models/experiments.py

"""实验表

定义模型版本之间的 AB 实验或灰度策略配置。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Experiment(Base, IdMixin, TimestampMixin):
    """实验表

    属性：
        experiment_id: 实验唯一标识
        model_id: 所属模型ID
        name: 实验名称
        description: 实验描述
        status: 实验状态（running/paused/completed）
        config: 实验配置（策略、变体、权重等）
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        created_by: 创建人
    """

    __tablename__ = "experiments"

    __table_args__ = (
        Index("idx_experiments_model_id", "model_id"),
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created_at", "created_at"),
        Index("idx_experiments_effective_time", "effective_from", "effective_to"),
        Index("idx_experiments_model_id_status", "model_id", "status"),
    )

    experiment_id = Column(String(64), nullable=False, unique=True)
    model_id = Column(String(64), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    status = Column(String(20), nullable=False, default="running")

    config = Column(JSON, nullable=True)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    created_by = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<Experiment(experiment_id='{self.experiment_id}', name='{self.name}', status='{self.status}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\metadata.py
```python
# datamind/db/models/metadata.py

"""模型元数据模型

存储模型的元数据信息，包括模型标识、类型、Schema和状态等。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表

    属性：
        model_id: 模型唯一标识
        name: 模型名称
        description: 模型描述
        model_type: 模型类型（logistic_regression/decision_tree/random_forest/xgboost/lightgbm/catboost）
        task_type: 任务类型（classification/scoring）
        framework: 框架（sklearn/xgboost/lightgbm/torch/tensorflow/onnx/catboost）
        input_schema: 输入Schema
        output_schema: 输出Schema
        status: 状态（active/inactive/deprecated/archived）
        created_by: 创建人
        updated_by: 更新人
    """

    __tablename__ = "metadata"

    __table_args__ = (
        Index("idx_metadata_name", "name"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_framework", "framework"),
        Index("idx_metadata_model_type", "model_type"),
        Index("idx_metadata_task_type", "task_type"),
        Index("idx_metadata_created_at", "created_at"),
    )

    model_id = Column(String(64), nullable=False, unique=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    model_type = Column(String(50), nullable=False)
    task_type = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    input_schema = Column(JSONB)
    output_schema = Column(JSONB)

    status = Column(String(20), nullable=False, default="active")

    created_by = Column(String(50))
    updated_by = Column(String(50))

    def __repr__(self):
        return f"<Metadata(name='{self.name}', model_id='{self.model_id}', model_type='{self.model_type}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\requests.py
```python
# datamind/db/models/requests.py

"""请求表

记录进入系统的原始请求信息，用于请求追踪和性能分析。
"""

from sqlalchemy import Column, String, Index, JSON, Float

from datamind.db.core import Base, IdMixin, TimestampMixin


class Request(Base, IdMixin, TimestampMixin):
    """请求表

    属性：
        request_id: 请求唯一标识
        user_id: 用户标识（可选）
        model_id: 目标模型ID
        payload: 请求输入（特征/参数）
        source: 请求来源（api/batch/stream）
        ip: 客户端IP地址
        latency_ms: 处理耗时（毫秒）
    """

    __tablename__ = "requests"

    __table_args__ = (
        Index("idx_requests_request_id", "request_id"),
        Index("idx_requests_user_id", "user_id"),
        Index("idx_requests_model_id", "model_id"),
        Index("idx_requests_created_at", "created_at"),
        Index("idx_requests_source", "source"),
    )

    request_id = Column(String(64), nullable=False, unique=True)
    user_id = Column(String(64), nullable=True)

    model_id = Column(String(64), nullable=False)

    payload = Column(JSON, nullable=True)

    source = Column(String(50), nullable=True)
    ip = Column(String(64), nullable=True)

    latency_ms = Column(Float, nullable=True)

    def __repr__(self):
        return f"<Request(request_id='{self.request_id}', model_id='{self.model_id}', source='{self.source}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\routing.py
```python
# datamind/db/models/routing.py

"""模型路由表

定义模型版本的流量分配规则，支持多种路由策略。
"""

from sqlalchemy import Column, String, JSON, Index

from datamind.db.core import Base, IdMixin, TimestampMixin


class Routing(Base, IdMixin, TimestampMixin):
    """模型路由表

    属性：
        model_id: 所属模型ID
        strategy: 路由策略（RANDOM/CONSISTENT/BUCKET/ROUND_ROBIN/WEIGHTED）
        config: 策略配置（权重、桶范围等）
        enabled: 是否启用（true/false）
    """

    __tablename__ = "routing"

    __table_args__ = (
        Index("idx_routing_model_id", "model_id"),
        Index("idx_routing_strategy", "strategy"),
        Index("idx_routing_enabled", "enabled"),
    )

    model_id = Column(String(64), nullable=False)

    strategy = Column(String(20), nullable=False)

    config = Column(JSON, nullable=True)

    enabled = Column(String(10), nullable=False, default="true")

    def __repr__(self):
        return f"<Routing(model_id='{self.model_id}', strategy='{self.strategy}', enabled='{self.enabled}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\versions.py
```python
# datamind/db/models/versions.py

"""模型版本模型

存储模型版本信息，每次模型注册生成一条记录。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表

    属性：
        model_id: 所属模型ID
        version: 版本号
        bento_tag: BentoML 标签（格式：模型名:版本）
        model_path: 模型文件存储路径
        params: 模型参数
        metrics: 模型评估指标
        description: 版本说明
        created_by: 创建人
    """

    __tablename__ = "versions"

    __table_args__ = (
        Index("idx_versions_model_id", "model_id"),
        Index("idx_versions_bento_tag", "bento_tag"),
        Index("idx_versions_created_at", "created_at"),
        Index("uk_versions_model_id_version", "model_id", "version", unique=True),
    )

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)

    bento_tag = Column(String(100), nullable=False)

    model_path = Column(String(255), nullable=False)

    params = Column(JSONB)
    metrics = Column(JSONB)

    description = Column(Text)
    created_by = Column(String(50))

    def __repr__(self):
        return f"<Version(model_id='{self.model_id}', version='{self.version}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\\_\_init\_\_.py
```python
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
```
