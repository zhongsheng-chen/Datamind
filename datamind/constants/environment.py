# datamind/constants/environment.py

"""服务环境枚举

定义服务的运行环境类型。

核心功能：
  - Environment: 服务环境字符串枚举
  - SUPPORTED_ENVIRONMENTS: 支持的环境集合

使用示例：
  from datamind.constants.environment import Environment

  if environment == Environment.PRODUCTION:
      enable_monitoring()
"""

from enum import Enum
from typing import FrozenSet


class Environment(str, Enum):
    """服务环境字符串枚举"""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_ENVIRONMENTS: FrozenSet[str] = frozenset(
    str(environment)
    for environment in Environment
)
