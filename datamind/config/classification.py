# datamind/config/classification.py

"""分类模型配置

定义通用分类模型的默认参数。

属性：
  - threshold: 分类阈值，概率大于该值时预测为正类

环境变量：
  - DATAMIND_CLASSIFICATION_THRESHOLD: 分类阈值，默认 0.5
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


class ClassificationConfig(BaseSettings):
    """分类模型配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_CLASSIFICATION_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    threshold: float = 0.5

    @model_validator(mode="after")
    def validate(self):
        """校验配置参数"""
        if not 0 <= self.threshold <= 1:
            raise ValueError(f"threshold 必须在 0 到 1 之间，当前值：{self.threshold}")

        return self