# datamind/config/database.py

"""数据库配置

定义数据库连接参数。

属性：
  - url: 数据库连接 URL
  - pool_size: 连接池大小
  - max_overflow: 最大溢出连接数
  - pool_timeout: 获取连接超时时间（秒）
  - pool_recycle: 连接回收时间（秒）
  - echo: 是否打印 SQL 语句

环境变量：
  - DATAMIND_DATABASE_URL: 数据库连接 URL
  - DATAMIND_DATABASE_POOL_SIZE: 连接池大小，默认 10
  - DATAMIND_DATABASE_MAX_OVERFLOW: 最大溢出连接数，默认 20
  - DATAMIND_DATABASE_POOL_TIMEOUT: 获取连接超时时间，默认 30
  - DATAMIND_DATABASE_POOL_RECYCLE: 连接回收时间，默认 3600
  - DATAMIND_DATABASE_ECHO: 是否打印 SQL，默认 False
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class DatabaseConfig(BaseSettings):
    """数据库配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_DATABASE_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    url: str = "postgresql+asyncpg://user:password@localhost:5432/dbname"

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if not self.url:
            raise ValueError("url 不能为空")

        if self.pool_size < 0:
            raise ValueError(f"pool_size 必须大于等于 0，当前值：{self.pool_size}")

        if self.max_overflow < 0:
            raise ValueError(f"max_overflow 必须大于等于 0，当前值：{self.max_overflow}")

        if self.pool_timeout < 0:
            raise ValueError(f"pool_timeout 必须大于等于 0，当前值：{self.pool_timeout}")

        if self.pool_recycle < 0:
            raise ValueError(f"pool_recycle 必须大于等于 0，当前值：{self.pool_recycle}")

        return self