# Datamind/datamind/cli/commands/audit.py
import click
from datetime import datetime, timedelta
import json

from datamind.cli.utils.printer import print_table, print_json, print_error, print_warning
from datamind.core.db.database import get_db
from datamind.core import AuditLog


@click.group(name='audit')
def audit():
    """审计日志命令"""
    pass


@audit.command(name='list')
@click.option('--days', '-d', default=7, help='最近几天 (默认: 7)')
@click.option('--action', '-a', help='操作类型筛选')
@click.option('--user', '-u', help='操作人筛选')
@click.option('--resource', '-r', help='资源类型筛选')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table')
@click.option('--limit', '-l', default=100, help='最大记录数')
def list_logs(days, action, user, resource, output_format, limit):
    """查看审计日志"""
    try:
        start_date = datetime.now() - timedelta(days=days)

        with get_db() as session:
            query = session.query(AuditLog).filter(
                AuditLog.created_at >= start_date
            ).order_by(AuditLog.created_at.desc())

            if action:
                query = query.filter(AuditLog.action == action)
            if user:
                query = query.filter(AuditLog.operator == user)
            if resource:
                query = query.filter(AuditLog.resource_type == resource)

            logs = query.limit(limit).all()

        if not logs:
            print_warning("未找到审计日志")
            return

        if output_format == 'json':
            result = []
            for log in logs:
                result.append({
                    'time': log.created_at.isoformat(),
                    'action': log.action,
                    'operator': log.operator,
                    'resource_type': log.resource_type,
                    'resource_id': log.resource_id,
                    'result': log.result,
                    'details': log.details
                })
            print_json(result)
        else:
            headers = ['时间', '操作', '操作人', '资源类型', '资源ID', '结果']
            rows = []
            for log in logs:
                rows.append([
                    log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    log.action,
                    log.operator,
                    log.resource_type,
                    log.resource_id or '-',
                    '✅' if log.result == 'SUCCESS' else '❌'
                ])
            print_table(headers, rows)
            click.echo(f"\n总计: {len(logs)} 条记录")

    except Exception as e:
        print_error(f"获取审计日志失败: {e}")


@audit.command(name='show')
@click.argument('audit-id')
def show_log(audit_id):
    """查看审计日志详情"""
    try:
        with get_db() as session:
            log = session.query(AuditLog).filter_by(audit_id=audit_id).first()

            if not log:
                print_error(f"审计日志不存在: {audit_id}")
                return

            click.echo("\n" + "=" * 60)
            click.echo(f"审计日志详情: {audit_id}")
            click.echo("=" * 60)
            click.echo(f"时间:     {log.created_at}")
            click.echo(f"操作:     {log.action}")
            click.echo(f"操作人:   {log.operator} ({log.operator_ip or 'unknown'})")
            click.echo(f"资源类型: {log.resource_type}")
            click.echo(f"资源ID:   {log.resource_id or '-'}")
            click.echo(f"结果:     {'成功' if log.result == 'SUCCESS' else '失败'}")

            if log.reason:
                click.echo(f"原因:     {log.reason}")

            if log.details:
                click.echo("\n详细信息:")
                click.echo(json.dumps(log.details, indent=2, ensure_ascii=False))

            if log.changes:
                click.echo("\n变更内容:")
                click.echo(json.dumps(log.changes, indent=2, ensure_ascii=False))

    except Exception as e:
        print_error(f"获取审计日志失败: {e}")


@audit.command(name='export')
@click.option('--days', '-d', default=30, help='导出最近几天的日志')
@click.option('--output', '-o', required=True, help='输出文件路径')
def export_logs(days, output):
    """导出审计日志到文件"""
    try:
        start_date = datetime.now() - timedelta(days=days)

        with get_db() as session:
            logs = session.query(AuditLog).filter(
                AuditLog.created_at >= start_date
            ).order_by(AuditLog.created_at).all()

        result = []
        for log in logs:
            result.append({
                'audit_id': log.audit_id,
                'time': log.created_at.isoformat(),
                'action': log.action,
                'operator': log.operator,
                'operator_ip': log.operator_ip,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'result': log.result,
                'reason': log.reason,
                'details': log.details,
                'changes': log.changes
            })

        with open(output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        click.echo(f"已导出 {len(result)} 条审计日志到 {output}")

    except Exception as e:
        print_error(f"导出失败: {e}")