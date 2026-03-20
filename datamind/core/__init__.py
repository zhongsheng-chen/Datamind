# Datamind/datamind/core/__init__.py

"""核心模块

包含数据库、领域模型、机器学习、日志、实验等核心功能，是 Datamind 系统的核心业务层。

模块组成：
  - db: 数据库模块，涵盖连接管理、会话管理、模型定义
  - domain: 领域模型模块，涵盖枚举定义、兼容性验证
  - ml: 机器学习模块，涵盖模型注册、加载、推理
  - logging: 日志模块，涵盖日志管理、链路追踪、上下文管理
  - experiment: 实验模块，涵盖A/B测试管理
"""

from datamind.core import (
    db,
    domain,
    experiment,
    logging,
    ml,
)

__version__ = "1.0.0"
__all__ = [
    'db',
    'domain',
    'experiment',
    'logging',
    'ml',
]