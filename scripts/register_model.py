# scripts/register_model.py
# !/usr/bin/env python
"""
命令行模型注册工具

使用方法:
    python register_model.py --file model.pkl --id credit_model --type logistic_regression ...
"""

import argparse
import requests
import json
import os


def main():
    parser = argparse.ArgumentParser(description='注册模型到Datamind')
    parser.add_argument('--file', required=True, help='模型文件路径')
    parser.add_argument('--model-id', required=True, help='模型ID')
    parser.add_argument('--task-type', required=True, choices=['scoring', 'fraud_detection'])
    parser.add_argument('--model-type', required=True,
                        choices=['decision_tree', 'random_forest', 'xgboost',
                                 'lightgbm', 'logistic_regression'])
    parser.add_argument('--framework', required=True,
                        choices=['sklearn', 'xgboost', 'lightgbm', 'torch',
                                 'tensorflow', 'onnx', 'catboost'])
    parser.add_argument('--version', required=True, help='版本号')
    parser.add_argument('--feature-names', required=True, help='特征名称，逗号分隔')
    parser.add_argument('--description', help='模型描述')
    parser.add_argument('--tags', help='标签，JSON格式')
    parser.add_argument('--server', default='http://localhost:8000', help='服务器地址')

    args = parser.parse_args()

    # 准备请求数据
    with open(args.file, 'rb') as f:
        files = {'model_file': f}
        data = {
            'model_id': args.model_id,
            'task_type': args.task_type,
            'model_type': args.model_type,
            'framework': args.framework,
            'version': args.version,
            'feature_names': json.dumps(args.feature_names.split(',')),
            'description': args.description or '',
            'tags': args.tags or '{}'
        }

        # 发送请求
        response = requests.post(
            f"{args.server}/v1/models/register",
            data=data,
            files=files
        )

        if response.status_code == 201:
            print("✅ 模型注册成功!")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❌ 注册失败: {response.text}")


if __name__ == '__main__':
    main()