#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
service_stress_test.py

对 Datamind BentoML 服务进行并发压测。
支持：
- 指定测试 endpoint（predict / predict_label / predict_proba / predict_score）
- 统计成功率、平均响应时间、P90/P95 延迟、QPS/TPS
- 自动生成随机 payload、serial_number、workflow
- 可选 ab_test_all_run 参数
"""

import argparse
import requests
import random
import statistics
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import time


# =============================
# 全局常量
# =============================

BASE_URL = "http://127.0.0.1:3000"
HEADERS = {"Content-Type": "application/json"}
WORKFLOW_NAME = "demo_loan_approval_workflow"


# =============================
# 随机数据生成
# =============================

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


def random_serial_number(length=15):
    import string
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


# =============================
# 请求发送函数
# =============================

def send_request(base_url: str, endpoint: str, i: int, ab_test_all_run: bool):
    """发送单个请求"""
    payload = random_payload()
    serial_number = random_serial_number()
    url = f"{base_url.rstrip('/')}/{endpoint}"

    request_data = {
        "request": {
            "workflow": WORKFLOW_NAME,
            "features": payload,
            "serial_number": serial_number,
            "threshold": 0.56
        }
    }

    if ab_test_all_run:
        request_data["request"]["ab_test_all_run"] = True

    start = time()
    try:
        response = requests.post(url, json=request_data, headers=HEADERS, timeout=5)
        latency = time() - start
        return response.status_code, latency
    except Exception:
        return 0, time() - start  # 0 表示失败


# =============================
# 并发压测执行
# =============================

def run_concurrent_test(base_url: str, endpoint: str, num_requests=500, max_workers=20, ab_test_all_run=False):
    """并发压测"""
    latencies = []
    success = 0
    start_all = time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(send_request, base_url, endpoint, i, ab_test_all_run)
            for i in range(num_requests)
        ]
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

    print("=== Datamind 服务压测报告 ===")
    print(f"服务地址             : {base_url}")
    print(f"测试接口             : /{endpoint}")
    print(f"ab_test_all_run 模式 : {ab_test_all_run}")
    print(f"请求总数             : {num_requests}")
    print(f"并发线程数           : {max_workers}")
    print(f"成功请求数           : {success}")
    print(f"失败请求数           : {num_requests - success}")
    print(f"成功率               : {success_rate:.2f}%")
    print(f"平均响应时间         : {avg_latency:.4f}s")
    print(f"P90 响应时间         : {p90:.4f}s")
    print(f"P95 响应时间         : {p95:.4f}s")
    print(f"最短响应时间         : {min(latencies):.4f}s")
    print(f"最长响应时间         : {max(latencies):.4f}s")
    print(f"总耗时               : {total_time:.4f}s")
    print(f"QPS (请求数/秒)      : {qps:.2f}")
    print(f"TPS (成功数/秒)      : {tps:.2f}")
    print("==============================")


# =============================
# 主入口
# =============================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Datamind 并发压测工具")
    parser.add_argument("--url", type=str, default=BASE_URL,
                        help="服务地址（默认：http://127.0.0.1:3000）")
    parser.add_argument("--endpoint", type=str, default="predict",
                        help="接口名称：predict | predict_label | predict_proba | predict_score")
    parser.add_argument("--count", type=int, default=1000, help="请求总数")
    parser.add_argument("--workers", type=int, default=20, help="并发线程数")
    parser.add_argument("--ab_test_all_run", action="store_true", help="是否启用 ab_test_all_run 模式")
    args = parser.parse_args()

    print(f"开始压测接口: {args.url}/{args.endpoint} ...")
    run_concurrent_test(
        base_url=args.url,
        endpoint=args.endpoint,
        num_requests=args.count,
        max_workers=args.workers,
        ab_test_all_run=args.ab_test_all_run
    )
