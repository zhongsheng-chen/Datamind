# datamind/constants/model_stage.py

"""模型阶段常量

定义模型生命周期中的各个阶段，用于模型版本管理和部署控制。

核心功能：
  - ModelStage: 模型阶段常量类
  - SUPPORTED_MODEL_STAGES: 支持的阶段集合

使用示例：
  from datamind.constants.model_stage import ModelStage, SUPPORTED_MODEL_STAGES

  if stage == ModelStage.production:
      route_to_production(model_id)
  elif stage == ModelStage.development:
      allow_test_traffic(model_id)

阶段说明：
  - development: 开发阶段，仅开发环境可用
  - testing: 测试阶段，可用于集成测试
  - staging: 预发布阶段，灰度验证
  - production: 生产阶段，正式服务流量
"""


class ModelStage:
    """模型阶段常量"""

    development: str = "development"
    testing: str = "testing"
    staging: str = "staging"
    production: str = "production"


SUPPORTED_MODEL_STAGES = frozenset({
    ModelStage.development,
    ModelStage.testing,
    ModelStage.staging,
    ModelStage.production,
})