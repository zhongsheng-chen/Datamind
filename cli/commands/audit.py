import click
from datetime import datetime, timedelta
import requests
from cli.utils.printer import print_table, print_json
from cli.utils.config import get_api_url


@click.group(name='audit')
def audit():
    """审计日志管理"""
    pass


@audit.command(name='list')
@click.option('--model', '-m', help='模型ID')
@click.option('--user', '-u', help='操作人ID')
@click.option('--action', '-a', help='操作类型')
@click.option('--days', '-d', type=int, default=7, help='查询天数')
@click.option('--limit', '-l', type=int, default=100, help='返回条数')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table')
def list_audit_logs(model, user, action, days, limit, output_format):
    """查询审计日志"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        url = f"{get_api_url()}/v1/audit/logs"
        params = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'limit': limit
        }
        if model:
            params['model_id'] = model
        if user:
            params['user_id'] = user
        if action:
            params['action'] = action

        response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 200:
            data = response.json()

            if output_format == 'json':
                print_json(data)
            else:
                table = Table(title="审计日志")
                table.add_column("时间", style="cyan")
                table.add_column("操作", style="green")
                table.add_column("用户", style="yellow")
                table.add_column("模型", style="blue")
                table.add_column("状态", style="magenta")

                for log in data.get('logs', []):
                    table.add_row(
                        log.get('timestamp', ''),
                        log.get('action', ''),
                        log.get('user_id', ''),
                        log.get('model_info', {}).get('model_id', '') if log.get('model_info') else '',
                        log.get('status', '')
                    )

                print_table(table)
        else:
            click.echo(f"查询失败: {response.text}")

    except Exception as e:
        click.echo(f"错误: {str(e)}")


@audit.command(name='stats')
@click.option('--days', '-d', type=int, default=30, help='统计天数')
def audit_stats(days):
    """审计统计信息"""
    try:
        url = f"{get_api_url()}/v1/audit/stats"
        params = {'days': days}

        response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 200:
            print_json(response.json())
        else:
            click.echo(f"查询失败: {response.text}")

    except Exception as e:
        click.echo(f"错误: {str(e)}")


@audit.command(name='export')
@click.option('--days', '-d', type=int, default=7, help='导出天数')
@click.option('--output', '-o', default='audit_export.json', help='输出文件')
def export_audit_logs(days, output):
    """导出审计日志"""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        url = f"{get_api_url()}/v1/audit/logs"
        params = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'limit': 10000
        }

        with click.progressbar(length=100, label='导出审计日志') as bar:
            response = requests.get(url, params=params, headers=get_headers())
            bar.update(50)

            if response.status_code == 200:
                data = response.json()

                with open(output, 'w') as f:
                    json.dump(data, f, indent=2)

                bar.update(50)
                click.echo(f"已导出 {len(data.get('logs', []))} 条记录到 {output}")
            else:
                click.echo(f"导出失败: {response.text}")

    except Exception as e:
        click.echo(f"错误: {str(e)}")