# datamind/core/scoring/adapters/xgboost.py

"""XGBoost 模型适配器

支持 XGBoost 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - decision_function: 获取原始 logit 值
  - decision_function_batch: 批量获取 logit 值
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集

特性：
  - 原生支持：直接使用 XGBoost 的 predict 方法
  - 特征重要性提取：从模型中提取 gain 或 weight 类型的重要性
  - 自动归一化：特征重要性自动归一化到 [0,1] 区间
  - 批量预测优化：重写 predict_proba_batch 提升性能
"""

import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability
from datamind.core.logging import get_logger

_logger = get_logger(__name__)


class XGBoostAdapter(BaseModelAdapter):
    """XGBoost 模型适配器"""

    SUPPORTED_CAPABILITIES: ScorecardCapability = (
        ScorecardCapability.PREDICT_CLASS |
        ScorecardCapability.BATCH_PREDICT |
        ScorecardCapability.FEATURE_IMPORTANCE |
        ScorecardCapability.SHAP |
        ScorecardCapability.SHAP_TREE
    )

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        data_types: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化适配器

        参数:
            model: XGBoost 模型实例
            feature_names: 特征名称列表（可选）
            data_types: 特征数据类型映射，用于类型验证
        """
        super().__init__(model, feature_names, data_types)

        self._capabilities = self.SUPPORTED_CAPABILITIES

        _logger.debug("XGBoost 适配器初始化完成")

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        返回:
            ScorecardCapability 位掩码
        """
        return self._capabilities

    # ==================== 核心预测方法 ====================

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            proba = self.model.predict(X, iteration_range=(0, self.model.best_iteration + 1))[0]
            return float(proba)
        except Exception as e:
            _logger.error("XGBoost 单条预测失败: %s", e)
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
            probs = self.model.predict(X, iteration_range=(0, self.model.best_iteration + 1))
            return probs.tolist()
        except Exception as e:
            _logger.error("XGBoost 批量预测失败: %s", e)
            raise

    def decision_function(self, X: np.ndarray) -> float:
        """
        获取原始 logit 值

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            logit 值
        """
        # XGBoost 使用 output_margin=True 获取原始分数
        return float(self.model.predict(X, output_margin=True)[0])

    def decision_function_batch(self, X: np.ndarray) -> List[float]:
        """
        批量获取 logit 值

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            logit 值列表
        """
        return self.model.predict(X, output_margin=True).tolist()

    # ==================== 特征重要性 ====================

    def get_feature_importance(self, importance_type: str = 'gain') -> Dict[str, float]:
        """
        获取特征重要性

        参数:
            importance_type: 重要性类型，可选 'weight', 'gain', 'cover'

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        importance = {}

        if hasattr(self.model, 'get_score'):
            scores = self.model.get_score(importance_type=importance_type)

            if self.feature_names:
                for name in self.feature_names:
                    importance[name] = float(scores.get(name, 0))
            else:
                for i in range(len(scores)):
                    importance[f"feature_{i}"] = float(scores.get(f"f{i}", 0))

            total = sum(importance.values())
            if total > 0:
                for name in importance:
                    importance[name] = importance[name] / total

        return importance