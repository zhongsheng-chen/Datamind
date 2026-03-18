# datamind/cli/commands/version.py
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
        ['Datamind', settings.VERSION],
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
    """获取包版本"""
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
    except:
        return '未安装'