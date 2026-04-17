# datamind/config/scorecard.py

"""评分卡配置

定义信用评分卡的标准参数，基于PDO（Points to Double Odds）方法进行刻度参数化。

属性：
  - base_score: 基准分，当好坏比等于base_odds时的分数
  - base_odds: 基准好坏比，对应base_score时的odds值
  - pdo: 翻倍分，odds每翻一倍分数的变化量
  - min_score: 评分输出下限
  - max_score: 评分输出上限

环境变量：
  - DATAMIND_SCORECARD_BASE_SCORE: 基准分，默认 600.0
  - DATAMIND_SCORECARD_BASE_ODDS: 基准好坏比，默认 50.0
  - DATAMIND_SCORECARD_PDO: 翻倍分，默认 50.0
  - DATAMIND_SCORECARD_MIN_SCORE: 评分下限，默认 0
  - DATAMIND_SCORECARD_MAX_SCORE: 评分上限，默认 1000
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class ScorecardConfig(BaseSettings):
    """评分卡配置类"""

    base_score: float = 600.0
    base_odds: float = 50.0
    pdo: float = 50.0
    min_score: float = 0
    max_score: float = 1000

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_SCORECARD_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate(self):
        if self.pdo <= 0:
            raise ValueError(f"pdo 必须大于 0，当前值：{self.pdo}")
        if self.base_odds <= 0:
            raise ValueError(f"base_odds 必须大于 0，当前值：{self.base_odds}")
        if self.min_score >= self.max_score:
            raise ValueError(f"min_score（{self.min_score}）必须小于 max_score（{self.max_score}）")
        if self.min_score < 0:
            raise ValueError(f"min_score 必须大于等于 0，当前值：{self.min_score}")
        if self.max_score - self.min_score < 100:
            raise ValueError(f"评分范围（{self.max_score - self.min_score}）太小，至少需要 100")
        if not 20 <= self.pdo <= 100:
            raise ValueError(f"pdo（{self.pdo}）应在 20 到 100 之间")
        if not self.min_score <= self.base_score <= self.max_score:
            raise ValueError(
                f"base_score（{self.base_score}）必须在 min_score（{self.min_score}）和 max_score（{self.max_score}）之间")
        return self