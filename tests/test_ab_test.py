#!/usr/bin/env python3
"""调试 AB 测试分配"""

import requests
import json

BASE_URL = "http://localhost:3000"


def test_ab_assignment():
    """测试 AB 测试分配"""

    # 测试用户
    test_users = ["USER_001", "USER_002", "USER_003"]

    # 测试 ID（使用您创建的实际测试 ID）
    test_id = "ABT_DEMO_001"

    print("=" * 60)
    print("AB 测试分配调试")
    print("=" * 60)
    print(f"测试 ID: {test_id}\n")

    for user_id in test_users:
        print(f"用户: {user_id}")

        payload = {
            "request": {
                "application_id": user_id,
                "features": {
                    "age": 35,
                    "income": 50000,
                    "debt_ratio": 0.3,
                    "credit_history": 720,
                    "employment_years": 5,
                    "loan_amount": 100000
                },
                "ab_test_id": test_id,
                "return_details": False
            }
        }

        response = requests.post(f"{BASE_URL}/predict", json=payload)
        result = response.json()

        print(f"  响应码: {result.get('code')}")

        if result.get("code") == 0:
            data = result.get("data", {})

            # 打印所有可能包含 AB 测试信息的字段
            print(f"  experiment: {data.get('experiment')}")
            print(f"  ab_test_info: {data.get('ab_test_info')}")
            print(f"  model_id: {data.get('model', {}).get('id')}")
            print(f"  score: {data.get('score')}")
        else:
            print(f"  错误: {result.get('message')}")

        print()

    print("=" * 60)


def check_ab_test_config():
    """检查 AB 测试配置"""
    print("=" * 60)
    print("检查 AB 测试配置")
    print("=" * 60)

    # 直接调用 AB 测试管理器的接口（如果有）
    # 这里假设有一个查询测试配置的接口

    # 或者直接查询数据库
    print("请检查数据库中的 AB 测试配置:")
    print("  SELECT * FROM ab_test_configs WHERE test_id = 'ABT_1775138367_FAE9C6F8';")

    print("\n检查 Redis 缓存:")
    print("  redis-cli KEYS 'ab_test:*'")

    print("\n检查模型部署配置:")
    print("  SELECT * FROM model_deployments WHERE environment = 'production';")


if __name__ == "__main__":
    test_ab_assignment()
    # check_ab_test_config()