#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试评分卡服务

测试 Datamind 评分卡服务的所有 API 端点：
  - /predict: 评分预测（支持特征贡献解释）
  - /health: 健康检查
  - /models: 列出已加载模型

使用方法：
    python test_service.py

环境要求：
    - 服务已启动：bentoml serve datamind.serving.scoring_service:ScoringService --reload
    - 端口：3000
"""

import requests
import json
import time
from typing import Dict, Any, List, Tuple

# 服务配置
BASE_URL = "http://localhost:3000"
TIMEOUT = 10


class Colors:
    """终端颜色输出"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    """打印成功信息"""
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    """打印错误信息"""
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg: str):
    """打印信息"""
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_warning(msg: str):
    """打印警告"""
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_header(msg: str):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 60}{Colors.END}\n")


def print_json(data: Dict[str, Any], indent: int = 2):
    """格式化打印 JSON"""
    print(json.dumps(data, ensure_ascii=False, indent=indent))


def check_service() -> bool:
    """检查服务是否可用"""
    print_header("检查服务状态")

    try:
        response = requests.post(f"{BASE_URL}/health", json={}, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                status = data.get("data", {}).get("status", "unknown")
                print_success(f"服务运行中: {status}")
                return True
        print_error(f"服务响应异常: {response.status_code}")
        return False
    except requests.ConnectionError:
        print_error("无法连接到服务，请确保服务已启动")
        print_info("启动命令: bentoml serve datamind.serving.scoring_service:ScoringService --reload")
        return False
    except Exception as e:
        print_error(f"检查服务失败: {e}")
        return False


def test_health() -> Dict[str, Any]:
    """测试健康检查接口"""
    print_header("健康检查 (/health)")

    try:
        response = requests.post(f"{BASE_URL}/health", json={}, timeout=TIMEOUT)
        data = response.json()

        print_json(data)

        if data.get("code") == 0:
            health_data = data.get("data", {})
            print_success(f"服务状态: {health_data.get('status', 'unknown')}")
            print_success(f"已加载模型数: {health_data.get('loaded_models', 0)}")
            return data
        else:
            print_error(f"健康检查失败: {data.get('message')}")
            return data

    except Exception as e:
        print_error(f"健康检查异常: {e}")
        return {"code": -1, "message": str(e)}


def test_models() -> Dict[str, Any]:
    """测试列出模型接口"""
    print_header("列出模型 (/models)")

    try:
        response = requests.post(f"{BASE_URL}/models", json={}, timeout=TIMEOUT)
        data = response.json()

        print_json(data)

        if data.get("code") == 0:
            models = data.get("data", {}).get("models", [])
            print_success(f"共加载 {len(models)} 个模型")
            for model in models:
                print(f"  - {model.get('model_id')}: {model.get('model_name')} v{model.get('version')}")
            return data
        else:
            print_error(f"列出模型失败: {data.get('message')}")
            return data

    except Exception as e:
        print_error(f"列出模型异常: {e}")
        return {"code": -1, "message": str(e)}


def test_predict(
        application_id: str,
        features: Dict[str, Any],
        return_details: bool = True,
        model_id: str = None,
        ab_test_id: str = None
) -> Dict[str, Any]:
    """
    测试评分预测接口

    参数:
        application_id: 申请ID
        features: 特征字典
        return_details: 是否返回详细特征贡献
        model_id: 指定模型ID（可选）
        ab_test_id: A/B测试ID（可选）

    返回:
        响应数据
    """
    # 构建请求
    request_body = {
        "application_id": application_id,
        "features": features,
        "return_details": return_details
    }

    if model_id:
        request_body["model_id"] = model_id
    if ab_test_id:
        request_body["ab_test_id"] = ab_test_id

    payload = {"request": request_body}

    try:
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=TIMEOUT)
        return response.json()

    except Exception as e:
        print_error(f"预测请求异常: {e}")
        return {"code": -1, "message": str(e)}


def analyze_result(result: Dict[str, Any], case_name: str) -> Tuple[bool, Dict[str, Any]]:
    """
    分析预测结果

    参数:
        result: 预测响应
        case_name: 测试用例名称

    返回:
        (是否成功, 分析结果)
    """
    if result.get("code") != 0:
        print_error(f"{case_name}: {result.get('message', '未知错误')}")
        return False, result

    data = result.get("data", {})
    score = data.get("score", 0)
    probability = data.get("probability", 0)
    trace = data.get("trace", {})
    latency = trace.get("latency_ms", 0)

    # 判断风险等级
    if probability >= 0.5:
        risk_level = f"{Colors.RED}高风险{Colors.END}"
    elif probability >= 0.1:
        risk_level = f"{Colors.YELLOW}中等风险{Colors.END}"
    else:
        risk_level = f"{Colors.GREEN}低风险{Colors.END}"

    # 判断分数合理性
    if 0 <= score <= 1000:
        score_valid = True
    else:
        score_valid = False

    # 判断概率合理性
    if 0 <= probability <= 1:
        prob_valid = True
    else:
        prob_valid = False

    # 获取验证信息
    explain = data.get("explain", {})
    validation = explain.get("details", {}).get("validation", {})
    score_match = validation.get("score_match", False)

    analysis = {
        "score": score,
        "probability": probability,
        "latency_ms": latency,
        "risk_level": risk_level,
        "score_valid": score_valid,
        "prob_valid": prob_valid,
        "score_match": score_match,
        "model_id": data.get("model", {}).get("id"),
        "model_version": data.get("model", {}).get("version")
    }

    # 打印结果
    print(f"\n{Colors.BOLD}{case_name}{Colors.END}")
    print(f"  分数: {score:.2f} {'✓' if score_valid else '✗'}")
    print(f"  概率: {probability:.6f} ({probability * 100:.4f}%) {'✓' if prob_valid else '✗'}")
    print(f"  风险等级: {risk_level}")
    print(f"  耗时: {latency:.2f}ms")
    print(f"  模型ID: {analysis['model_id']}")
    print(f"  模型版本: {analysis['model_version']}")
    print(f"  评分一致性: {'✓' if score_match else '✗'}")

    # 如果有特征贡献，打印前3个主要因子
    if "explain" in data and data["explain"].get("type") == "scorecard":
        details = data["explain"].get("details", {})
        score_contrib = details.get("score", {})
        if score_contrib:
            sorted_contrib = sorted(score_contrib.items(), key=lambda x: abs(x[1]), reverse=True)
            print(f"  主要影响因子:")
            for feature, contrib in sorted_contrib[:3]:
                direction = "↑" if contrib > 0 else "↓"
                print(f"    - {feature}: {contrib:+.2f} {direction}")

    return score_match, analysis


def run_tests():
    """运行所有测试"""
    print_header("Datamind 评分卡服务测试")

    # 1. 检查服务状态
    if not check_service():
        return

    # 2. 健康检查
    test_health()

    # 3. 列出模型
    test_models()

    # 4. 定义测试用例
    test_cases = [
        {
            "name": f"{Colors.GREEN}低风险客户{Colors.END}",
            "application_id": "TEST_LOW_RISK",
            "features": {
                "age": 55,
                "income": 150000,
                "debt_ratio": 0.15,
                "credit_history": 820,
                "employment_years": 20,
                "loan_amount": 30000
            },
            "expected_risk": "low"
        },
        {
            "name": f"{Colors.YELLOW}中等风险客户{Colors.END}",
            "application_id": "TEST_MEDIUM_RISK",
            "features": {
                "age": 35,
                "income": 50000,
                "debt_ratio": 0.3,
                "credit_history": 720,
                "employment_years": 5,
                "loan_amount": 100000
            },
            "expected_risk": "medium"
        },
        {
            "name": f"{Colors.RED}高风险客户{Colors.END}",
            "application_id": "TEST_HIGH_RISK",
            "features": {
                "age": 20,
                "income": 20000,
                "debt_ratio": 0.8,
                "credit_history": 400,
                "employment_years": 1,
                "loan_amount": 500000
            },
            "expected_risk": "high"
        },
        {
            "name": "年轻高收入客户",
            "application_id": "TEST_YOUNG_HIGH_INCOME",
            "features": {
                "age": 25,
                "income": 120000,
                "debt_ratio": 0.2,
                "credit_history": 650,
                "employment_years": 3,
                "loan_amount": 200000
            },
            "expected_risk": "medium"
        },
        {
            "name": "老年低收入客户",
            "application_id": "TEST_OLD_LOW_INCOME",
            "features": {
                "age": 65,
                "income": 25000,
                "debt_ratio": 0.1,
                "credit_history": 750,
                "employment_years": 30,
                "loan_amount": 50000
            },
            "expected_risk": "low"
        }
    ]

    # 5. 运行测试用例
    print_header("评分预测测试")

    results = []
    for test_case in test_cases:
        print(f"\n{'-' * 40}")

        result = test_predict(
            application_id=test_case["application_id"],
            features=test_case["features"],
            return_details=True
        )

        success, analysis = analyze_result(result, test_case["name"])
        results.append({
            "name": test_case["name"],
            "success": success,
            "analysis": analysis,
            "expected_risk": test_case["expected_risk"]
        })

    # 6. 测试不返回详细特征贡献
    print_header("不返回详细特征贡献测试")

    result = test_predict(
        application_id="TEST_NO_DETAILS",
        features={
            "age": 35,
            "income": 50000,
            "debt_ratio": 0.3,
            "credit_history": 720,
            "employment_years": 5,
            "loan_amount": 100000
        },
        return_details=False
    )

    if result.get("code") == 0:
        data = result.get("data", {})
        print_success(f"预测成功: 分数={data.get('score', 0):.2f}, 概率={data.get('probability', 0):.6f}")
        if "explain" not in data:
            print_info("特征贡献已省略（return_details=False）")
    else:
        print_error(f"预测失败: {result.get('message')}")

    # 7. 测试重新加载模型（可选）
    print_header("重新加载模型测试")

    reload_payload = {"request": {"model_id": "MDL_20260402202506_F425BA35"}}
    try:
        response = requests.post(f"{BASE_URL}/reload_model", json=reload_payload, timeout=TIMEOUT)
        reload_result = response.json()

        if reload_result.get("code") == 0:
            print_success(f"模型重新加载成功: {reload_result.get('data', {}).get('message')}")
        else:
            print_warning(f"重新加载失败: {reload_result.get('message')}")
    except Exception as e:
        print_warning(f"重新加载测试跳过: {e}")

    # 8. 打印测试总结
    print_header("测试总结")

    total = len(results)
    passed = sum(1 for r in results if r["success"])

    print(f"总测试数: {total}")
    print(f"通过: {Colors.GREEN}{passed}{Colors.END}")
    print(f"失败: {Colors.RED}{total - passed}{Colors.END}")
    print(f"通过率: {passed / total * 100:.1f}%\n")

    # 打印详细结果
    print("详细结果:")
    for r in results:
        status = "✓" if r["success"] else "✗"
        color = Colors.GREEN if r["success"] else Colors.RED
        analysis = r["analysis"]
        print(f"  {color}{status}{Colors.END} {r['name']}: "
              f"分数={analysis['score']:.2f}, "
              f"概率={analysis['probability']:.4f}, "
              f"耗时={analysis['latency_ms']:.2f}ms")

    print("\n" + "=" * 60)
    if passed == total:
        print_success("所有测试通过！🎉")
    else:
        print_warning(f"{total - passed} 个测试失败，请检查服务状态")
    print("=" * 60)


def run_single_test():
    """运行单个预测测试（交互式）"""
    print_header("单次预测测试")

    print("请输入特征值（留空使用默认值）:")

    age = input("年龄 (默认35): ").strip()
    age = int(age) if age else 35

    income = input("收入 (默认50000): ").strip()
    income = int(income) if income else 50000

    debt_ratio = input("负债率 (默认0.3): ").strip()
    debt_ratio = float(debt_ratio) if debt_ratio else 0.3

    credit_history = input("信用历史 (默认720): ").strip()
    credit_history = int(credit_history) if credit_history else 720

    employment_years = input("工作年限 (默认5): ").strip()
    employment_years = int(employment_years) if employment_years else 5

    loan_amount = input("贷款金额 (默认100000): ").strip()
    loan_amount = int(loan_amount) if loan_amount else 100000

    return_details = input("返回详细特征贡献? (y/n, 默认y): ").strip().lower()
    return_details = return_details != 'n'

    features = {
        "age": age,
        "income": income,
        "debt_ratio": debt_ratio,
        "credit_history": credit_history,
        "employment_years": employment_years,
        "loan_amount": loan_amount
    }

    print_info(f"请求特征: {json.dumps(features, ensure_ascii=False)}")

    result = test_predict(
        application_id=f"MANUAL_{int(time.time())}",
        features=features,
        return_details=return_details
    )

    if result.get("code") == 0:
        data = result.get("data", {})
        print_success(f"预测成功!")
        print(f"  信用评分: {data.get('score', 0):.2f}")
        print(f"  违约概率: {data.get('probability', 0):.6f} ({data.get('probability', 0) * 100:.4f}%)")

        if return_details and "explain" in data:
            details = data["explain"].get("details", {})
            score_contrib = details.get("score", {})
            if score_contrib:
                print(f"\n  特征贡献:")
                sorted_contrib = sorted(score_contrib.items(), key=lambda x: abs(x[1]), reverse=True)
                for feature, contrib in sorted_contrib:
                    direction = "↑" if contrib > 0 else "↓"
                    print(f"    {feature}: {contrib:+.2f} {direction}")
    else:
        print_error(f"预测失败: {result.get('message')}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        run_single_test()
    else:
        run_tests()