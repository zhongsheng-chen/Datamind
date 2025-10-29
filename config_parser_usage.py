#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from src.config_parser import config, Config


def main():
    print("=== 使用全局 config 实例 ===")

    # 1️⃣ 数据库配置
    print("\n--- 数据库配置 ---")
    oracle_cfg = config.get_databases("oracle")
    print("Oracle Host:", oracle_cfg.get("host"))
    print("Oracle User:", oracle_cfg.get("user"))

    postgres_cfg = config.get_databases("postgres")
    print("Postgres Host:", postgres_cfg.get("host"))
    print("Postgres User:", postgres_cfg.get("user"))

    # 2️⃣ 日志配置
    print("\n--- 日志配置 ---")
    log_cfg = config.get_logging()
    print("Logger Name:", log_cfg.get("name"))
    print("Logger Level:", log_cfg.get("level"))

    # 3️⃣ 特征集
    print("\n--- 特征集 ---")
    loan_features = config.get_features("demo_loan_features")
    print("Loan Features:", loan_features)

    # 4️⃣ 模型信息
    print("\n--- 模型信息 ---")
    lr_model = config.get_model("demo_loan_scorecard_lr_20250930")
    if lr_model:
        print("Model Name:", lr_model.get("model_name"))
        print("Framework:", lr_model.get("framework"))
        print("Features:", lr_model.get("features"))

    models = config.list_models()
    print(models)

    # 5️⃣ 业务工作流
    print("\n--- 业务工作流 ---")
    approval_wf = config.get_business_workflow("demo_loan_approval_workflow")
    print("Business Name:", approval_wf.name)
    print("Description:", approval_wf.description)

    # 遍历步骤
    for step in approval_wf.steps:
        print(f"\nStep: {step.name}")
        print("Modules:", [m.get("name") for m in step.modules])
        print("Models in Step:", step.models)

    # 6️⃣ 获取 AB 测试信息
    print("\n--- AB 测试信息 ---")
    ab_info = approval_wf.get_ab_test_info()
    for model_name, ab_cfg in ab_info.items():
        print(f"{model_name}: {ab_cfg}")

    # 7️⃣ 使用自定义 Config 实例
    print("\n=== 使用自定义 Config 实例 ===")
    cfg = Config(cfg_path="config/config.yaml")  # 可以换成其他测试配置
    fraud_models = cfg.get("models")["fraud"]
    print("Fraud Models:", [m["model_name"] for m in fraud_models])

    disbursement_wf = cfg.get_business_workflow("demo_loan_disbursement_workflow")
    for step in disbursement_wf.steps:
        print(f"Disbursement Step: {step.name}, Modules: {[m.get('name') for m in step.modules]}")


if __name__ == "__main__":
    main()
