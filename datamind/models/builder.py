# datamind/models/builder.py

from datamind.models.artifact import ModelArtifact


class ModelBuilder:
    """模型构建器（策略层）"""

    @staticmethod
    def build(framework: str, data: bytes, **context):
        # 1. 反序列化
        model = ModelArtifact.load(framework, data)

        # 2. 预留扩展点（非常重要）
        model = ModelBuilder._post_process(model, framework, context)

        return model

    @staticmethod
    def _post_process(model, framework, context):
        # 后续可以加：
        # - wrapper
        # - schema attach
        # - compatibility patch
        # - optimization
        return model