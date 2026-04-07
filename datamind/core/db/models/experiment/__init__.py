# Datamind/datamind/core/db/models/experiment/__init__.py

"""实验相关数据库模型

包含A/B测试等实验功能的数据模型。

模块组成：
  - ab_test: A/B测试配置表定义（ABTestConfig）
  - assignment: A/B测试分配记录表定义（ABTestAssignment）
"""

from .ab_test import ABTestConfig
from .assignment import ABTestAssignment

__all__ = [
    'ABTestConfig',
    'ABTestAssignment',
]