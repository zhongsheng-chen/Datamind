# datamind/config/database.py

"""数据库配置

定义元数据库和审计日志数据库的连接参数。

属性：
  - host: 数据库主机地址
  - port: 数据库端口
  - user: 数据库用户名
  - password: 数据库密码
  - database: 数据库名称

环境变量：
  - DATAMIND_DB_HOST: 数据库主机，默认 localhost
  - DATAMIND_DB_PORT: 数据库端口，默认 5432
  - DATAMIND_DB_USER: 数据库用户，默认 datamind
  - DATAMIND_DB_PASSWORD: 数据库密码，默认空
  - DATAMIND_DB_DATABASE: 数据库名称，默认 datamind
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class DatabaseConfig(BaseSettings):
    """数据库配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_DB_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    host: str = "localhost"
    port: int = 5432
    user: str = "datamind"
    password: str = ""
    database: str = "datamind"

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if not self.host:
            raise ValueError("host 不能为空")

        if not 1 <= self.port <= 65535:
            raise ValueError(f"port 必须在 1 到 65535 之间，当前值：{self.port}")

        if not self.user:
            raise ValueError("user 不能为空")

        if not self.database:
            raise ValueError("database 不能为空")

        return self