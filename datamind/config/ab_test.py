# datamind/config/ab_test.py

"""AB测试配置

定义模型AB测试的流量分配策略。

属性：
  - enabled: 是否启用AB测试
  - group_a_weight: A组流量权重
  - group_b_weight: B组流量权重
  - strategy: 分流策略，random（随机）或 hash（哈希）

环境变量：
  - DATAMIND_ABTEST_ENABLED: 是否启用，默认 false
  - DATAMIND_ABTEST_GROUP_A_WEIGHT: A组权重，默认 0.5
  - DATAMIND_ABTEST_GROUP_B_WEIGHT: B组权重，默认 0.5
  - DATAMIND_ABTEST_STRATEGY: 分流策略，默认 random
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class ABTestConfig(BaseSettings):
    """AB测试配置类"""

    enabled: bool = False
    group_a_weight: float = 0.5
    group_b_weight: float = 0.5
    strategy: str = "random"

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_ABTEST_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate(self):
        if self.group_a_weight + self.group_b_weight != 1.0:
            raise ValueError(
                f"group_a_weight（{self.group_a_weight}）和 group_b_weight（{self.group_b_weight}）之和必须等于 1")
        if self.group_a_weight < 0 or self.group_b_weight < 0:
            raise ValueError("权重不能为负数")
        if self.strategy not in ["random", "hash"]:
            raise ValueError(f"strategy 必须是 random 或 hash，当前值：{self.strategy}")
        return self