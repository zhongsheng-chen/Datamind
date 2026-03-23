# scripts/start_bentoml_service.py

"""BentoML 服务启动脚本

支持评分卡和反欺诈模型的 BentoML 服务管理。

使用示例:
    # 启动评分卡服务（开发模式）
    python scripts/start_bentoml_service.py scoring --dev

    # 启动反欺诈服务（开发模式，指定端口）
    python scripts/start_bentoml_service.py fraud --dev --port 3001

    # 启动所有服务（生产模式）
    python scripts/start_bentoml_service.py all --prod --workers 4

    # 构建 Bento 包
    python scripts/start_bentoml_service.py build scoring

    # 容器化服务
    python scripts/start_bentoml_service.py containerize fraud
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 使用项目已有的 BASE_DIR
from datamind.config import get_settings, BASE_DIR

from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs, bootstrap_info
from datamind.core.logging.debug import debug_print

install_bootstrap_logger()


class BentoServiceManager:
    """BentoML 服务管理器"""

    SERVICES = {
        'scoring': {
            'path': 'datamind.serving.scoring_service:ScoringService',  # 使用类名
            'port': 3000,
            'workers': 2,
            'desc': '评分卡模型服务'
        },
        'fraud': {
            'path': 'datamind.serving.fraud_service:FraudService',  # 使用类名
            'port': 3001,
            'workers': 2,
            'desc': '反欺诈模型服务'
        },
        'all': {
            'path': None,
            'port': 3000,
            'workers': 4,
            'desc': '所有服务'
        }
    }

    def __init__(self):
        self.settings = get_settings()
        self.base_dir = BASE_DIR
        self.bentofile = self.base_dir / 'datamind' / 'serving' / 'bentofile.yaml'
        bootstrap_info(f"服务管理器初始化，环境: {self.settings.app.env}")

    def _print_banner(self, service: str, port: int, workers: int, dev: bool, prod: bool):
        """打印启动横幅"""
        mode = '生产模式' if prod else ('开发模式(热重载)' if dev else '标准模式')

        print(f"\n{'=' * 55}")
        print(f"  Datamind {self.SERVICES[service]['desc']}")
        print(f"{'=' * 55}")
        print(f"  环境: {self.settings.app.env}")
        print(f"  端口: {port}")
        print(f"  模式: {mode}")
        if prod:
            print(f"  进程: {workers}")
        print(f"  PID: {os.getpid()}")
        print(f"{'=' * 55}\n")

    def _build_cmd(self, service: str, port: int, workers: int, dev: bool, prod: bool) -> list:
        """构建 bentoml 命令"""
        cmd = ['bentoml', 'serve']

        if prod:
            cmd.extend(['--production', '--workers', str(workers)])
        elif dev:
            cmd.extend(['--reload'])

        cmd.extend(['--host', '0.0.0.0'])
        cmd.extend(['--port', str(port)])

        if service == 'all':
            cmd.extend(['--bentofile', str(self.bentofile)])
        else:
            cmd.append(self.SERVICES[service]['path'])

        return cmd

    def serve(self, service: str, port: int = None, workers: int = None, dev: bool = False, prod: bool = False) -> int:
        """启动服务"""
        if service not in self.SERVICES:
            print(f"错误: 未知服务 '{service}'，可选: {list(self.SERVICES.keys())}")
            return 1

        config = self.SERVICES[service]
        port = port or config['port']
        workers = workers or config['workers']

        # 生产模式检查
        if prod and service == 'all' and not self.bentofile.exists():
            print(f"错误: bentofile.yaml 不存在: {self.bentofile}")
            return 1

        # 构建命令
        cmd = self._build_cmd(service, port, workers, dev, prod)

        # 设置环境变量
        env = os.environ.copy()
        env['PYTHONPATH'] = str(self.base_dir)
        env['DATAMIND_ENV'] = self.settings.app.env

        # 打印信息
        self._print_banner(service, port, workers, dev, prod)
        debug_print('BentoServiceManager', f"命令: {' '.join(cmd)}")

        bootstrap_info(f"启动服务: {service}", extra={
            "service": service,
            "port": port,
            "mode": "prod" if prod else ("dev" if dev else "std"),
            "environment": self.settings.app.env
        })

        try:
            subprocess.run(cmd, env=env, check=True)
            return 0
        except KeyboardInterrupt:
            print(f"\n{service} 服务已停止")
            bootstrap_info(f"{service} 服务已停止")
            return 0
        except subprocess.CalledProcessError as e:
            print(f"错误: 服务启动失败: {e}")
            bootstrap_info(f"服务启动失败: {e}")
            return 1

    def build(self, service: str, version: str = None) -> int:
        """构建 Bento 包"""
        if service not in self.SERVICES or service == 'all':
            print("错误: 请指定具体服务 (scoring/fraud)")
            return 1

        config = self.SERVICES[service]
        version = version or self.settings.app.version

        cmd = [
            'bentoml', 'build',
            '--version', version,
            '--service', config['path'],
            str(self.base_dir)
        ]

        print(f"\n{'=' * 55}")
        print(f"  构建 {config['desc']} Bento 包")
        print(f"{'=' * 55}")
        print(f"  服务: {config['path']}")
        print(f"  版本: {version}")
        print(f"{'=' * 55}\n")

        bootstrap_info(f"构建 Bento 包: {service} v{version}")

        try:
            subprocess.run(cmd, check=True)
            print(f"✓ {service} Bento 包构建成功")
            bootstrap_info(f"Bento 包构建成功: {service} v{version}")
            return 0
        except subprocess.CalledProcessError as e:
            print(f"✗ {service} Bento 包构建失败: {e}")
            bootstrap_info(f"Bento 包构建失败: {e}", level="ERROR")
            return 1

    def containerize(self, service: str, tag: str = None) -> int:
        """容器化服务"""
        if service not in self.SERVICES or service == 'all':
            print("错误: 请指定具体服务 (scoring/fraud)")
            return 1

        # 获取 bento 名称
        bento_name = f"{service}_service"

        cmd = [
            'bentoml', 'containerize',
            f"{bento_name}:latest",
            '-t', tag or f"datamind/{bento_name}:{self.settings.app.version}"
        ]

        print(f"\n{'=' * 55}")
        print(f"  容器化 {self.SERVICES[service]['desc']}")
        print(f"{'=' * 55}")
        print(f"  Bento: {bento_name}:latest")
        print(f"  镜像: {tag or f'datamind/{bento_name}:{self.settings.app.version}'}")
        print(f"{'=' * 55}\n")

        bootstrap_info(f"容器化服务: {service} -> {tag}")

        try:
            subprocess.run(cmd, check=True)
            print(f"✓ {service} 容器化成功")
            bootstrap_info(f"容器化成功: {service}")
            return 0
        except subprocess.CalledProcessError as e:
            print(f"✗ {service} 容器化失败: {e}")
            bootstrap_info(f"容器化失败: {e}", level="ERROR")
            return 1

    def list_services(self) -> int:
        """列出可用服务"""
        print("\nDatamind BentoML 服务:")
        print("-" * 55)
        for name, config in self.SERVICES.items():
            port = config.get('port', 'N/A')
            if name == 'all':
                print(f"  {name:8} - {config['desc']}")
            else:
                print(f"  {name:8} - {config['desc']} (端口: {port})")
        print("-" * 55)
        print(f"  bentofile: {self.bentofile}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Datamind BentoML 服务管理",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动评分卡服务（开发模式）
  python scripts/start_bentoml_service.py scoring --dev

  # 启动反欺诈服务
  python scripts/start_bentoml_service.py fraud --port 3001

  # 启动所有服务（生产模式）
  python scripts/start_bentoml_service.py all --prod --workers 4

  # 构建 Bento 包
  python scripts/start_bentoml_service.py build scoring

  # 容器化服务
  python scripts/start_bentoml_service.py containerize fraud

  # 列出服务
  python scripts/start_bentoml_service.py list
        """
    )

    parser.add_argument(
        'command',
        choices=['scoring', 'fraud', 'all', 'build', 'containerize', 'list'],
        help='命令或服务名称'
    )
    parser.add_argument('--port', type=int, help='服务端口')
    parser.add_argument('--workers', type=int, help='工作进程数')
    parser.add_argument('--dev', action='store_true', help='开发模式（热重载）')
    parser.add_argument('--prod', action='store_true', help='生产模式')
    parser.add_argument('--version', help='版本号（用于 build）')
    parser.add_argument('--tag', help='Docker 镜像标签（用于 containerize）')

    args = parser.parse_args()

    manager = BentoServiceManager()

    if args.command == 'list':
        return manager.list_services()
    elif args.command == 'build':
        return manager.build(args.command, args.version)
    elif args.command == 'containerize':
        return manager.containerize(args.command, args.tag)
    else:
        return manager.serve(
            service=args.command,
            port=args.port,
            workers=args.workers,
            dev=args.dev,
            prod=args.prod
        )


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        flush_bootstrap_logs()