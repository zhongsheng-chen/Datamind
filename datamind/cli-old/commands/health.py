# Datamind/datamind/cli/commands/health.py

"""健康检查命令行命令

提供系统健康状态的检查功能，包括 API 服务、数据库、Redis 等组件的健康状态。

功能特性：
  - 检查 API 服务健康状态（响应时间、版本、环境）
  - 检查数据库连接（PostgreSQL）
  - 检查 Redis 连接（版本、内存使用、连接数）
  - 检查已加载模型数量
  - 支持检查所有组件

命令列表：
  - health check: 检查 API 服务健康状态
  - health db: 检查数据库连接
  - health redis: 检查 Redis 连接
  - health all: 检查所有服务

检查项说明（health check）：
  - 服务状态：API 服务是否正常
  - 响应时间：API 响应耗时（毫秒）
  - 版本信息：当前服务版本
  - 运行环境：development/testing/staging/production
  - 数据库状态：数据库连接是否正常
  - 已加载模型：当前内存中已加载的模型数量

使用示例：
  # 检查 API 服务
  datamind health check

  # 检查 API 服务（自定义主机和端口）
  datamind health check --host 192.168.1.100 --port 8080

  # 检查数据库
  datamind health db

  # 检查 Redis
  datamind health redis

  # 检查所有服务
  datamind health all

返回值说明：
  - 成功：返回 0，打印 ✅ 或绿色文字
  - 失败：返回非 0，打印 ❌ 或红色文字
"""

import click
import requests
from datetime import datetime

from datamind.cli.utils.printer import print_table, print_success, print_error
from datamind.config import settings


@click.group(name='health')
def health():
    """健康检查命令"""
    pass


@health.command(name='check')
@click.option('--host', default='localhost', help='API主机')
@click.option('--port', default=8000, help='API端口')
@click.option('--timeout', default=5, help='超时时间(秒)')
def check_health(host, port, timeout):
    """检查API服务健康状态"""
    url = f"http://{host}:{port}/health"

    try:
        click.echo(f"检查服务健康状态: {url}")

        start_time = datetime.now()
        response = requests.get(url, timeout=timeout)
        duration = (datetime.now() - start_time).total_seconds() * 1000

        if response.status_code == 200:
            data = response.json()

            print_success(f"服务正常 (响应时间: {duration:.0f}ms)")

            info_table = [
                ['状态', data.get('status', 'unknown')],
                ['版本', data.get('version', 'unknown')],
                ['环境', data.get('env', 'unknown')],
                ['时间戳', data.get('timestamp', 'unknown')],
                ['请求ID', data.get('request_id', 'unknown')]
            ]

            print_table(['项', '值'], info_table)

            # 数据库状态
            db_health = data.get('database', {})
            if db_health.get('status') == 'healthy':
                print_success("数据库连接正常")
            else:
                print_error("数据库连接异常")

            # 模型状态
            models = data.get('models', {})
            click.echo(f"\n已加载模型: {models.get('loaded', 0)} 个")

        else:
            print_error(f"服务异常 (HTTP {response.status_code})")

    except requests.exceptions.ConnectionError:
        print_error(f"无法连接到服务: {url}")
    except requests.exceptions.Timeout:
        print_error(f"连接超时 ({timeout}秒)")
    except Exception as e:
        print_error(f"检查失败: {e}")


@health.command(name='db')
@click.option('--host', default='localhost', help='数据库主机')
@click.option('--port', default=5432, help='数据库端口')
def check_db(host, port):
    """检查数据库连接"""
    try:
        import psycopg2

        click.echo(f"检查数据库连接: {host}:{port}")

        # 从settings获取连接信息
        # 注意：需要根据实际配置解析数据库URL
        from datamind.config import get_settings
        settings = get_settings()
        db_url = settings.database.url

        # 解析数据库URL
        import re
        match = re.search(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', db_url)
        if match:
            user, password, db_host, db_port, db_name = match.groups()
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                user=user,
                password=password,
                dbname=db_name,
                connect_timeout=5
            )
        else:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=settings.database.url.split('/')[-1],
                dbname=settings.database.url.split('/')[-1],
                connect_timeout=5
            )

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()

        if result:
            print_success("数据库连接正常")

        cursor.close()
        conn.close()

    except Exception as e:
        print_error(f"数据库连接失败: {e}")


@health.command(name='redis')
@click.option('--host', default='localhost', help='Redis主机')
@click.option('--port', default=6379, help='Redis端口')
def check_redis(host, port):
    """检查Redis连接"""
    try:
        import redis

        click.echo(f"检查Redis连接: {host}:{port}")

        r = redis.Redis(host=host, port=port, socket_connect_timeout=5)
        r.ping()

        print_success("Redis连接正常")

        # 获取信息
        info = r.info()
        click.echo(f"版本: {info.get('redis_version', 'unknown')}")
        click.echo(f"内存使用: {info.get('used_memory_human', 'unknown')}")
        click.echo(f"连接数: {info.get('connected_clients', 0)}")

    except Exception as e:
        print_error(f"Redis连接失败: {e}")


@health.command(name='all')
@click.option('--host', default='localhost', help='API主机')
@click.option('--port', default=8000, help='API端口')
def check_all(host, port):
    """检查所有服务"""
    click.echo("=" * 50)
    click.echo("Datamind 服务健康检查")
    click.echo("=" * 50)

    # 检查API
    check_health.callback(host, port, 5)

    click.echo("\n" + "-" * 50)

    # 检查数据库
    check_db.callback('localhost', 5432)

    click.echo("\n" + "-" * 50)

    # 检查Redis
    check_redis.callback('localhost', 6379)