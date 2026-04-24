# datamind/config/ab_test.py

"""AB测试配置

定义模型AB测试的流量分配策略。

属性：
  - enabled: 是否启用AB测试
  - group_a_weight: A组流量权重
  - group_b_weight: B组流量权重
  - strategy: 分流策略

环境变量：
  - DATAMIND_ABTEST_ENABLED: 是否启用，默认 false
  - DATAMIND_ABTEST_GROUP_A_WEIGHT: A组权重，默认 0.5
  - DATAMIND_ABTEST_GROUP_B_WEIGHT: B组权重，默认 0.5
  - DATAMIND_ABTEST_STRATEGY: 分流策略，默认 random
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

from datamind.constants import ABStrategy, SUPPORTED_AB_STRATEGIES


class ABTestConfig(BaseSettings):
    """AB测试配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_ABTEST_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    enabled: bool = False
    group_a_weight: float = 0.5
    group_b_weight: float = 0.5
    strategy: str = ABStrategy.RANDOM

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if self.strategy not in SUPPORTED_AB_STRATEGIES:
            raise ValueError(f"不支持的策略类型：{self.strategy}，支持：{SUPPORTED_AB_STRATEGIES}")

        total = self.group_a_weight + self.group_b_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"权重之和必须等于 1，当前值：{total}")

        if self.group_a_weight < 0 or self.group_b_weight < 0:
            raise ValueError("权重不能为负数")

        return self