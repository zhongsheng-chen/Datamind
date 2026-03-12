import click
import requests
import json
from pathlib import Path
from rich.table import Table
from rich.progress import Progress
from cli.utils.printer import print_table, print_json, print_error, print_success
from cli.utils.config import get_api_url, get_headers


@click.group(name='model')
def model():
    """模型管理命令"""
    pass


@model.command(name='register')
@click.option('--file', '-f', required=True, type=click.Path(exists=True), help='模型文件路径')
@click.option('--name', '-n', required=True, help='模型名称')
@click.option('--type', '-t', 'model_type', required=True,
              type=click.Choice(['decision_tree', 'random_forest', 'xgboost', 'lightgbm', 'logistic_regression']),
              help='模型类型')
@click.option('--framework', '-fw', required=True,
              type=click.Choice(['sklearn', 'xgboost', 'lightgbm', 'torch', 'tensorflow', 'onnx', 'catboost']),
              help='模型框架')
@click.option('--task', '-tk', required=True,
              type=click.Choice(['scoring', 'fraud_detection']),
              help='任务类型')
@click.option('--version', '-v', required=True, help='版本号')
@click.option('--features', '-fe', required=True, help='特征名称，逗号分隔')
@click.option('--description', '-d', help='模型描述')
@click.option('--tags', '-tg', help='标签，JSON格式')
@click.option('--user', '-u', required=True, help='操作人ID')
def register_model(file, name, model_type, framework, task, version, features, description, tags, user):
    """注册新模型"""
    try:
        # 解析特征列表
        feature_list = [f.strip() for f in features.split(',')]

        # 解析标签
        tags_dict = json.loads(tags) if tags else {}

        # 准备请求
        url = f"{get_api_url()}/v1/models/register"

        with Progress() as progress:
            task = progress.add_task("上传模型中...", total=100)

            with open(file, 'rb') as f:
                files = {'model_file': f}
                data = {
                    'model_name': name,
                    'model_type': model_type,
                    'framework': framework,
                    'task_type': task,
                    'version': version,
                    'feature_names': json.dumps(feature_list),
                    'description': description or '',
                    'tags': json.dumps(tags_dict),
                    'created_by': user
                }

                progress.update(task, advance=50)

                response = requests.post(url, files=files, data=data)
                progress.update(task, advance=50)

        if response.status_code == 201:
            result = response.json()
            print_success(f"模型注册成功！")
            print_json(result)
        else:
            print_error(f"注册失败: {response.text}")

    except Exception as e:
        print_error(f"错误: {str(e)}")


@model.command(name='list')
@click.option('--task', '-t', type=click.Choice(['scoring', 'fraud_detection']), help='按任务类型过滤')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table', help='输出格式')
def list_models(task, output_format):
    """列出所有模型"""
    try:
        url = f"{get_api_url()}/v1/models"
        params = {'task_type': task} if task else {}

        response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 200:
            data = response.json()

            if output_format == 'json':
                print_json(data)
            else:
                table = Table(title="模型列表")
                table.add_column("模型ID", style="cyan")
                table.add_column("名称", style="green")
                table.add_column("类型", style="yellow")
                table.add_column("任务", style="blue")
                table.add_column("版本", style="magenta")
                table.add_column("状态", style="red")

                for model in data.get('models', []):
                    table.add_row(
                        model.get('model_id', ''),
                        model.get('model_name', ''),
                        model.get('model_type', ''),
                        model.get('task_type', ''),
                        model.get('current_version', ''),
                        model.get('status', '')
                    )

                print_table(table)
        else:
            print_error(f"查询失败: {response.text}")

    except Exception as e:
        print_error(f"错误: {str(e)}")


@model.command(name='info')
@click.argument('model_id')
@click.option('--version', '-v', help='版本号，默认最新')
def get_model_info(model_id, version):
    """获取模型详细信息"""
    try:
        url = f"{get_api_url()}/v1/models/{model_id}"
        params = {'version': version} if version else {}

        response = requests.get(url, params=params, headers=get_headers())

        if response.status_code == 200:
            print_json(response.json())
        else:
            print_error(f"查询失败: {response.text}")

    except Exception as e:
        print_error(f"错误: {str(e)}")


@model.command(name='delete')
@click.argument('model_id')
@click.option('--version', '-v', help='版本号，不指定则删除整个模型')
@click.option('--force', '-f', is_flag=True, help='强制删除，不提示确认')
@click.option('--user', '-u', required=True, help='操作人ID')
def delete_model(model_id, version, force, user):
    """删除模型"""
    if not force:
        if version:
            click.confirm(f'确定要删除模型 {model_id} 的版本 {version} 吗？', abort=True)
        else:
            click.confirm(f'确定要删除整个模型 {model_id} 吗？', abort=True)

    try:
        url = f"{get_api_url()}/v1/models/{model_id}"
        params = {'version': version} if version else {}
        params['user_id'] = user

        response = requests.delete(url, params=params, headers=get_headers())

        if response.status_code == 200:
            print_success("删除成功")
        else:
            print_error(f"删除失败: {response.text}")

    except Exception as e:
        print_error(f"错误: {str(e)}")