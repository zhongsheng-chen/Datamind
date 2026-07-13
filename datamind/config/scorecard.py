# datamind/config/scorecard.py

"""评分卡配置

定义信用评分卡的标准参数，
基于 PDO（Points to Double Odds）方法进行刻度参数化。

核心功能：
  - ScorecardConfig: 读取并校验评分卡配置

属性：
  - base_score: 基准分，当好坏比等于 base_odds 时的分数
  - base_odds: 基准好坏比，对应 base_score 时的 odds 值
  - pdo: 翻倍分，odds 每翻一倍时分数的变化量
  - min_score: 评分输出下限
  - max_score: 评分输出上限

环境变量：
  - DATAMIND_SCORECARD_BASE_SCORE: 基准分，默认 600.0
  - DATAMIND_SCORECARD_BASE_ODDS: 基准好坏比，默认 50.0
  - DATAMIND_SCORECARD_PDO: 翻倍分，默认 20.0
  - DATAMIND_SCORECARD_MIN_SCORE: 评分下限，默认 0.0
  - DATAMIND_SCORECARD_MAX_SCORE: 评分上限，默认 1000.0

使用示例：
  from datamind.config.scorecard import ScorecardConfig

  config = ScorecardConfig()

  print(config.base_score)
  print(config.pdo)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class ScorecardConfig(BaseSettings):
    """评分卡配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_SCORECARD_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    base_score: float = 600.0
    base_odds: float = 50.0
    pdo: float = 20.0
    min_score: float = 0.0
    max_score: float = 1000.0

    @model_validator(mode="after")
    def validate_config(self) -> "ScorecardConfig":
        """校验评分卡配置参数"""
        if self.base_odds <= 0:
            raise ValueError(
                "base_odds 必须大于 0，"
                f"当前值：{self.base_odds}"
            )

        if self.min_score < 0:
            raise ValueError(
                "min_score 必须大于等于 0，"
                f"当前值：{self.min_score}"
            )

        if self.min_score >= self.max_score:
            raise ValueError(
                f"min_score（{self.min_score}）"
                f"必须小于 max_score（{self.max_score}）"
            )

        score_range = self.max_score - self.min_score

        if score_range < 100:
            raise ValueError(
                f"评分范围（{score_range}）太小，"
                "至少需要 100"
            )

        if not 20 <= self.pdo <= 100:
            raise ValueError(
                f"pdo（{self.pdo}）"
                "必须在 20 到 100 之间"
            )

        if not self.min_score <= self.base_score <= self.max_score:
            raise ValueError(
                f"base_score（{self.base_score}）"
                f"必须在 min_score（{self.min_score}）"
                f"和 max_score（{self.max_score}）之间"
            )

        return self
