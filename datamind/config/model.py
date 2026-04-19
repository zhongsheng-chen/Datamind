# datamind/config/model.py

"""模型配置

定义模型注册、加载和管理的相关参数。

属性：
  - enable_hot_reload: 是否启用模型热加载

环境变量：
  - DATAMIND_MODEL_ENABLE_HOT_RELOAD: 是否启用热加载，默认 true
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """模型配置类"""

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_MODEL_",
        env_file=".env",
        extra="ignore",
        frozen=True,
    )

    enable_hot_reload: bool = True