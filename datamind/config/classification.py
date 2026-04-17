# datamind/config/classification.py

"""分类模型配置

定义通用分类模型的默认参数。

属性：
  - threshold: 分类阈值，概率大于该值时预测为正类

环境变量：
  - DATAMIND_CLASSIFICATION_THRESHOLD: 分类阈值，默认 0.5
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ClassificationConfig(BaseSettings):
    """分类模型配置类"""

    threshold: float = 0.5

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_CLASSIFICATION_",
        env_file=".env",
        extra="ignore",
    )