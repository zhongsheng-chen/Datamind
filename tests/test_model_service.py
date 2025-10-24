import unittest
import pandas as pd
import bentoml
from src.utils import load_config

class TestModelService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_config()
        cls.xgb_model_path = config["model_registry"]["xgboost"]

    def test_model_loading(self):
        model = bentoml.load(self.xgb_model_path)
        self.assertIsNotNone(model)

    def test_model_inference(self):
        model = bentoml.load(self.xgb_model_path)
        test_df = pd.DataFrame([{"age":30,"income":10000,"debt_ratio":0.3}])
        runner = model.to_runner()
        result = runner.predict.run(test_df)
        self.assertIsNotNone(result)

if __name__ == "__main__":
    unittest.main()
