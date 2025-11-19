class ScoreTransformer:
    """
    通用打分引擎：根据模型输出概率和请求配置计算信用评分。

    默认逻辑：
      - 高概率代表高风险（分数越低）
      - 评分方向：lower_better（可通过 request["scoring"]["direction"] 改为 higher_better）

    支持配置项：
      - base_score: 基准分（默认 600）
      - pdo: 每翻倍赔率对应的分数变化（默认 50）
      - min_score: 最低分（默认 None，不限制）
      - max_score: 最高分（默认 None，不限制）
      - direction: "lower_better"（默认）或 "higher_better" . lower_better 表示高概率，高风险，分数低
    """

    DEFAULT_BASE_SCORE = 600
    DEFAULT_MIN_SCORE = 320
    DEFAULT_MAX_SCORE = 960
    DEFAULT_DIRECTION = "lower_better"
    DEFAULT_PDO = 50
    _EPS = 1e-6

    @classmethod
    def _extract_params(cls, request: dict):
        """统一从 request 中提取参数"""
        scoring = {}
        if isinstance(request, dict):
            scoring = request.get("scoring", {}) if isinstance(request.get("scoring", {}), dict) else {}
            base_score = scoring.get("base_score", request.get("base_score", cls.DEFAULT_BASE_SCORE))
            pdo = scoring.get("pdo", request.get("pdo", cls.DEFAULT_PDO))
            min_score = scoring.get("min_score", request.get("min_score", cls.DEFAULT_MIN_SCORE))
            max_score = scoring.get("max_score", request.get("max_score", cls.DEFAULT_MAX_SCORE))
            direction = scoring.get("direction", request.get("direction", cls.DEFAULT_DIRECTION))
        else:
            base_score, pdo = cls.DEFAULT_BASE_SCORE, cls.DEFAULT_PDO
            min_score = max_score = None
            direction = "lower_better"

        # 类型安全检查
        try:
            base_score = int(base_score)
        except Exception:
            base_score = cls.DEFAULT_BASE_SCORE

        try:
            pdo = float(pdo)
        except Exception:
            pdo = float(cls.DEFAULT_PDO)
        if pdo <= 0:
            pdo = float(cls.DEFAULT_PDO)

        try:
            min_score = int(min_score) if min_score is not None else None
        except Exception:
            min_score = None

        try:
            max_score = int(max_score) if max_score is not None else None
        except Exception:
            max_score = None

        direction = str(direction).lower().strip()
        if direction not in ("higher_better", "lower_better"):
            direction = "lower_better"

        return base_score, pdo, min_score, max_score, direction

    @classmethod
    def probability_to_score(cls, probability: float, request: dict = None) -> int:
        """根据请求配置计算概率对应的信用分"""
        import math

        base_score, pdo, min_score, max_score, direction = cls._extract_params(request or {})

        # 限制概率范围，避免 log(0)
        p = min(max(float(probability), cls._EPS), 1.0 - cls._EPS)
        odds = p / (1.0 - p)

        # 计算分数
        if direction == "lower_better":
            # 高概率 -> 高风险 -> 分数低
            score = base_score - (pdo / math.log(2)) * math.log(odds)
        else:
            # higher_better: 高概率 -> 分数高
            score = base_score + (pdo / math.log(2)) * math.log(odds)

        # 限定上下界
        if min_score is not None:
            score = max(score, min_score)
        if max_score is not None:
            score = min(score, max_score)

        return int(round(score))

    @staticmethod
    def get_feature_score(model, X):
        """
        获取模型的特征重要性或特征评分

        参数:
            model: sklearn-like 模型或 Pipeline
            X: pd.DataFrame, 输入特征（未经过 Pipeline 预处理）

        返回:
            dict: {feature_name: score}
        """
        import numpy as np

        # 如果是 Pipeline，取最后一步模型
        if hasattr(model, 'steps'):
            final_model = model.steps[-1][1]
            # 尝试获取经过预处理后的特征名
            try:
                X_transformed = model[:-1].transform(X)
                if hasattr(model[:-1], 'get_feature_names_out'):
                    feature_names = model[:-1].get_feature_names_out(X.columns)
                else:
                    feature_names = X.columns
            except Exception:
                # 如果 transform 出错，直接用原始特征
                X_transformed = X.values
                feature_names = X.columns
        else:
            final_model = model
            X_transformed = X.values
            feature_names = X.columns

        # 逻辑回归
        if hasattr(final_model, 'coef_'):
            coefs = final_model.coef_
            if coefs.ndim == 2 and coefs.shape[0] == 1:
                coefs = coefs[0]
            scores = {f: float(coef) for f, coef in zip(feature_names, coefs)}

        # 树模型
        elif hasattr(final_model, 'feature_importances_'):
            importances = final_model.feature_importances_
            scores = {f: float(imp) for f, imp in zip(feature_names, importances)}

        # 回退到 SHAP
        else:
            try:
                import shap
                explainer = shap.Explainer(final_model, X_transformed)
                shap_values = explainer(X_transformed)
                mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
                scores = {f: float(v) for f, v in zip(feature_names, mean_abs_shap)}
            except Exception:
                # 如果 SHAP 也失败
                scores = {f: None for f in feature_names}

        return scores
