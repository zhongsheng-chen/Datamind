# datamind/core/experiment/__init__.py
"""
实验模块

提供A/B测试功能
"""

from core.experiment.ab_test import ab_test_manager

__all__ = [
    'ab_test_manager',
]