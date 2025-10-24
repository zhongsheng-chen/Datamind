import unittest
import pandas as pd
from src.db_engine import postgres_engine
from sqlalchemy.exc import SQLAlchemyError

class TestResultWriter(unittest.TestCase):
    def test_write_decision_result(self):
        result_df = pd.DataFrame([{
            "application_id": 99999,
            "business_type": "personal_loan",
            "features": str({"age":30,"income":10000,"debt_ratio":0.3}),
            "probability_of_default": 0.123,
            "final_decision": "approve"
        }])
        try:
            result_df.to_sql("decision_results", postgres_engine, if_exists="append", index=False)
        except SQLAlchemyError as e:
            self.fail(f"Writing decision result failed: {e}")

if __name__ == "__main__":
    unittest.main()
