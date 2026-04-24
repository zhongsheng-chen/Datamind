# datamind/models/loader.py

"""模型加载器

负责从 BentoML Model Store 加载模型。

使用示例：
  from datamind.models.loader import ModelLoader

  loader = ModelLoader()
  model = loader.load("sklearn", "scorecard_model:latest")
"""

from datamind.models.backend import BentoBackend


class ModelLoader:
    """模型加载器"""

    def __init__(self):
        self.backend = BentoBackend()

    def load(self, framework: str, tag: str):
        """从 BentoML Model Store 加载模型

        参数：
            framework: 模型框架（sklearn/xgboost/lightgbm 等）
            tag: 模型标签（格式：模型名:版本）

        返回：
            加载的模型实例
        """
        return self.backend.load(framework, tag)