import numpy as np
from src.setup import setup_logger
from pypmml import Model

logger = setup_logger()

class Wrapper:
    def __init__(self, model, model_type: str):
        self.model_type = model_type.lower()

        # 自动识别 PMML 模型
        if isinstance(model, str) and model.endswith(".pmml"):
            logger.info(f"[Wrapper] 正在加载 PMML 模型：{model}")
            model = Model.load(model)
            self.is_pmml = True
        else:
            self.is_pmml = False

        self.model = model

        if not hasattr(model, "predict"):
            raise AttributeError(f"[Wrapper] 模型 {model_type} 缺少 predict() 方法")

        # PMML 模型不需要再注入 predict_proba
        if not self.is_pmml and not hasattr(model, "predict_proba"):
            logger.warning(f"[Wrapper] 模型 {model_type} 缺少 predict_proba()，已基于 predict() 自动生成兼容版本")
            self._predict_proba()

    def _predict_proba(self):
        def _proba(X):
            preds = np.asarray(self.model.predict(X))
            if preds.ndim == 1:
                p = np.clip(preds.astype(float), 0, 1)
                probs = np.column_stack([1 - p, p])
            else:
                probs = preds / np.sum(preds, axis=1, keepdims=True)
            return probs

        setattr(self.model, "predict_proba", _proba)
        logger.info(f"[Wrapper] 已为 {self.model_type} 模型注入 predict_proba() 方法")

    def predict(self, X):
        # PMML 模型 predict 返回 DataFrame，需要转 numpy
        result = self.model.predict(X)
        if hasattr(result, "values"):
            return result.values
        return result

    def predict_proba(self, X):
        if self.is_pmml:
            result = self.model.predict(X, outputProbability=True)
            if hasattr(result, "values"):
                return result.values
            return result
        return self.model.predict_proba(X)[:,1]
