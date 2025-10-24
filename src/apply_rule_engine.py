from src.rule_engine import RuleEngine
from datetime import datetime

# 定义外部函数
external_funcs = {
    "not_in_internal_blacklist": lambda id_number: id_number not in blacklist_internal,
    "not_in_external_blacklist": lambda id_number, phone_number: True,
    "not_in_sanctions_list": lambda id_number, full_name: True,
    "check_tax_record": lambda id_number: True,
    "check_judicial_record": lambda id_number, full_name: True,
    "check_housing_fund": lambda id_number: True,
    "check_business_registration": lambda id_number, business_name: True,
    "check_farm_loan_risk": lambda id_number, crop_area, annual_farm_output: True,
    "check_credit_card_usage": lambda id_number: True,
    "check_business_risk": lambda id_number, annual_turnover, industry_code: True,
    "is_employee": lambda id_number: True,
}

engine = RuleEngine(external_funcs=external_funcs)
applicant = {
    "age": 30,
    "income": 8000,
    "employment_status": "full_time",
    "id_number": "123456789012345678",
    "loan_purpose": "travel",
    "crop_area": 120,
    "annual_farm_output": 60000,
    "annual_turnover": 250000,
    "score_probability": 0.8,
    "employment_date": datetime(2022,1,1),
    "overdue_last12m": [0,0,1,0]
}

results = engine.execute(applicant)
print(results)
