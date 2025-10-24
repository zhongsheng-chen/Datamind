#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
data_mocker.py

生成贷款申请的模拟数据
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from faker import Faker
from src.db_engine import oracle_engine


def generate_data(n_customers=10, n_tax_records=5):
    # --------------------------
    # 生成 loan_application 测试数据
    # --------------------------

    fake = Faker("zh_CN")

    loan_applications = pd.DataFrame({
        "application_id": [f"BA{fake.random_int(10 ** 12, 10 ** 13 - 1)}" for _ in range(n_customers)],
        "customer_id": [str(fake.random_int(10 ** 9, 10 ** 10 - 1)) for _ in range(n_customers)],
        "name": [fake.name() for _ in range(n_customers)],                                                                            # 客户姓名
        "gender": np.random.choice(["男", "女"], size=n_customers),                                                                 # 性别
        "age": np.random.randint(20, 60, size=n_customers),                                                                           # 年龄
        "phone": [fake.phone_number() for _ in range(n_customers)],                                                                   # 电话号码
        "email": [fake.email() for _ in range(n_customers)],                                                                          # 电子邮件
        "address": [fake.address().replace("\n", " ") for _ in range(n_customers)],                                       # 地址
        "income": np.random.randint(3000, 20000, size=n_customers),                                                                   # 收入
        "debt_ratio": np.round(np.random.uniform(0.1, 0.9, size=n_customers), 2),                                   # 债务比率
        "loan_amount": np.random.randint(5000, 300000, size=n_customers),                                                             # 贷款金额
        "existing_loans": np.random.randint(0, 5, size=n_customers),                                                                  # 现有贷款数量
        "marital_status": np.random.choice(["未婚", "已婚", "离异"], size=n_customers),                                               # 婚姻状态
        "education_level": np.random.choice(["高中", "大专", "本科", "硕士", "博士"], size=n_customers),                                # 学历
        "occupation": [fake.job() for _ in range(n_customers)],                                                                        # 职业
        "loan_purpose": np.random.choice(["购房", "购车", "装修", "教育", "消费", "医疗"], size=n_customers),                            # 贷款用途
        "application_date": [fake.date_between(start_date="-2y", end_date="today").strftime('%Y-%m-%d') for _ in range(n_customers)],  # 申请日期
        "status": np.random.choice(["已提交", "审核中", "已批准", "已拒绝"], size=n_customers)                                           # 申请状态
    })

    # --------------------------
    # 生成 tax_transaction 测试数据
    # --------------------------
    tax_list = []
    for cust_id in loan_applications["customer_id"]:
        n_tax = np.random.randint(1, n_tax_records + 1)
        for i in range(n_tax):
            tax_year = datetime.today().year - np.random.randint(0, 3)  # 最近3年
            tax_amount = np.random.randint(500, 20000)
            tax_list.append({
                "tax_id": f"{cust_id}_{i+1}",
                "customer_id": cust_id,
                "tax_year": tax_year,
                "tax_amount": tax_amount
            })

    transactions = pd.DataFrame(tax_list)

    # --------------------------
    # 写入数据库
    # --------------------------
    loan_applications.to_sql("loan_application", oracle_engine, index=False, if_exists="replace")
    transactions.to_sql("tax_transaction", oracle_engine, index=False, if_exists="replace")

    print(f"已生成 {n_customers} 个客户及交易数据，并写入数据库")

# --------------------------
# 脚本入口
# --------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成测试数据")
    parser.add_argument("--n_customers", type=int, default=100, help="客户数量")
    parser.add_argument("--n_tax_records", type=int, default=5, help="每个客户最大交易数量")
    args = parser.parse_args()

    generate_data(n_customers=args.n_customers, n_tax_records=args.n_tax_records)
