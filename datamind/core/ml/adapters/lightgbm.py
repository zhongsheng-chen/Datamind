# datamind/core/ml/common/adapters/lightgbm.py

"""LightGBM 模型适配器

支持 LightGBM 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性

特性：
  - 原生支持：直接使用 LightGBM 的 predict_proba 方法
  - 特征重要性提取：从模型中提取 split 或 gain 类型的重要性
  - 自动归一化：特征重要性自动归一化到 [0,1] 区间
  - 批量预测优化：重写 predict_proba_batch 提升性能
"""

import numpy as np
from typing import Dict, List

from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.logging.debug import debug_print


class LightGBMAdapter(BaseModelAdapter):
    """LightGBM 模型适配器"""

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)[0][1]
            else:
                proba = self.model.predict(X)[0]
            return float(proba)
        except Exception as e:
            debug_print("LightGBMAdapter", f"预测失败: {e}")
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（重写基类方法以优化性能）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)[:, 1].tolist()
        return self.model.predict(X).tolist()

    def get_feature_importance(self, importance_type: str = 'split') -> Dict[str, float]:
        """
        获取特征重要性

        参数:
            importance_type: 重要性类型，可选 'split'（分裂次数）或 'gain'（信息增益）

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        importance = {}

        if hasattr(self.model, 'feature_importance'):
            values = self.model.feature_importance(importance_type=importance_type)

            if self.feature_names:
                for i, name in enumerate(self.feature_names):
                    if i < len(values):
                        importance[name] = float(values[i])
            else:
                for i, val in enumerate(values):
                    importance[f"feature_{i}"] = float(val)

            # 归一化到 [0,1] 区间
            total = sum(importance.values())
            if total > 0:
                for name in importance:
                    importance[name] = importance[name] / total

        return importance