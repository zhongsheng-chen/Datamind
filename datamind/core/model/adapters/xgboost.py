# datamind/core/model/adapters/xgboost.py

"""XGBoost 模型适配器

为 XGBoost 模型提供统一接口适配。
"""

import structlog
import numpy as np

from datamind.core.model.adapters.base import BaseModelAdapter
from datamind.core.capability import ModelCapability

logger = structlog.get_logger(__name__)


class XGBoostAdapter(BaseModelAdapter):
    """XGBoost 模型适配器

    能力声明：
        - FEATURE_IMPORTANCE: 特征重要性
        - PREDICT_LOG_ODDS: 原始对数几率
        - SHAP: SHAP 解释
    """

    SUPPORTED_CAPABILITIES = (
        ModelCapability.FEATURE_IMPORTANCE
        | ModelCapability.PREDICT_LOG_ODDS
        | ModelCapability.SHAP
    )

    def __init__(
            self,
            model,
            feature_names=None,
            data_types=None,
    ):
        """初始化适配器

        参数：
            model: XGBoost 模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
        """
        super().__init__(
            model=model,
            feature_names=feature_names,
            data_types=data_types,
        )

        self._validate_model()

    def _validate_model(self):
        """校验模型

        异常：
            ValueError: Datamind 仅支持二分类模型
        """
        if hasattr(self.model, "n_classes_"):
            class_count = self.model.n_classes_

            if class_count != 2:
                raise ValueError(
                    f"{self.__class__.__name__}: Datamind 仅支持二分类模型，当前类别数={class_count}"
                )

            logger.debug("模型校验通过 | 类别数=%d", class_count)

    def predict_proba(self, X: np.ndarray) -> float:
        """预测违约概率

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            违约概率 (0-1)

        异常：
            NotImplementedError: 模型不支持 predict_proba 方法
            NotImplementedError: 暂不支持多分类
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "predict_proba"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 predict_proba 方法"
            )

        probs = self.model.predict_proba(X)

        if probs.shape[1] != 2:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 暂不支持多分类，当前类别数={probs.shape[1]}"
            )

        result = float(probs[0, 1])

        logger.debug("预测概率成功 | 概率=%s", result)
        return result

    def decision_function(self, X: np.ndarray) -> float:
        """获取原始 logit 值

        XGBoost 使用 predict(output_margin=True) 获取原始 margin。

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            logit 值

        异常：
            NotImplementedError: 暂不支持多分类 decision_function 方法
        """
        X = self._ensure_2d(X)

        margin = self.model.predict(X, output_margin=True)

        if margin.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 暂不支持多分类 decision_function 方法"
            )

        result = float(margin[0])

        logger.debug("获取 logit 成功 | logit=%s", result)
        return result

    def predict_proba_batch(self, X: np.ndarray) -> list[float]:
        """批量预测违约概率

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            概率列表，长度 n_samples

        异常：
            NotImplementedError: 模型不支持 predict_proba 方法
            NotImplementedError: 暂不支持多分类
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "predict_proba"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 predict_proba 方法"
            )

        probs = self.model.predict_proba(X)

        if probs.shape[1] != 2:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 暂不支持多分类，当前类别数={probs.shape[1]}"
            )

        result = [float(p[1]) for p in probs]

        logger.debug("批量预测概率成功 | 样本数=%d", len(result))
        return result

    def decision_function_batch(self, X: np.ndarray) -> list[float]:
        """批量获取原始 logit 值

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            logit 值列表

        异常：
            NotImplementedError: 暂不支持多分类
        """
        X = self._ensure_2d(X)

        margins = self.model.predict(X, output_margin=True)

        if margins.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 暂不支持多分类 decision_function 方法"
            )

        result = [float(x) for x in margins]

        logger.debug("批量获取 logit 成功 | 样本数=%d", len(result))
        return result

    def get_feature_importance(self) -> dict[str, float]:
        """获取特征重要性

        使用 gain 作为重要性度量。

        返回：
            特征重要性字典

        异常：
            NotImplementedError: 模型不支持特征重要性
        """
        self.require_capability(ModelCapability.FEATURE_IMPORTANCE)

        if not hasattr(self.model, "get_booster"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持特征重要性"
            )

        booster = self.model.get_booster()
        score = booster.get_score(importance_type="gain")

        logger.debug("获取特征重要性 | 来源=XGBoost gain")

        if not self.feature_names:
            result = {
                k: float(v)
                for k, v in score.items()
            }
        else:
            result = {
                name: float(score.get(f"f{i}", 0.0))
                for i, name in enumerate(self.feature_names)
            }

        logger.debug("特征重要性计算完成 | 特征数=%d", len(result))
        return result

    @staticmethod
    def _ensure_2d(X: np.ndarray) -> np.ndarray:
        """确保输入为 2D 数组

        参数：
            X: 输入数组

        返回：
            2D 数组，形状为 (1, n_features) 或 (n_samples, n_features)

        异常：
            ValueError: 数组维度不支持
        """
        if X.ndim == 1:
            return X.reshape(1, -1)

        if X.ndim != 2:
            raise ValueError(
                f"仅支持 1D / 2D numpy 输入，当前 ndim={X.ndim}"
            )

        return X