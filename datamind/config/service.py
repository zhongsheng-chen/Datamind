# datamind/config/service.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class ServiceConfig(BaseSettings):

    # 服务信息
    name: str = "datamind"
    version: str = "1.0.0"

    # 运行环境
    environment: Literal["dev", "test", "uat", "prod"] = "dev"

    # API 服务
    host: str = "0.0.0.0"
    port: int = 8080

    # 并发
    workers: int = 1
    timeout: int = 30

    # 文档
    enable_docs: bool = True

    # 请求ID
    enable_request_id: bool = True

    # 健康检查
    enable_health_check: bool = True

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_SERVICE_",
        env_file=".env",
        extra="ignore",
    )