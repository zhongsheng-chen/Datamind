# datamind/core/model/adapters/sklearn.py

"""Sklearn 模型适配器

为 Sklearn 模型提供统一接口适配。

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
      模型实现 decision_function 方法
  - FEATURE_IMPORTANCE:
      模型具有 feature_importances_ 或 coef_ 属性
  - BATCH_PREDICT:
      模型支持概率预测或 Logit 预测
"""

import numpy as np
import structlog

from datamind.core.capability import ModelCapability
from datamind.core.model.adapters.base import BaseModelAdapter

logger = structlog.get_logger(__name__)


class SklearnAdapter(BaseModelAdapter):
    """Sklearn 模型适配器

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
            model: Sklearn 模型
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
        """检测当前 Sklearn 模型实例能力

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

        supports_logit = callable(
            getattr(
                self.model,
                "decision_function",
                None,
            )
        )

        if supports_proba:
            capabilities |= (
                ModelCapability.PREDICT_PROBA
            )

        if supports_logit:
            capabilities |= (
                ModelCapability.PREDICT_LOG_ODDS
            )

        if supports_proba or supports_logit:
            capabilities |= (
                ModelCapability.BATCH_PREDICT
            )

        if (
            hasattr(
                self.model,
                "feature_importances_",
            )
            or hasattr(
                self.model,
                "coef_",
            )
        ):
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
            "Sklearn 模型校验通过",
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
            "概率预测成功",
            probability=result,
        )

        return result

    def decision_function(
        self,
        X: np.ndarray,
    ) -> float:
        """获取原始 Logit 值

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            Logit 值

        异常：
            NotImplementedError:
                模型不支持 decision_function
            NotImplementedError:
                模型返回多分类结果
        """
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        X = self._ensure_2d(X)

        logits = np.asarray(
            self.model.decision_function(X)
        )

        if logits.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 decision_function，"
                f"当前输出 shape={logits.shape}"
            )

        result = float(
            logits[0]
        )

        logger.debug(
            "Logit 预测成功",
            logit=result,
        )

        return result

    def predict_proba_batch(
        self,
        X: np.ndarray,
    ) -> list[float]:
        """批量预测违约概率

        参数：
            X: 输入数组，形状为
               (n_samples, n_features)

        返回：
            正类概率列表

        异常：
            NotImplementedError:
                模型不支持概率预测
            NotImplementedError:
                模型不是二分类模型
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
            "批量概率预测成功",
            sample_count=len(result),
        )

        return result

    def decision_function_batch(
        self,
        X: np.ndarray,
    ) -> list[float]:
        """批量获取原始 Logit 值

        参数：
            X: 输入数组，形状为
               (n_samples, n_features)

        返回：
            Logit 值列表

        异常：
            NotImplementedError:
                模型不支持 decision_function
            NotImplementedError:
                模型返回多分类结果
        """
        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        X = self._ensure_2d(X)

        logits = np.asarray(
            self.model.decision_function(X)
        )

        if logits.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "暂不支持多分类 decision_function，"
                f"当前输出 shape={logits.shape}"
            )

        result = [
            float(logit)
            for logit in logits
        ]

        logger.debug(
            "批量 Logit 预测成功",
            sample_count=len(result),
        )

        return result

    def get_feature_importance(
        self,
    ) -> dict[str, float]:
        """获取特征重要性

        支持以下来源：
          - feature_importances_: 树模型
          - coef_: 线性模型，使用系数绝对值

        返回：
            特征重要性字典

        异常：
            NotImplementedError:
                模型不支持特征重要性
            NotImplementedError:
                coef_ 为多分类结构
        """
        self.require_capability(
            ModelCapability.FEATURE_IMPORTANCE
        )

        if hasattr(
            self.model,
            "feature_importances_",
        ):
            importance = np.asarray(
                self.model.feature_importances_
            )

            logger.debug(
                "获取特征重要性",
                source="feature_importances_",
            )

        elif hasattr(
            self.model,
            "coef_",
        ):
            coefficients = np.asarray(
                self.model.coef_
            )

            logger.debug(
                "获取特征重要性",
                source="coef_",
                shape=coefficients.shape,
            )

            if coefficients.ndim == 1:
                importance = np.abs(
                    coefficients
                )

            elif (
                coefficients.ndim == 2
                and coefficients.shape[0] == 1
            ):
                importance = np.abs(
                    coefficients[0]
                )

            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__}: "
                    "暂不支持多分类 coef_ 特征重要性，"
                    f"当前 shape={coefficients.shape}"
                )

        else:
            raise NotImplementedError(
                f"{self.__class__.__name__}: "
                "模型不支持特征重要性"
            )

        if self.feature_names:
            result = {
                name: float(value)
                for name, value in zip(
                    self.feature_names,
                    importance,
                )
            }

        else:
            result = {
                f"f{index}": float(value)
                for index, value in enumerate(
                    importance
                )
            }

        logger.debug(
            "特征重要性计算完成",
            feature_count=len(result),
        )

        return result

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
            ValueError:
                输入不是一维或二维数组
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