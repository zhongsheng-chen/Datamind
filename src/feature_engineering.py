import pandas as pd
import numpy as np
from .db_engine import oracle_engine

def get_features(application_ids):
    placeholders = ','.join([f':id{i}' for i in range(len(application_ids))])
    sql = f"""
    SELECT a.application_id, a.age, a.income, a.debt_ratio,
           SUM(t.txn_amount) AS total_txn,
           COUNT(t.txn_id) AS txn_count
    FROM loan_application a
    LEFT JOIN transaction t
      ON a.customer_id = t.customer_id
     AND t.txn_date >= ADD_MONTHS(SYSDATE, -6)
    WHERE a.application_id IN ({placeholders})
    GROUP BY a.application_id, a.age, a.income, a.debt_ratio
    """
    params = {f'id{i}': val for i, val in enumerate(application_ids)}
    df = pd.read_sql(sql, oracle_engine, params=params)
    df['txn_amount_log'] = np.log1p(df['total_txn'])
    return df
