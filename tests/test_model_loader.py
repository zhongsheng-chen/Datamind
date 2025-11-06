import unittest
import numpy as np
from src.model_loader import ModelLoader

class TestModelLoader(unittest.TestCase):
    """
    单元测试 ModelLoader 支持的所有框架和文件格式
    """

    # 这里填写你的模型路径和对应框架/类型
    model_paths = {
        "catboost": "models/demo_loan_scorecard_cat_20250930.cbm",
        "catboost_fraud": "models/demo_loan_fraud_detection_cat_20250930.cbm",
        "lightgbm": "models/demo_loan_scorecard_lgbm_20250930.pkl",
        "xgboost": "models/demo_loan_scorecard_xgb_20250930.pkl",
        "logistic_regression": "models/demo_loan_scorecard_lr_20250930.pkl",
        "decision_tree": "models/demo_loan_scorecard_dt_20250930.pkl",
        "random_forest": "models/demo_loan_scorecard_rf_20250930.pkl"
    }

    def setUp(self):
        # 随机输入，假设模型特征数为13，可根据实际修改
        self.n_samples = 2
        self.n_features = 13
        self.X_test = np.random.rand(self.n_samples, self.n_features)

    def test_models(self):
        for model_type, path in self.model_paths.items():
            with self.subTest(model_type=model_type):
                try:
                    loader = ModelLoader(path, framework=self._infer_framework(model_type))

                    # 测试 predict()
                    preds = loader.predict(self.X_test)
                    self.assertEqual(len(preds), self.n_samples)
                    print(f"[{model_type}] predict OK:", preds)

                    # 测试 predict_proba()
                    probs = loader.predict_proba(self.X_test)
                    self.assertEqual(probs.shape[0], self.n_samples)
                    self.assertTrue(probs.shape[1] >= 2)
                    print(f"[{model_type}] predict_proba OK:\n", probs)

                except Exception as e:
                    self.fail(f"[{model_type}] 测试失败: {e}")

    def _infer_framework(self, model_type):
        """
        根据 model_type 推断框架
        """
        if model_type.startswith("catboost"):
            return "catboost"
        elif model_type == "lightgbm":
            return "lightgbm"
        elif model_type == "xgboost":
            return "xgboost"
        elif model_type in ["logistic_regression", "decision_tree", "random_forest"]:
            return "sklearn"
        else:
            raise ValueError(f"无法推断 {model_type} 的框架")

if __name__ == "__main__":
    unittest.main()
