# datamind/core/scoring/adapters/tensorflow.py

"""TensorFlow 模型适配器

支持 TensorFlow 和 Keras 模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集

特性：
  - Keras 支持：支持 Keras Sequential 和 Functional API 模型
  - 多输出支持：支持二分类（softmax）和回归（sigmoid/直接输出）
  - 批量预测优化：重写 predict_proba_batch 使用 batch 参数提升性能
"""

import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability


class TensorFlowAdapter(BaseModelAdapter):
    """TensorFlow/Keras 模型适配器"""

    SUPPORTED_CAPABILITIES: ScorecardCapability = (
        ScorecardCapability.PREDICT_CLASS |
        ScorecardCapability.BATCH_PREDICT |
        ScorecardCapability.SHAP_KERNEL
    )

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        transformer: Optional[Any] = None,
        debug: bool = False
    ):
        """
        初始化适配器

        参数:
            model: TensorFlow/Keras 模型实例
            feature_names: 特征名称列表（可选）
            transformer: WOE转换器（评分卡模型使用）
            debug: 是否启用调试日志
        """
        super().__init__(model, feature_names, transformer=transformer, debug=debug)

        self._capabilities = self.SUPPORTED_CAPABILITIES

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        返回:
            ScorecardCapability 位掩码
        """
        return self._capabilities

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

            if output.shape[-1] == 2:
                proba = output[0][1]
            else:
                proba = output[0] if output.ndim == 1 else output[0][0]

            return float(proba)

        except Exception as e:
            self._error("预测失败: %s", e)
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        try:
            output = self.model.predict(X, verbose=0)

            if output.shape[-1] == 2:
                probs = output[:, 1]
            else:
                probs = output.flatten()

            return probs.tolist()

        except Exception as e:
            self._error("批量预测失败: %s", e)
            raise

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        TensorFlow/Keras 模型通常不直接提供特征重要性。

        返回:
            空字典
        """
        return {}