# datamind/core/model/adapters/catboost.py

"""CatBoost 模型适配器

为 CatBoost 二分类模型提供统一接口适配。

核心功能：
  - predict_proba: 预测违约概率
  - decision_function: 获取原始 Logit 值
  - predict_proba_batch: 批量预测违约概率
  - decision_function_batch: 批量获取 Logit 值
  - get_feature_importance: 获取特征重要性
  - _detect_capabilities: 动态检测当前模型实例能力

能力检测规则：
  - PREDICT_PROBA:
      模型实现 predict_proba 方法
  - PREDICT_LOG_ODDS:
      模型实现 predict 方法，并支持 prediction_type="RawFormulaVal"
  - FEATURE_IMPORTANCE:
      模型实现 get_feature_importance 方法
  - BATCH_PREDICT:
      模型支持概率预测或 Logit 预测
"""

from collections.abc import Iterable

import numpy as np
import structlog

from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)


class CatBoostAdapter(BaseModelAdapter):
    """CatBoost 模型适配器

    根据当前模型实例动态检测模型能力。
    """

    def __init__(
        self,
        model,
        feature_names=None,
        data_types=None,
    ):
        """初始化适配器

        参数：
            model: CatBoost 模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
        """
        super().__init__(
            model=model,
            feature_names=feature_names,
            data_types=data_types,
        )

        self._validate_model()

    def _detect_capabilities(
        self,
    ) -> ModelCapability:
        """检测当前 CatBoost 模型实例能力

        返回：
            模型能力位掩码
        """
        capabilities = ModelCapability.NONE

        supports_proba = callable(
            getattr(
                self.model,
                "predict_proba",
                None,
            )
        )

        supports_predict = callable(
            getattr(
                self.model,
                "predict",
                None,
            )
        )

        supports_importance = callable(
            getattr(
                self.model,
                "get_feature_importance",
                None,
            )
        )

        if supports_proba:
            capabilities |= (
                ModelCapability.PREDICT_PROBA
            )

        if supports_predict:
            capabilities |= (
                ModelCapability.PREDICT_LOG_ODDS
            )

        if supports_proba or supports_predict:
            capabilities |= (
                ModelCapability.BATCH_PREDICT
            )

        if supports_importance:
            capabilities |= (
                ModelCapability.FEATURE_IMPORTANCE
            )

        return capabilities

    def _validate_model(
        self,
    ) -> None:
        """校验模型

        当前仅支持二分类模型。

        如果模型具有 classes_ 属性，则检查类别数量。

        异常：
            ValueError: 模型类别数量不是 2
        """
        if not hasattr(
            self.model,
            "classes_",
        ):
            return

        class_count = len(
            self.model.classes_
        )

        if class_count != 2:
            raise ValueError(
                f"{self.__class__.__name__}: "
                "仅支持二分类模型，"
                f"当前类别数={class_count}"
            )

        logger.debug(
            "CatBoost 模型校验通过",
            adapter=self.__class__.__name__,
            class_count=class_count,
        )

    def predict_proba(
        self,
        X: np.ndarray,
    ) -> float:
        """预测违约概率

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            正类概率，范围 0 到 1

        异常：
            NotImplementedError: 模型不支持概率预测
            NotImplementedError: 模型不是二分类模型
        """
        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        X = self._ensure_2d(X)

        probabilities = np.asarray(
            self.model.predict_proba(X)
        )

        if (
            probabilities.ndim != 2
            or probabilities.shape[1] != 2
        ):
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "仅支持二分类概率预测，"
                f"当前输出 shape={probabilities.shape}"
            )

        result = float(
            probabilities[0, 1]
        )

        logger.debug(
            "CatBoost 概率预测成功",
            probability=result,
        )

        return result

    def decision_function(
        self,
        X: np.ndarray,
    ) -> float:
        """获取原始 Logit 值

        CatBoost 使用：

            predict(
                X,
                prediction_type="RawFormulaVal",
            )

        获取原始模型输出。

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            Logit 值

        异常：
            NotImplementedError: 模型不支持 Logit 输出
            NotImplementedError: 模型返回多分类结果
        """
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        X = self._ensure_2d(X)

        raw_scores = np.asarray(
            self.model.predict(
                X,
                prediction_type="RawFormulaVal",
            )
        )

        if raw_scores.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 RawFormulaVal，"
                f"当前输出 shape={raw_scores.shape}"
            )

        result = float(
            raw_scores[0]
        )

        logger.debug(
            "CatBoost Logit 预测成功",
            logit=result,
        )

        return result

    def predict_proba_batch(
        self,
        X: np.ndarray,
    ) -> list[float]:
        """批量预测违约概率

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            正类概率列表

        异常：
            NotImplementedError: 模型不支持概率预测
            NotImplementedError: 模型不是二分类模型
        """
        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        X = self._ensure_2d(X)

        probabilities = np.asarray(
            self.model.predict_proba(X)
        )

        if (
            probabilities.ndim != 2
            or probabilities.shape[1] != 2
        ):
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "仅支持二分类概率预测，"
                f"当前输出 shape={probabilities.shape}"
            )

        result = [
            float(probability)
            for probability in probabilities[:, 1]
        ]

        logger.debug(
            "CatBoost 批量概率预测成功",
            sample_count=len(result),
        )

        return result

    def decision_function_batch(
        self,
        X: np.ndarray,
    ) -> list[float]:
        """批量获取原始 Logit 值

        使用 RawFormulaVal 获取批量原始输出。

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            Logit 值列表

        异常：
            NotImplementedError: 模型不支持 Logit 输出
            NotImplementedError: 模型返回多分类结果
        """
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        X = self._ensure_2d(X)

        raw_scores = np.asarray(
            self.model.predict(
                X,
                prediction_type="RawFormulaVal",
            )
        )

        if raw_scores.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 RawFormulaVal，"
                f"当前输出 shape={raw_scores.shape}"
            )

        result = [
            float(raw_score)
            for raw_score in raw_scores
        ]

        logger.debug(
            "CatBoost 批量 Logit 预测成功",
            sample_count=len(result),
        )

        return result

    def get_feature_importance(
        self,
    ) -> dict[str, float]:
        """获取特征重要性

        使用 CatBoost PredictionValuesChange
        作为默认特征重要性度量。

        返回：
            特征重要性字典

        异常：
            NotImplementedError: 当前模型不支持特征重要性
        """
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        importance = np.asarray(
            self.model.get_feature_importance(
                type="PredictionValuesChange",
            )
        )

        logger.debug(
            "获取 CatBoost 特征重要性",
            source="PredictionValuesChange",
        )

        names = self._resolve_feature_names(
            importance_count=len(importance),
        )

        result = {
            name: float(value)
            for name, value in zip(
                names,
                importance,
            )
        }

        logger.debug(
            "CatBoost 特征重要性计算完成",
            feature_count=len(result),
        )

        return result

    def _resolve_feature_names(
        self,
        *,
        importance_count: int,
    ) -> list[str]:
        """解析特征名称

        优先级：
          - 显式传入的 feature_names
          - CatBoost 模型自带的 feature_names_
          - f0、f1、f2 等默认名称

        参数：
            importance_count: 特征数量

        返回：
            特征名称列表
        """
        if self.feature_names:
            return [
                str(name)
                for name in self.feature_names
            ]

        model_feature_names = getattr(
            self.model,
            "feature_names_",
            None,
        )

        if (
            not isinstance(
                model_feature_names,
                str,
            )
            and isinstance(
                model_feature_names,
                Iterable,
            )
        ):
            names = [
                str(name)
                for name in model_feature_names
            ]

            if names:
                return names

        return [
            f"f{index}"
            for index in range(
                importance_count
            )
        ]

    @staticmethod
    def _ensure_2d(
        X: np.ndarray,
    ) -> np.ndarray:
        """确保输入为二维数组

        参数：
            X: 输入数组

        返回：
            二维数组

        异常：
            ValueError: 输入不是一维或二维数组
        """
        if X.ndim == 1:
            return X.reshape(
                1,
                -1,
            )

        if X.ndim != 2:
            raise ValueError(
                "仅支持 1D / 2D numpy 输入，"
                f"当前 ndim={X.ndim}"
            )

        return X