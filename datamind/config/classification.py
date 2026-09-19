"""分类模型配置

定义通用分类模型的默认分类阈值。

核心功能：
  - ClassificationConfig: 读取并校验分类模型配置

属性：
  - threshold: 分类阈值，概率大于该值时预测为正类

环境变量：
  - DATAMIND_CLASSIFICATION_THRESHOLD:
    分类阈值，默认 0.5

使用示例：
  from datamind.config.classification import ClassificationConfig

  config = ClassificationConfig()

  print(config.threshold)
"""

from pydantic import model_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


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
    def validate_config(self) -> "ClassificationConfig":
        """校验分类模型配置参数"""
        if not 0 <= self.threshold <= 1:
            raise ValueError(
                "threshold 必须在 0 到 1 之间，"
                f"当前值：{self.threshold}"
            )

        return self
