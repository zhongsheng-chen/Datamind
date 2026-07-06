# datamind/core/inference/inference.py

"""统一推理接口

提供模型推理的统一入口，封装适配器调用。

核心功能：
    - predict: 预测概率违约
    - predict_logit: 预测原始 logit
    - transform： 特征转换
    - transform_batch： 批量特征转换
    - get_feature_importance: 特征重要性

使用示例：
    from datamind.core.inference.inference import Inference

    # 创建推理实例
    inference = Inference(
        model=model,
        feature_names=["age", "income"],
        data_types={"age": "numerical", "income": "numerical"}
    )

    # 单条预测
    prob = inference.predict({"age": 30, "income": 50000})

    # 批量预测
    probs = inference.predict([
        {"age": 30, "income": 50000},
        {"age": 40, "income": 80000},
    ])
"""

from typing import Any

from datamind.constants import DataType
from datamind.core.model.adapters.factory import ModelAdapterFactory


class Inference:
    """统一模型推理接口"""

    def __init__(
            self,
            model: Any,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
    ):
        """初始化推理实例

        参数：
            model: 已训练模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
        """
        self.adapter = ModelAdapterFactory.create(
            model=model,
            feature_names=feature_names,
            data_types=data_types,
        )

    def predict(self, X):
        """预测概率违约

        参数：
            X: 特征数据，支持单条字典或字典列表

        返回：
            float 或 list[float]: 违约概率 (0-1)
        """
        return self.adapter.predict(X)

    def predict_logit(self, X):
        """预测原始 logit

        参数：
            X: 特征数据，支持单条字典或字典列表

        返回：
            float 或 list[float]: logit 值
        """
        return self.adapter.predict_logit(X)

    def transform(self, X):
        """特征转换

        将输入特征字典转换为模型输入数组。

        参数：
            X: 特征数据，支持单条字典

        返回：
            numpy 数组，形状为 (1, n_features)
        """
        return self.adapter.to_array(X)

    def transform_batch(self, X):
        """批量特征转换

        将输入特征列表转换为模型输入数组。

        参数：
            X: 特征数据列表

        返回：
            numpy 数组，形状为 (n_samples, n_features)
        """
        return self.adapter.to_array_batch(X)

    def get_feature_importance(self):
        """获取特征重要性

        返回：
            dict[str, float]: 特征重要性字典
        """
        return self.adapter.get_feature_importance()
