# datamind/core/model/adapters/sklearn.py

"""Sklearn 模型适配器

为 Sklearn 模型提供统一接口适配。
"""

import structlog
import numpy as np

from datamind.core.model.adapters.base import BaseModelAdapter
from datamind.core.capability import ModelCapability

logger = structlog.get_logger(__name__)


class SklearnAdapter(BaseModelAdapter):
    """Sklearn 模型适配器

    能力声明：
        - FEATURE_IMPORTANCE: 特征重要性
        - SHAP: SHAP 解释
    """

    SUPPORTED_CAPABILITIES = (
        ModelCapability.FEATURE_IMPORTANCE
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

    def _validate_model(self):
        """校验模型

        异常：
            ValueError: Datamind 仅支持二分类模型
        """
        if hasattr(self.model, "classes_"):
            class_count = len(self.model.classes_)

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
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "predict_proba"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 predict_proba 方法"
            )

        proba = self.model.predict_proba(X)
        result = float(proba[0, 1])

        logger.debug("预测概率成功 | 概率=%s", result)
        return result

    def decision_function(self, X: np.ndarray) -> float:
        """获取原始 logit 值

        参数：
            X: 输入特征数组，形状为 (1, n_features)

        返回：
            logit 值（原始模型输出）

        异常：
            NotImplementedError: 模型不支持 decision_function 方法
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "decision_function"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 decision_function 方法"
            )

        logit = float(self.model.decision_function(X)[0])
        logger.debug("获取 logit 成功 | logit=%s", logit)
        return logit

    def predict_proba_batch(self, X: np.ndarray) -> list[float]:
        """批量预测违约概率

        参数：
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回：
            概率列表，长度 n_samples

        异常：
            NotImplementedError: 模型不支持 predict_proba 方法
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "predict_proba"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 predict_proba 方法"
            )

        probs = self.model.predict_proba(X)
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
            NotImplementedError: 模型不支持 decision_function 方法
            NotImplementedError: 暂不支持多分类 decision_function 方法
        """
        X = self._ensure_2d(X)

        if not hasattr(self.model, "decision_function"):
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持 decision_function 方法"
            )

        logits = self.model.decision_function(X)

        if logits.ndim != 1:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 暂不支持多分类 decision_function 方法"
            )

        result = [float(x) for x in logits]

        logger.debug("批量获取 logit 成功 | 样本数=%d", len(result))
        return result

    def get_feature_importance(self) -> dict[str, float]:
        """获取特征重要性

        支持的特征重要性来源：
            - feature_importances_（树模型）
            - coef_（线性模型，取绝对值）

        返回：
            特征重要性字典

        异常：
            NotImplementedError: 模型不支持特征重要性
            NotImplementedError: 暂不支持多分类 coef_ 特征重要性
        """
        self.require_capability(ModelCapability.FEATURE_IMPORTANCE)

        if hasattr(self.model, "feature_importances_"):
            imp = self.model.feature_importances_
            logger.debug("获取特征重要性 | 来源=feature_importances_")

        elif hasattr(self.model, "coef_"):
            coef = np.asarray(self.model.coef_)

            logger.debug("获取特征重要性 | 来源=coef_ | shape=%s", coef.shape)

            if coef.ndim == 1:
                imp = np.abs(coef)

            elif coef.ndim == 2 and coef.shape[0] == 1:
                imp = np.abs(coef[0])

            else:
                raise NotImplementedError(
                    f"{self.__class__.__name__}: 暂不支持多分类 coef_ 特征重要性"
                )

        else:
            raise NotImplementedError(
                f"{self.__class__.__name__}: 模型不支持特征重要性"
            )

        if not self.feature_names:
            result = {
                f"f{i}": float(v)
                for i, v in enumerate(imp)
            }
        else:
            result = {
                name: float(v)
                for name, v in zip(self.feature_names, imp)
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