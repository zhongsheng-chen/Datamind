# datamind/core/ml/features/transformer.py
"""WOE 转换器

将原始特征转换为 WOE 值，同时返回完整的分箱信息。

核心功能：
  - transform_with_meta: 转换并返回完整分箱信息
  - to_woe_vector: 提取 WOE 向量用于模型预测
  - transform: 简化版转换（仅 WOE 值）

特性：
  - 完整分箱信息：返回 bin_id、bin_label、边界、坏账率等
  - 缺失值处理：支持缺失值分箱
  - 异常值处理：值不在任何分箱时抛出异常
  - 类型支持：数值型和分类型特征

使用示例：
  >>> from datamind.core.ml.features.transformer import WOETransformer
  >>>
  >>> transformer = WOETransformer(binning_config)
  >>> meta = transformer.transform_with_meta({"age": 45, "income": 50000})
  >>> woe = transformer.to_woe_vector(meta)
"""

from typing import Dict, Any, List
import bisect
import pandas as pd

from datamind.core.ml.features.binning import Bin


class WOETransformer:
    """WOE 转换器

    将原始特征值转换为 WOE 值，同时返回完整的分箱元信息。
    """

    def __init__(self, binning_config: Dict[str, List[Bin]]):
        """
        初始化 WOE 转换器

        参数:
            binning_config: 分箱配置字典
                格式：{"feature_name": [Bin(), Bin(), ...], ...}
        """
        self.binning = binning_config

    def transform_with_meta(self, data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        转换特征并返回完整分箱信息

        参数:
            data: 原始特征字典，格式：{"feature_name": value, ...}

        返回:
            特征元信息字典，格式：
            {
                "feature_name": {
                    "value": 原始值,
                    "woe": WOE值,
                    "bin_id": 分箱ID,
                    "bin_label": 分箱标签,
                    "lower": 下边界,
                    "upper": 上边界,
                    "is_missing": 是否缺失,
                    "bad_rate": 坏账率,
                    "sample_ratio": 样本占比,
                    "description": 描述
                }
            }

        异常:
            ValueError: 特征没有分箱配置或值不在任何分箱中
        """
        result = {}

        for feature, value in data.items():
            bins = self.binning.get(feature)
            if not bins:
                raise ValueError(f"No binning config for feature: {feature}")

            # 查找匹配的分箱
            matched_bin = None
            for b in bins:
                if b.contains(value):
                    matched_bin = b
                    break

            if matched_bin is None:
                raise ValueError(
                    f"Value {value} not in any bin of feature {feature}"
                )

            result[feature] = {
                "value": value,
                "woe": matched_bin.woe,
                "bin_id": matched_bin.id,
                "bin_label": matched_bin.label,
                "lower": matched_bin.lower,
                "upper": matched_bin.upper,
                "is_missing": matched_bin.is_missing,
                "bad_rate": matched_bin.bad_rate,
                "sample_ratio": matched_bin.sample_ratio,
                "description": matched_bin.description,
            }

        return result

    def to_woe_vector(self, feature_meta: Dict[str, Dict]) -> Dict[str, float]:
        """
        从特征元信息中提取 WOE 向量

        参数:
            feature_meta: transform_with_meta 返回的特征元信息

        返回:
            WOE 向量字典，格式：{"feature_name": woe_value, ...}
        """
        return {
            feature: meta["woe"]
            for feature, meta in feature_meta.items()
        }

    def transform(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        简化版转换（仅返回 WOE 值）

        参数:
            features: 原始特征字典

        返回:
            WOE 值字典
        """
        meta = self.transform_with_meta(features)
        return self.to_woe_vector(meta)