"""数据库 URL 获取模块

负责从全局配置中读取数据库连接 URL。

核心功能：
  - get_db_url: 获取数据库连接 URL

使用示例：
  from datamind.db.core.url import get_db_url

  url = get_db_url()
"""

from datamind.config import get_database_config


def get_db_url() -> str:
    """获取数据库连接 URL

    数据库 URL 已由 DatabaseConfig 校验为必填且非空。

    返回：
        数据库连接 URL
    """
    return get_database_config().url
