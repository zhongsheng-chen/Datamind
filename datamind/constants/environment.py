# datamind/constants/environment.py

"""服务环境常量

定义服务的运行环境类型。

核心功能：
  - Environment: 服务环境常量类
  - SUPPORTED_ENVIRONMENTS: 支持的环境集合

使用示例：
  from datamind.constants.environment import Environment, SUPPORTED_ENVIRONMENTS

  if env == Environment.PRODUCTION:
      enable_monitoring()

环境说明：
  - development: 开发环境
  - testing: 测试环境
  - staging: 预发布环境
  - production: 生产环境
"""


class Environment:
    """服务环境常量"""

    DEVELOPMENT: str = "development"
    TESTING: str = "testing"
    STAGING: str = "staging"
    PRODUCTION: str = "production"


SUPPORTED_ENVIRONMENTS = frozenset({
    Environment.DEVELOPMENT,
    Environment.TESTING,
    Environment.STAGING,
    Environment.PRODUCTION,
})