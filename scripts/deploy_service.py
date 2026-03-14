# datamind/scripts/deploy_service.py

import subprocess
import sys
from pathlib import Path
import argparse
import yaml


def deploy_service(service_type: str, environment: str):
    """部署BentoML服务"""

    print(f"部署 {service_type} 服务到 {environment} 环境...")

    # 构建Bento
    print("构建Bento包...")
    subprocess.run(["bentoml", "build"], cwd="serving", check=True)

    # 容器化
    print("容器化服务...")
    subprocess.run(
        ["bentoml", "containerize", "datamind-models:latest"],
        check=True
    )

    # 部署到目标环境
    if environment == "docker":
        subprocess.run([
            "docker", "run", "-d",
            "--name", f"datamind-{service_type}",
            "-p", "3001:3000" if service_type == "scoring" else "3002:3000",
            "-e", f"SERVICE_TYPE={service_type}",
            "-e", "ENVIRONMENT=production",
            "datamind-models:latest"
        ], check=True)

    elif environment == "kubernetes":
        # 生成K8s配置
        generate_k8s_config(service_type)

    print(f"{service_type} 服务部署完成")


def generate_k8s_config(service_type: str):
    """生成Kubernetes配置"""
    config = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": f"datamind-{service_type}",
            "labels": {
                "app": "datamind",
                "service": service_type
            }
        },
        "spec": {
            "replicas": 3,
            "selector": {
                "matchLabels": {
                    "app": "datamind",
                    "service": service_type
                }
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "datamind",
                        "service": service_type
                    }
                },
                "spec": {
                    "containers": [{
                        "name": service_type,
                        "image": "datamind-models:latest",
                        "ports": [{"containerPort": 3000}],
                        "env": [
                            {"name": "SERVICE_TYPE", "value": service_type},
                            {"name": "ENVIRONMENT", "value": "production"}
                        ],
                        "resources": {
                            "requests": {
                                "cpu": "500m",
                                "memory": "1Gi"
                            },
                            "limits": {
                                "cpu": "1000m",
                                "memory": "2Gi"
                            }
                        }
                    }]
                }
            }
        }
    }

    with open(f"k8s-{service_type}.yaml", "w") as f:
        yaml.dump(config, f)

    print(f"K8s配置文件已生成: k8s-{service_type}.yaml")
    print("执行以下命令部署:")
    print(f"kubectl apply -f k8s-{service_type}.yaml")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="部署BentoML服务")
    parser.add_argument("service", choices=["scoring", "fraud", "all"],
                        help="服务类型")
    parser.add_argument("--env", choices=["docker", "kubernetes"],
                        default="docker", help="部署环境")

    args = parser.parse_args()

    if args.service == "all":
        deploy_service("scoring", args.env)
        deploy_service("fraud", args.env)
    else:
        deploy_service(args.service, args.env)