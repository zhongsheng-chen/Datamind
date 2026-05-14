# datamind/db/core/url.py

"""数据库 URL 获取模块

负责从配置中读取数据库连接 URL。

核心功能：
  - get_db_url: 获取数据库连接 URL

使用示例：
  from datamind.db.core.url import get_db_url

  url = get_db_url()
"""

from datamind.config import get_settings


def get_db_url() -> str:
    """获取数据库连接 URL

    返回：
        数据库连接 URL

    异常：
        RuntimeError: URL 未配置时抛出
    """
    settings = get_settings()
    db = settings.database

    if not db.url:
        raise RuntimeError("未配置数据库连接 URL，请设置环境变量 DATAMIND_DATABASE_URL")

    return db.url