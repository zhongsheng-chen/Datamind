# datamind/core/ml/common/adapters/xgboost.py

"""XGBoost 模型适配器

支持 XGBoost 原生模型的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - get_feature_importance: 获取特征重要性

特性：
  - DMatrix 支持：自动将 numpy 数组转换为 XGBoost DMatrix 格式
  - 特征重要性提取：从模型中提取 weight 类型的重要性（特征被使用的次数）
  - 自动归一化：特征重要性自动归一化到 [0,1] 区间
  - 批量预测优化：重写 predict_proba_batch 使用 DMatrix 批量处理，提升性能
  - 错误处理：完善的异常捕获和调试信息

继承的方法（由基类提供）：
  - predict: 统一的预测接口，支持多种输入格式
  - to_array: 特征字典转 numpy 数组
  - to_array_batch: 批量特征字典转 numpy 数组
"""

import numpy as np
import xgboost as xgb
from typing import Dict, List

from datamind.core.ml.adapters.base import BaseModelAdapter
from datamind.core.logging.debug import debug_print


class XGBoostAdapter(BaseModelAdapter):
    """XGBoost 模型适配器"""

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            dmatrix = xgb.DMatrix(X)

            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(dmatrix)[0][1]
            else:
                proba = self.model.predict(dmatrix)[0]

            return float(proba)
        except Exception as e:
            debug_print("XGBoostAdapter", f"预测失败: {e}")
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率（重写基类方法以优化性能）

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        dmatrix = xgb.DMatrix(X)
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(dmatrix)[:, 1].tolist()
        return self.model.predict(dmatrix).tolist()

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        使用 weight 类型的重要性（特征在树中被使用的次数）。

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        importance = {}

        if hasattr(self.model, 'get_score'):
            scores = self.model.get_score(importance_type='weight')
            for name, val in scores.items():
                importance[name] = float(val)

            # 归一化到 [0,1] 区间
            total = sum(importance.values())
            if total > 0:
                for name in importance:
                    importance[name] = importance[name] / total

        return importance