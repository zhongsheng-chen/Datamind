#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
service_stress_test.py

用于对 BentoML 服务进行并发压测。
支持统计成功率、平均响应时间、P90/P95 延迟、QPS/TPS 等指标。
"""

import requests
import random
import statistics
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time

# URL = "http://127.0.0.1:3000/predict"
URL = "http://100.92.47.128:3000/predict"
HEADERS = {"Content-Type": "application/json"}

# === 随机生成 payload ===
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
        "existing_loans_ratio": round(random.uniform(0, 1), 2),
    }

# === 发送单个请求 ===
def send_request(i):
    payload = random_payload()
    start = time()
    try:
        response = requests.post(
            URL,
            json={"request": {"payload": payload, "threshold": 0.5}},
            headers=HEADERS,
            timeout=5
        )
        latency = time() - start
        if response.status_code != 200:
            print("请求失败:", response.text)
        return response.status_code, latency
    except Exception as e:
        print(f"请求异常: {e}")
        return 0, time() - start  # 0 代表请求失败

# === 并发压测 ===
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
    avg_latency = statistics.mean(latencies)
    p90 = np.percentile(latencies, 90)
    p95 = np.percentile(latencies, 95)
    qps = num_requests / total_time
    tps = success / total_time
    success_rate = success / num_requests * 100

    print("\n=== 🚀 压测结果报告 ===")
    print(f"请求总数         : {num_requests}")
    print(f"并发线程数       : {max_workers}")
    print(f"成功请求数       : {success}")
    print(f"失败请求数       : {num_requests - success}")
    print(f"成功率           : {success_rate:.2f}%")
    print(f"平均响应时间     : {avg_latency:.4f}s")
    print(f"P90 响应时间     : {p90:.4f}s")
    print(f"P95 响应时间     : {p95:.4f}s")
    print(f"最短响应时间     : {min(latencies):.4f}s")
    print(f"最长响应时间     : {max(latencies):.4f}s")
    print(f"总耗时           : {total_time:.4f}s")
    print(f"QPS (请求数/秒)  : {qps:.2f}")
    print(f"TPS (成功数/秒)  : {tps:.2f}")
    print("============================\n")

if __name__ == "__main__":
    run_concurrent_test(num_requests=1000, max_workers=20)
