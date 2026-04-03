# datamind/core/scoring/adapters/lightgbm.py

"""LightGBM 模型适配器

支持 LightGBM 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - decision_function: 获取原始 logit 值
  - decision_function_batch: 批量获取 logit 值
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集

特性：
  - 原生支持：直接使用 LightGBM 的 predict_proba 方法
  - 特征重要性提取：从模型中提取 split 或 gain 类型的重要性
  - 自动归一化：特征重要性自动归一化到 [0,1] 区间
  - 批量预测优化：重写 predict_proba_batch 提升性能
"""

import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class LightGBMAdapter(BaseModelAdapter):
    """LightGBM 模型适配器"""

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
            model: LightGBM 模型
            feature_names: 特征名称列表（可选）
            data_types: 特征数据类型映射，用于类型验证
        """
        super().__init__(model, feature_names, data_types)

        self._capabilities = self.SUPPORTED_CAPABILITIES

        # 尝试提取特征名（如果未提供）
        if feature_names is None:
            self._extract_feature_names_from_model()

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        返回:
            ScorecardCapability 位掩码
        """
        return self._capabilities

    def _extract_feature_names_from_model(self):
        """自动提取 LightGBM 模型特征名"""
        try:
            if hasattr(self.model, 'feature_name'):
                self.feature_names = list(self.model.feature_name())
                logger.debug("成功提取 LightGBM 特征名，数量: %d", len(self.feature_names))
            else:
                logger.debug("LightGBM 模型无 feature_name 属性，将使用默认命名")
        except Exception as e:
            logger.debug("提取 LightGBM 特征名失败: %s", e)

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
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)[0][1]
            else:
                proba = float(self.model.predict(X)[0])
            return float(proba)
        except Exception as e:
            logger.error("LightGBM 单条预测失败: %s", e)
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
            if hasattr(self.model, "predict_proba"):
                return self.model.predict_proba(X)[:, 1].tolist()
            return self.model.predict(X).tolist()
        except Exception as e:
            logger.error("LightGBM 批量预测失败: %s", e)
            raise

    def decision_function(self, X: np.ndarray) -> float:
        """
        获取原始 logit 值

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            logit 值
        """
        # LightGBM 使用 raw_score=True 获取原始分数
        return float(self.model.predict(X, raw_score=True)[0])

    def decision_function_batch(self, X: np.ndarray) -> List[float]:
        """
        批量获取 logit 值

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            logit 值列表
        """
        return self.model.predict(X, raw_score=True).tolist()

    # ==================== 特征重要性 ====================

    def get_feature_importance(self, importance_type: str = 'split') -> Dict[str, float]:
        """
        获取特征重要性

        参数:
            importance_type: 重要性类型，可选 'split'（分裂次数）或 'gain'（信息增益）

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        importance = {}

        try:
            if hasattr(self.model, 'feature_importance'):
                values = self.model.feature_importance(importance_type=importance_type)

                if self.feature_names:
                    for i, name in enumerate(self.feature_names):
                        if i < len(values):
                            importance[name] = float(values[i])
                else:
                    for i, val in enumerate(values):
                        importance[f"feature_{i}"] = float(val)

                total = sum(importance.values())
                if total > 0:
                    for name in importance:
                        importance[name] = importance[name] / total
        except Exception as e:
            logger.error("获取 LightGBM 特征重要性失败: %s", e)

        return importance