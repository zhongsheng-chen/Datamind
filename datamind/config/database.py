# datamind/config/database.py

"""数据库配置

定义元数据库和审计日志数据库的连接参数。

属性：
  - host: 数据库主机地址
  - port: 数据库端口
  - user: 数据库用户名
  - password: 数据库密码

环境变量：
  - DATAMIND_DB_HOST: 数据库主机，默认 127.0.0.1
  - DATAMIND_DB_PORT: 数据库端口，默认 5432
  - DATAMIND_DB_USER: 数据库用户，默认 root
  - DATAMIND_DB_PASSWORD: 数据库密码，默认空字符串
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """数据库配置类"""

    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "root"
    password: str = ""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_DB_",
        env_file=".env",
        extra="ignore",
    )