#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

URL = "http://127.0.0.1:3000/predict"
HEADERS = {"Content-Type": "application/json"}

# 生成随机 payload
def random_payload():
    return {
        "age": random.randint(20, 60),
        "income": random.randint(5000, 20000),
        "debt_ratio": round(random.uniform(0, 1), 2),
        "loan_amount": random.randint(1000, 10000),
        "existing_loans": random.randint(0, 5),
        "total_tax_records": random.randint(0, 20),
        "total_tax_amount": random.randint(0, 50000),
        "avg_tax_amount": random.randint(0, 10000),
        "max_tax_amount": random.randint(0, 15000),
        "min_tax_amount": random.randint(0, 5000),
        "tax_amount_std": random.randint(0, 5000),
        "loan_to_income_ratio": round(random.uniform(0, 2), 2),
        "existing_loans_ratio": round(random.uniform(0, 1), 2)
    }

# 发送单个请求
def send_request(i):
    payload = random_payload()
    start = time()
    response = requests.post(URL, json=payload, headers=HEADERS)
    latency = time() - start
    return response.status_code, latency

# 并发压测
def run_concurrent_test(num_requests=100, max_workers=20):
    latencies = []
    success = 0
    start_all = time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(send_request, i) for i in range(num_requests)]
        for future in as_completed(futures):
            status, latency = future.result()
            latencies.append(latency)
            if status == 200:
                success += 1

    total_time = time() - start_all
    avg_latency = sum(latencies) / len(latencies)
    qps = num_requests / total_time  # 每秒请求数
    tps = success / total_time       # 每秒成功请求数

    print(f"总请求数: {num_requests}")
    print(f"成功请求数: {success}")
    print(f"失败请求数: {num_requests - success}")
    print(f"平均响应时间: {avg_latency:.4f}s")
    print(f"最短响应时间: {min(latencies):.4f}s")
    print(f"最长响应时间: {max(latencies):.4f}s")
    print(f"总耗时: {total_time:.4f}s")
    print(f"QPS (每秒请求数): {qps:.2f}")
    print(f"TPS (每秒成功请求数): {tps:.2f}")

if __name__ == "__main__":
    run_concurrent_test(num_requests=1000, max_workers=20)
