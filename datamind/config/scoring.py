"""评分任务配置

定义评分任务的默认决策阈值。

核心功能：
  - ScoringConfig: 读取并校验评分任务配置

属性：
  - threshold: 评分决策阈值，评分大于等于该值时通过

环境变量：
  - DATAMIND_SCORING_THRESHOLD:
    评分决策阈值，默认 600.0

使用示例：
  from datamind.config.scoring import ScoringConfig

  config = ScoringConfig()

  print(config.threshold)
"""

import math

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class ScoringConfig(BaseSettings):
    """评分任务配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_SCORING_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    threshold: float = 600.0

    @model_validator(mode="after")
    def validate_config(self) -> "ScoringConfig":
        """校验评分任务配置参数"""
        if not math.isfinite(self.threshold):
            raise ValueError(
                "threshold 必须是有限数值，"
                f"当前值：{self.threshold}"
            )

        return self
