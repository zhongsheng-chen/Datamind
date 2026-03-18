# Datamind/datamind/core/experiment/__init__.py
"""实验模块

提供A/B测试功能
"""

from datamind.core.experiment.ab_test import (
    ABTestManager,
    AssignmentStrategy,
    TrafficSplitter,
)

__all__ = [
    'ABTestManager',
    'AssignmentStrategy',
    'TrafficSplitter',
]