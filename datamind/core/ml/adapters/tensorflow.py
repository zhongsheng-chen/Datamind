# datamind/core/ml/adapters/tensorflow.py

"""TensorFlow 模型适配器

支持 TensorFlow 和 Keras 模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性

特性：
  - Keras 支持：支持 Keras Sequential 和 Functional API 模型
  - 多输出支持：支持二分类（softmax）和回归（sigmoid/直接输出）
  - 批量预测优化：重写 predict_proba_batch 使用 batch 参数提升性能
  - 错误处理：完善的异常捕获和调试信息

继承的方法（由基类提供）：
  - predict: 统一的预测接口，支持多种输入格式
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
"""

import numpy as np
from typing import Dict, List, Optional

from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.logging.debug import debug_print


class TensorFlowAdapter(BaseModelAdapter):
    """TensorFlow/Keras 模型适配器"""

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            output = self.model.predict(X, verbose=0)

            # 处理输出
            if output.shape[-1] == 2:
                # 二分类，取正类概率
                proba = output[0][1]
            else:
                # 回归或单输出
                proba = output[0] if output.ndim == 1 else output[0][0]

            return float(proba)

        except Exception as e:
            debug_print("TensorFlowAdapter", f"预测失败: {e}")
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（重写基类方法以优化性能）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        try:
            output = self.model.predict(X, verbose=0)

            # 处理输出
            if output.shape[-1] == 2:
                # 二分类，取正类概率
                probs = output[:, 1]
            else:
                # 回归或单输出
                probs = output.flatten()

            return probs.tolist()

        except Exception as e:
            debug_print("TensorFlowAdapter", f"批量预测失败: {e}")
            raise

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        TensorFlow/Keras 模型通常不直接提供特征重要性，
        子类可重写此方法实现自定义的重要性提取逻辑。

        返回:
            空字典（TensorFlow/Keras 模型不直接支持特征重要性）
        """
        return {}