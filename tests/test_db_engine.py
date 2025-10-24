import unittest
import pandas as pd
from src.db_engine import oracle_engine, postgres_engine
from sqlalchemy.exc import SQLAlchemyError

class TestDBConnection(unittest.TestCase):
    def test_oracle_connection(self):
        try:
            df = pd.read_sql("SELECT 1 FROM dual", oracle_engine)
            self.assertEqual(df.iloc[0,0], 1)
        except SQLAlchemyError as e:
            self.fail(f"Oracle connection failed: {e}")

    def test_postgres_connection(self):
        try:
            df = pd.read_sql("SELECT 1", postgres_engine)
            self.assertEqual(df.iloc[0,0], 1)
        except SQLAlchemyError as e:
            self.fail(f"PostgreSQL connection failed: {e}")

if __name__ == "__main__":
    unittest.main()
