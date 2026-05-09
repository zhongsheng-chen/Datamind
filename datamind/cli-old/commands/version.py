# Datamind/datamind/cli/commands/version.py

"""版本管理命令行命令

提供系统版本信息查看和更新检查功能。

功能特性：
  - 显示 Datamind 核心版本
  - 显示 Python 运行时版本
  - 显示主要依赖包版本（FastAPI、SQLAlchemy、机器学习框架等）
  - 检查是否有新版本可用（开发中）

命令列表：
  - version show: 显示版本信息
  - version check: 检查更新（开发中）

显示信息包括：
  - Datamind: 核心系统版本
  - Python: Python 解释器版本
  - FastAPI: Web 框架版本
  - SQLAlchemy: ORM 框架版本
  - BentoML: 模型服务框架版本
  - scikit-learn: 机器学习库版本
  - XGBoost: 梯度提升库版本
  - LightGBM: 轻量梯度提升库版本
  - PyTorch: 深度学习框架版本
  - TensorFlow: 深度学习框架版本

使用示例：
  # 显示版本信息
  datamind version show

  # 检查更新（开发中）
  datamind version check

输出格式：
  - 表格形式展示组件和版本信息
  - 未安装的包显示为"未安装"
"""

import click
import sys

from datamind.cli.utils.printer import print_table
from datamind.config import settings


@click.group(name='version')
def version():
    """版本管理命令"""
    pass


@version.command(name='show')
def show_version():
    """显示版本信息"""
    info = [
        ['组件', '版本'],
        ['-' * 20, '-' * 20],
        ['Datamind', settings.app.version],
        ['Python', sys.version.split()[0]],
        ['FastAPI', get_package_version('fastapi')],
        ['SQLAlchemy', get_package_version('sqlalchemy')],
        ['BentoML', get_package_version('bentoml')],
        ['scikit-learn', get_package_version('sklearn')],
        ['XGBoost', get_package_version('xgboost')],
        ['LightGBM', get_package_version('lightgbm')],
        ['PyTorch', get_package_version('torch')],
        ['TensorFlow', get_package_version('tensorflow')],
    ]

    print_table(['组件', '版本'], info[1:], header=info[0])


@version.command(name='check')
def check_updates():
    """检查更新"""
    click.echo("检查更新功能开发中...")


def get_package_version(package_name):
    """获取包版本

    参数:
        package_name: 包名（如 'fastapi', 'sklearn', 'torch' 等）

    返回:
        包版本字符串，如果导入失败则返回 "未安装"

    注意:
        - 某些包需要特殊处理（如 sklearn 导入为 sklearn，但包名是 scikit-learn）
        - 使用 try/except 确保导入失败时不会中断程序
    """
    try:
        if package_name == 'sklearn':
            import sklearn
            return sklearn.__version__
        elif package_name == 'xgboost':
            import xgboost
            return xgboost.__version__
        elif package_name == 'lightgbm':
            import lightgbm
            return lightgbm.__version__
        elif package_name == 'torch':
            import torch
            return torch.__version__
        elif package_name == 'tensorflow':
            import tensorflow
            return tensorflow.__version__
        else:
            module = __import__(package_name)
            return module.__version__
    except Exception:
        return '未安装'