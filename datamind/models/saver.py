# datamind/models/saver.py

"""模型保存器

负责将训练好的模型保存到 BentoML Model Store。

使用示例：
  from datamind.models.saver import ModelSaver

  saver = ModelSaver()
  tag = saver.save("sklearn", model, "scorecard_model:latest")
"""

from datamind.models.backend import BentoBackend


class ModelSaver:
    """模型保存器"""

    def __init__(self):
        self.backend = BentoBackend()

    def save(self, framework: str, model, name: str) -> str:
        """保存模型到 BentoML Model Store

        参数：
            framework: 模型框架（sklearn/xgboost/lightgbm 等）
            model: 模型实例
            name: 模型名称（支持 tag 格式）

        返回：
            模型 tag
        """
        return self.backend.save(framework, model, name)