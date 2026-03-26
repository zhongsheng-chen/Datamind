# datamind/core/ml/adapters/sklearn.py

"""Sklearn 模型适配器

支持 Scikit-learn 模型和 Pipeline 的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性

特性：
  - Pipeline 支持：自动处理 Pipeline 模型，提取最终估算器
  - 特征名提取：从 Pipeline 中自动提取特征名（feature_names_in_ 或 get_feature_names_out）
  - 多模型支持：支持分类器（predict_proba）和回归器（predict）
  - 重要性提取：支持 feature_importances_ 和 coef_ 两种方式
  - 自动归一化：特征重要性自动归一化到 [0,1] 区间
  - 批量预测优化：重写 predict_proba_batch 提升性能

继承的方法（由基类提供）：
  - predict: 统一的预测接口，支持多种输入格式
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
"""

import numpy as np
from typing import Dict, List, Optional

from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.logging.debug import debug_print


class SklearnAdapter(BaseModelAdapter):
    """Sklearn 模型适配器（支持 Pipeline）"""

    def __init__(self, model, feature_names: Optional[List[str]] = None):
        """
        初始化适配器

        参数:
            model: sklearn 模型或 Pipeline
            feature_names: 特征名称列表（可选，不提供时尝试从模型提取）
        """
        super().__init__(model, feature_names)

        # 如果是 Pipeline，尝试自动提取特征名
        if hasattr(model, 'named_steps') and feature_names is None:
            self._extract_feature_names_from_pipeline()

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
            debug_print("SklearnAdapter", f"预测失败: {e}")
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

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        支持从 feature_importances_ 或 coef_ 中提取特征重要性。

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        # 如果是 Pipeline，获取最后一个估算器
        if hasattr(self.model, 'named_steps'):
            estimator = list(self.model.named_steps.values())[-1]
        else:
            estimator = self.model

        importance = {}

        # 提取重要性值
        if hasattr(estimator, 'feature_importances_'):
            values = estimator.feature_importances_
        elif hasattr(estimator, 'coef_'):
            coef = estimator.coef_
            if coef.ndim > 1:
                coef = coef[0]
            values = np.abs(coef)
        else:
            # 模型不支持特征重要性提取
            return {}

        # 构建特征名到重要性的映射
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

    def _extract_feature_names_from_pipeline(self):
        """
        从 Pipeline 中自动提取特征名

        支持两种方式：
          1. 从最后一个估算器的 feature_names_in_ 属性提取
          2. 从 Pipeline 的 get_feature_names_out 方法提取
        """
        try:
            # 获取最后一个步骤
            last_step_name = list(self.model.named_steps.keys())[-1]
            last_step = self.model.named_steps[last_step_name]

            # 方式1：从最后一个步骤的 feature_names_in_ 属性获取
            if hasattr(last_step, 'feature_names_in_'):
                self.feature_names = list(last_step.feature_names_in_)

            # 方式2：从 Pipeline 的 get_feature_names_out 方法获取
            elif hasattr(self.model, 'get_feature_names_out'):
                try:
                    self.feature_names = list(self.model.get_feature_names_out())
                except Exception:
                    pass

            if self.feature_names:
                debug_print("SklearnAdapter", f"成功提取特征名: {self.feature_names[:5]}...")
            else:
                debug_print("SklearnAdapter", "无法提取特征名，将使用默认命名")

        except Exception as e:
            debug_print("SklearnAdapter", f"提取特征名失败: {e}")