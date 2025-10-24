import unittest
from unittest.mock import patch
import pandas as pd
import numpy as np
from src.feature_engineering import get_features

class TestFeatureEngineering(unittest.TestCase):

    @patch("src.feature_engineering.pd.read_sql")
    def test_get_features(self, mock_read_sql):
        """测试 get_features 函数逻辑"""

        # 模拟 Oracle 返回的数据
        mock_data = pd.DataFrame({
            "application_id": [1, 2],
            "age": [25, 30],
            "income": [5000, 7000],
            "debt_ratio": [0.2, 0.3],
            "total_txn": [1000, 2000],
            "txn_count": [10, 15]
        })
        mock_read_sql.return_value = mock_data

        # 调用 get_features
        application_ids = [1, 2]
        result = get_features(application_ids)

        # 检查返回类型
        self.assertIsInstance(result, pd.DataFrame)

        # 检查列是否存在
        for col in ["application_id", "age", "income", "debt_ratio", "total_txn", "txn_count", "txn_amount_log"]:
            self.assertIn(col, result.columns)

        # 检查 txn_amount_log 计算是否正确
        expected_log = np.log1p(mock_data["total_txn"])
        self.assertTrue(np.allclose(result["txn_amount_log"], expected_log))

        # 检查数据行数是否一致
        self.assertEqual(len(result), len(mock_data))

if __name__ == "__main__":
    unittest.main()
