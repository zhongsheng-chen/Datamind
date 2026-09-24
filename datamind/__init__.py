"""Datamind 开放式模型服务管理平台."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

__all__ = [
    "PACKAGE_ROOT",
    "PROJECT_ROOT",
]
