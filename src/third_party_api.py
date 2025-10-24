import requests

def tax_check_api(applicant_id):
    resp = requests.get(f"https://api.tax.gov/check/{applicant_id}")
    # 假设返回 {"status": "ok"} 或 {"status": "violation"}
    return resp.json().get("status") == "ok"

def judicial_check_api(applicant_id):
    resp = requests.get(f"https://api.judicial.gov/check/{applicant_id}")
    return resp.json().get("status") == "ok"

def housing_fund_check_api(applicant_id):
    resp = requests.get(f"https://api.socialfund.gov/check/{applicant_id}")
    return resp.json().get("status") == "ok"

def business_registration_api(applicant_id):
    resp = requests.get(f"https://api.business.gov/check/{applicant_id}")
    return resp.json().get("status") == "ok"
