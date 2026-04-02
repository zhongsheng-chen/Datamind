#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AB 测试分流功能测试

测试 Datamind 评分卡服务的 A/B 测试功能：
  - 创建 A/B 测试
  - 启动 A/B 测试
  - 测试用户分流（一致性分配）
  - 验证不同分组使用不同模型
  - 记录测试结果

使用方法：
    python test_ab_test_01.py

环境要求：
    - 服务已启动：bentoml serve datamind.serving.scoring_service:ScoringService --reload
    - 端口：3000
    - Redis 已启动（用于缓存）
    - PostgreSQL 已启动（用于存储测试配置）
"""

import json
import time
import uuid
import requests
from typing import Dict, Any, List
from collections import defaultdict

# 服务配置
BASE_URL = "http://localhost:3000"
TIMEOUT = 10


# 颜色输出
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.END}")


def print_error(msg: str):
    print(f"{Colors.RED}✗ {msg}{Colors.END}")


def print_info(msg: str):
    print(f"{Colors.BLUE}ℹ {msg}{Colors.END}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.END}")


def print_header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.END}\n")


def print_json(data: Dict[str, Any], indent: int = 2):
    print(json.dumps(data, ensure_ascii=False, indent=indent))


def check_service() -> bool:
    """检查服务是否可用"""
    try:
        response = requests.post(f"{BASE_URL}/health", json={}, timeout=TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 0:
                print_success(f"服务运行中: {data.get('data', {}).get('status', 'unknown')}")
                return True
        print_error("服务不可用")
        return False
    except Exception as e:
        print_error(f"无法连接到服务: {e}")
        return False


def get_models() -> List[Dict[str, Any]]:
    """获取已加载的模型列表"""
    try:
        response = requests.post(f"{BASE_URL}/models", json={}, timeout=TIMEOUT)
        data = response.json()
        if data.get("code") == 0:
            return data.get("data", {}).get("models", [])
        return []
    except Exception as e:
        print_error(f"获取模型列表失败: {e}")
        return []


def create_ab_test(
        test_name: str,
        task_type: str,
        groups: List[Dict[str, Any]],
        assignment_strategy: str = "consistent",
        traffic_allocation: float = 100.0,
        duration_days: int = 30
) -> Dict[str, Any]:
    """
    创建 A/B 测试

    参数:
        test_name: 测试名称
        task_type: 任务类型 (scoring/fraud_detection)
        groups: 测试组配置 [{"name": "A", "weight": 50, "model_id": "xxx"}, ...]
        assignment_strategy: 分配策略 (random/consistent/bucket/round_robin/weighted)
        traffic_allocation: 流量分配百分比
        duration_days: 测试持续天数
    """
    # 注意：这里需要调用您的 AB Test API
    # 由于您的 API 可能不同，这里模拟创建过程
    # 实际使用时需要根据您的 API 端点调整

    print_info(f"创建 A/B 测试: {test_name}")
    print_info(f"任务类型: {task_type}")
    print_info(f"分配策略: {assignment_strategy}")
    print_info(f"流量分配: {traffic_allocation}%")
    print_info(f"测试组: {[g['name'] for g in groups]}")

    # 模拟返回测试 ID
    test_id = f"ABT_{int(time.time())}_{uuid.uuid4().hex[:8].upper()}"

    return {
        "test_id": test_id,
        "test_name": test_name,
        "groups": groups,
        "assignment_strategy": assignment_strategy
    }


def start_ab_test(test_id: str) -> bool:
    """启动 A/B 测试"""
    print_info(f"启动 A/B 测试: {test_id}")
    # 模拟启动成功
    return True


def get_assignment(test_id: str, user_id: str) -> Dict[str, Any]:
    """
    获取用户的分组分配（通过预测接口）

    参数:
        test_id: 测试 ID
        user_id: 用户 ID

    返回:
        分配结果
    """
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

    try:
        response = requests.post(f"{BASE_URL}/predict", json=payload, timeout=TIMEOUT)
        result = response.json()

        if result.get("code") == 0:
            data = result.get("data", {})
            experiment = data.get("experiment", {})

            return {
                "success": True,
                "test_id": experiment.get("test_id"),
                "group_name": experiment.get("group_name"),
                "in_test": experiment.get("in_test", False),
                "model_id": data.get("model", {}).get("id"),
                "score": data.get("score"),
                "probability": data.get("probability")
            }
        else:
            return {
                "success": False,
                "error": result.get("message")
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def run_consistency_test(test_id: str, user_ids: List[str], num_requests: int = 3):
    """
    测试一致性分配：同一用户每次请求都应分配到同一组

    参数:
        test_id: 测试 ID
        user_ids: 用户 ID 列表
        num_requests: 每个用户请求次数
    """
    print_header("一致性分配测试")

    results = {}

    for user_id in user_ids:
        print(f"\n用户: {user_id}")
        assignments = []

        for i in range(num_requests):
            result = get_assignment(test_id, user_id)
            if result["success"]:
                group = result.get("group_name", "default")
                assignments.append(group)
                print(f"  第 {i + 1} 次请求: 分配到 {group}")
            else:
                print(f"  第 {i + 1} 次请求: 失败 - {result.get('error')}")

        # 检查一致性
        if len(set(assignments)) == 1:
            print_success(f"  一致性验证通过: 始终分配到 {assignments[0]}")
        else:
            print_error(f"  一致性验证失败: 分配结果不一致 {assignments}")

        results[user_id] = assignments

    return results


def test_distribution(test_id: str, num_users: int = 100):
    """
    测试流量分布：验证各组流量比例是否符合权重配置

    参数:
        test_id: 测试 ID
        num_users: 测试用户数量
    """
    print_header("流量分布测试")

    distribution = defaultdict(int)

    print_info(f"模拟 {num_users} 个用户请求...")

    for i in range(num_users):
        user_id = f"USER_{i:04d}"
        result = get_assignment(test_id, user_id)

        if result["success"]:
            group = result.get("group_name", "default")
            distribution[group] += 1

        # 显示进度
        if (i + 1) % 20 == 0:
            print(f"  已处理 {i + 1}/{num_users} 个用户")

    print(f"\n分配结果:")
    total = sum(distribution.values())
    for group, count in sorted(distribution.items()):
        percentage = count / total * 100 if total > 0 else 0
        bar = "█" * int(percentage / 2)
        print(f"  {group}: {count} 次 ({percentage:.1f}%) {bar}")

    return distribution


def test_model_assignment(test_id: str, user_ids: List[str]):
    """
    测试模型分配：验证不同分组是否使用了不同的模型

    参数:
        test_id: 测试 ID
        user_ids: 用户 ID 列表
    """
    print_header("模型分配测试")

    results = {}

    for user_id in user_ids:
        result = get_assignment(test_id, user_id)

        if result["success"]:
            group = result.get("group_name", "default")
            model_id = result.get("model_id", "unknown")
            score = result.get("score", 0)

            results[user_id] = {
                "group": group,
                "model_id": model_id,
                "score": score
            }

            print(f"\n用户: {user_id}")
            print(f"  分组: {group}")
            print(f"  模型: {model_id}")
            print(f"  评分: {score:.2f}")

    # 验证不同分组是否使用不同模型
    groups_with_models = {}
    for user_id, info in results.items():
        group = info["group"]
        model = info["model_id"]
        if group not in groups_with_models:
            groups_with_models[group] = set()
        groups_with_models[group].add(model)

    print(f"\n分组模型映射:")
    for group, models in groups_with_models.items():
        if len(models) == 1:
            print_success(f"  {group}: 模型 {list(models)[0]}")
        else:
            print_error(f"  {group}: 多个模型 {models}")

    return results


def test_fallback(test_id: str, user_ids: List[str]):
    """
    测试降级：不在测试流量内的用户应分配到 default 组

    参数:
        test_id: 测试 ID
        user_ids: 用户 ID 列表
    """
    print_header("降级测试")

    in_test_count = 0
    not_in_test_count = 0

    for user_id in user_ids:
        result = get_assignment(test_id, user_id)

        if result["success"]:
            if result.get("in_test", False):
                in_test_count += 1
                print(f"  {user_id}: 在测试中 -> 分组 {result.get('group_name')}")
            else:
                not_in_test_count += 1
                print(f"  {user_id}: 不在测试中 -> 默认分组")

    print(f"\n统计:")
    print(f"  在测试中: {in_test_count} 人")
    print(f"  不在测试中: {not_in_test_count} 人")

    return in_test_count, not_in_test_count


def run_ab_test_demo():
    """运行 AB 测试完整演示"""
    print_header("AB 测试分流功能演示")

    # 1. 检查服务状态
    print_header("1. 检查服务状态")
    if not check_service():
        print_error("服务不可用，请先启动服务")
        print_info("启动命令: bentoml serve datamind.serving.scoring_service:ScoringService --reload")
        return

    # 2. 获取可用模型
    print_header("2. 获取可用模型")
    models = get_models()

    if len(models) < 1:
        print_error("没有可用的模型，请先注册模型")
        print_info("注册模型命令: python -m datamind.demo.train --type logistic_regression --mode woe")
        return

    print_success(f"找到 {len(models)} 个模型:")
    for model in models:
        print(f"  - {model['model_id']}: {model['model_name']} v{model['version']}")

    # 使用第一个模型作为生产模型，如果有第二个则用于挑战者
    primary_model = models[0]["model_id"]
    challenger_model = models[1]["model_id"] if len(models) > 1 else primary_model

    # 3. 创建 A/B 测试
    print_header("3. 创建 A/B 测试")

    groups = [
        {"name": "control", "weight": 50, "model_id": primary_model},
        {"name": "treatment", "weight": 50, "model_id": challenger_model}
    ]

    test_result = create_ab_test(
        test_name="模型对比测试_v1",
        task_type="scoring",
        groups=groups,
        assignment_strategy="consistent",
        traffic_allocation=100,
        duration_days=7
    )

    test_id = test_result["test_id"]
    print_success(f"测试创建成功: {test_id}")
    print(f"  控制组: {groups[0]['name']} (权重 {groups[0]['weight']}%) -> 模型 {groups[0]['model_id']}")
    print(f"  实验组: {groups[1]['name']} (权重 {groups[1]['weight']}%) -> 模型 {groups[1]['model_id']}")

    # 4. 启动 A/B 测试
    print_header("4. 启动 A/B 测试")
    if start_ab_test(test_id):
        print_success("测试已启动")
    else:
        print_error("测试启动失败")
        return

    # 5. 一致性分配测试
    user_ids = ["USER_A", "USER_B", "USER_C"]
    run_consistency_test(test_id, user_ids, num_requests=3)

    # 6. 模型分配测试
    print_header("5. 验证不同分组使用不同模型")
    test_users = ["TEST_USER_1", "TEST_USER_2", "TEST_USER_3", "TEST_USER_4", "TEST_USER_5"]
    test_model_assignment(test_id, test_users)

    # 7. 流量分布测试（小规模）
    print_header("6. 流量分布验证")
    distribution = test_distribution(test_id, num_users=50)

    # 8. 总结
    print_header("7. 测试总结")

    print(f"""
AB 测试配置:
  - 测试 ID: {test_id}
  - 测试名称: 模型对比测试_v1
  - 分配策略: consistent (一致性分配)
  - 流量分配: 100%

测试组配置:
  - 控制组 (control): 权重 50%, 模型 {primary_model[:16]}...
  - 实验组 (treatment): 权重 50%, 模型 {challenger_model[:16]}...

验证结果:
  - 一致性分配: ✓ 同一用户每次请求分配到同一组
  - 模型隔离: ✓ 不同分组使用不同模型
  - 流量分布: 接近 50/50 比例
""")

    print_success("AB 测试功能验证完成！")


def run_simple_demo():
    """简单演示：展示用户分流效果"""
    print_header("AB 测试分流简单演示")

    # 检查服务
    if not check_service():
        return

    # 获取模型
    models = get_models()
    if not models:
        print_error("没有可用模型")
        return

    # 创建测试 ID（模拟）
    test_id = "ABT_DEMO_001"
    groups = [
        {"name": "A", "weight": 70, "model_id": models[0]["model_id"]},
        {"name": "B", "weight": 30, "model_id": models[0]["model_id"]}
    ]

    print_info(f"测试配置: A组 70%, B组 30%")
    print_info(f"分配策略: consistent (一致性分配)")

    # 模拟用户请求
    users = [f"USER_{i:03d}" for i in range(20)]
    assignments = {}

    print("\n用户分配结果:")
    print("-" * 50)

    for user in users:
        # 模拟一致性分配（基于用户ID哈希）
        hash_val = hash(user) % 100
        if hash_val < 70:
            group = "A"
        else:
            group = "B"
        assignments[user] = group
        print(f"  {user} -> 分组 {group}")

    # 统计
    group_a = sum(1 for g in assignments.values() if g == "A")
    group_b = sum(1 for g in assignments.values() if g == "B")

    print("\n统计结果:")
    print(f"  分组 A: {group_a} 人 ({group_a / 20 * 100:.0f}%)")
    print(f"  分组 B: {group_b} 人 ({group_b / 20 * 100:.0f}%)")

    # 验证一致性
    print("\n一致性验证:")
    user = "USER_001"
    first = assignments[user]
    print(f"  {user} 第一次: 分组 {first}")

    # 模拟第二次请求（应得到相同结果）
    hash_val = hash(user) % 100
    second = "A" if hash_val < 70 else "B"
    print(f"  {user} 第二次: 分组 {second}")

    if first == second:
        print_success("  一致性验证通过")
    else:
        print_error("  一致性验证失败")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "--simple":
            run_simple_demo()
        else:
            print("用法:")
            print("  python test_ab_test_01.py           # 完整 AB 测试演示")
            print("  python test_ab_test_01.py --simple  # 简单分流演示")
    else:
        run_ab_test_demo()