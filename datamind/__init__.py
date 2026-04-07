# datamind/__init__.py

"""Datamind 核心包

提供平台核心功能并定义全局路径常量（PACKAGE_ROOT / PROJECT_ROOT）。
"""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

__all__ = [
    "PACKAGE_ROOT",
    "PROJECT_ROOT",
]