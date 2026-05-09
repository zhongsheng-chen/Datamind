# Datamind/datamind/cli/commands/model_type.py

"""模型管理命令行命令

提供模型的全生命周期管理功能，包括注册、查询、激活、停用、加载、卸载等操作。

功能特性：
  - 模型列表查询（支持多维度筛选）
  - 模型详细信息查看
  - 模型注册（支持本地文件上传）
  - 模型状态管理（激活/停用）
  - 生产模型管理（提升/降级）
  - 模型加载/卸载（内存管理）
  - 模型历史记录查看
  - 模型参数配置管理

命令列表：
  - model list: 列出所有模型
  - model show: 显示模型详细信息
  - model register: 注册新模型
  - model activate: 激活模型
  - model deactivate: 停用模型
  - model promote: 提升为生产模型
  - model load: 加载模型到内存
  - model unload: 从内存卸载模型
  - model history: 查看模型操作历史
  - model params: 获取模型参数配置
  - model update-params: 更新模型参数配置

筛选条件（list 命令）：
  - --task-type / -t: 任务类型（scoring/fraud_detection）
  - --status / -s: 状态（active/inactive/deprecated）
  - --framework / -f: 框架（sklearn/xgboost/torch等）
  - --production / --no-production: 是否为生产模型

输出格式：
  - table: 表格形式输出（默认）
  - json: JSON 格式输出

使用示例：
  # 列出所有活跃模型
  datamind model list --status active

  # 列出评分卡模型
  datamind model list --task-type scoring

  # 显示模型详情
  datamind model show MDL_20240315_123456

  # 注册新模型
  datamind model register \
    --name credit_score_model \
    --version 1.0.0 \
    --task-type scoring \
    --model-type xgboost \
    --framework xgboost \
    --features '["age","income"]' \
    --output '{"score":"float"}' \
    --file model.pkl \
    --user admin

  # 激活模型
  datamind model activate MDL_xxx --reason "上线测试"

  # 提升为生产模型
  datamind model promote MDL_xxx --reason "通过验证"

  # 加载模型到内存
  datamind model load MDL_xxx

  # 查看模型历史
  datamind model history MDL_xxx

  # 更新评分卡参数
  datamind model update-params MDL_xxx \
    --scorecard '{"base_score":650,"pdo":60}' \
    --reason "调整评分范围"

模型参数配置：
  - 评分卡参数（scorecard）：base_score、pdo、min_score、max_score、direction
  - 风险配置（risk_config）：levels（风险等级阈值）
"""

import click
import sys
import json

from datamind.cli.utils.printer import (
    print_table, print_json, print_success,
    print_error, print_warning, print_header
)
from datamind.cli.utils.progress import ProgressBar
from datamind.core.ml.model import model_registry
from datamind.core.ml.model import model_loader


@click.group(name='model')
def model():
    """模型管理命令"""
    pass


@model.command(name='list')
@click.option('--task-type', '-t', help='按任务类型筛选 (scoring/fraud_detection)')
@click.option('--status', '-s', help='按状态筛选 (active/inactive/deprecated)')
@click.option('--framework', '-f', help='按框架筛选')
@click.option('--production/--no-production', default=None, help='是否生产模型')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table')
def list_models(task_type, status, framework, production, output_format):
    """列出所有模型"""
    try:
        models = model_registry.list_models(
            task_type=task_type,
            status=status,
            framework=framework,
            is_production=production
        )

        if not models:
            print_warning("未找到模型")
            return

        if output_format == 'json':
            print_json(models)
        else:
            headers = ['ID', '名称', '版本', '任务类型', '模型类型', '框架', '状态', '生产', '创建时间']
            rows = []
            for m in models:
                rows.append([
                    m['model_id'][:12] + '...',
                    m['model_name'],
                    m['model_version'],
                    m['task_type'],
                    m['model_type'],
                    m['framework'],
                    m['status'],
                    '✅' if m['is_production'] else '❌',
                    m['created_at'][:10] if m['created_at'] else ''
                ])
            print_table(headers, rows)
            click.echo(f"\n总计: {len(models)} 个模型")

    except Exception as e:
        print_error(f"获取模型列表失败: {e}")
        sys.exit(1)


@model.command(name='show')
@click.argument('model-id')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table')
def show_model(model_id, output_format):
    """显示模型详细信息"""
    try:
        model_info = model_registry.get_model_info(model_id)
        if not model_info:
            print_error(f"模型不存在: {model_id}")
            sys.exit(1)

        # 添加加载状态
        model_info['is_loaded'] = model_loader.is_loaded(model_id)

        if output_format == 'json':
            print_json(model_info)
        else:
            print_header(f"模型详情: {model_info['model_name']} v{model_info['model_version']}")

            info_table = [
                ['模型ID', model_info['model_id']],
                ['名称', model_info['model_name']],
                ['版本', model_info['model_version']],
                ['任务类型', model_info['task_type']],
                ['模型类型', model_info['model_type']],
                ['框架', model_info['framework']],
                ['状态', model_info['status']],
                ['生产模型', '✅' if model_info['is_production'] else '❌'],
                ['内存加载', '✅' if model_info.get('is_loaded') else '❌'],
                ['创建人', model_info['created_by']],
                ['创建时间', model_info['created_at']],
                ['描述', model_info.get('description', '')]
            ]

            print_table(['属性', '值'], info_table)

            # 显示特征列表
            if model_info.get('input_features'):
                click.echo("\n输入特征:")
                for i, f in enumerate(model_info['input_features'], 1):
                    click.echo(f"  {i}. {f}")

            # 显示输出格式
            if model_info.get('output_schema'):
                click.echo("\n输出格式:")
                for key, value in model_info['output_schema'].items():
                    click.echo(f"  {key}: {value}")

    except Exception as e:
        print_error(f"获取模型信息失败: {e}")
        sys.exit(1)


@model.command(name='register')
@click.option('--name', '-n', required=True, help='模型名称')
@click.option('--version', '-v', required=True, help='模型版本')
@click.option('--task-type', '-t', required=True, type=click.Choice(['scoring', 'fraud_detection']), help='任务类型')
@click.option('--model-type', '-m', required=True, help='模型类型')
@click.option('--framework', '-f', required=True, help='模型框架')
@click.option('--features', '-i', required=True, help='输入特征JSON文件或JSON字符串')
@click.option('--output', '-o', required=True, help='输出格式JSON文件或JSON字符串')
@click.option('--file', '-F', required=True, type=click.Path(exists=True), help='模型文件路径')
@click.option('--description', '-d', help='模型描述')
@click.option('--params', '-p', help='模型参数JSON文件')
@click.option('--tags', help='标签JSON文件')
@click.option('--scorecard', '-s', help='评分卡配置JSON文件（仅评分卡模型）')
@click.option('--risk-config', '-r', help='风险配置JSON文件（仅反欺诈模型）')
@click.option('--user', '-u', default='cli_user', help='操作人')
def register_model(name, version, task_type, model_type, framework,
                   features, output, file, description, params, tags,
                   scorecard, risk_config, user):
    """注册新模型"""
    # ... 代码保持不变 ...


@model.command(name='activate')
@click.argument('model-id')
@click.option('--reason', '-r', help='激活原因')
@click.option('--user', '-u', default='cli_user', help='操作人')
def activate_model(model_id, reason, user):
    """激活模型"""
    try:
        model_registry.activate_model(
            model_id=model_id,
            operator=user,
            reason=reason
        )
        print_success(f"模型 {model_id} 已激活")
    except Exception as e:
        print_error(f"激活失败: {e}")
        sys.exit(1)


@model.command(name='deactivate')
@click.argument('model-id')
@click.option('--reason', '-r', help='停用原因')
@click.option('--user', '-u', default='cli_user', help='操作人')
def deactivate_model(model_id, reason, user):
    """停用模型"""
    try:
        model_registry.deactivate_model(
            model_id=model_id,
            operator=user,
            reason=reason
        )
        print_success(f"模型 {model_id} 已停用")
    except Exception as e:
        print_error(f"停用失败: {e}")
        sys.exit(1)


@model.command(name='promote')
@click.argument('model-id')
@click.option('--reason', '-r', help='提升原因')
@click.option('--user', '-u', default='cli_user', help='操作人')
def promote_model(model_id, reason, user):
    """提升为生产模型"""
    try:
        # 注意：model_registry 中的方法是 promote_to_production
        model_registry.promote_to_production(
            model_id=model_id,
            operator=user,
            reason=reason
        )
        print_success(f"模型 {model_id} 已设为生产模型")
    except Exception as e:
        print_error(f"提升失败: {e}")
        sys.exit(1)


@model.command(name='load')
@click.argument('model-id')
def load_model(model_id):
    """加载模型到内存"""
    try:
        with ProgressBar("加载模型中", "模型加载完成") as pb:
            pb.update(30, "验证模型...")
            success = model_loader.load_model(model_id, "cli")
            pb.update(100, "完成")

        if success:
            print_success(f"模型 {model_id} 已加载到内存")
        else:
            print_error(f"模型 {model_id} 加载失败")
    except Exception as e:
        print_error(f"加载失败: {e}")
        sys.exit(1)


@model.command(name='unload')
@click.argument('model-id')
def unload_model(model_id):
    """从内存卸载模型"""
    try:
        model_loader.unload_model(model_id, "cli")
        print_success(f"模型 {model_id} 已从内存卸载")
    except Exception as e:
        print_error(f"卸载失败: {e}")
        sys.exit(1)


@model.command(name='history')
@click.argument('model-id')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='table')
def model_history(model_id, output_format):
    """查看模型历史"""
    try:
        history = model_registry.get_model_history(model_id)

        if not history:
            print_warning("暂无历史记录")
            return

        if output_format == 'json':
            print_json(history)
        else:
            headers = ['时间', '操作', '操作人', '原因']
            rows = []
            for h in history:
                rows.append([
                    h['operation_time'][:16] if h['operation_time'] else '',
                    h['operation'],
                    h['operator'],
                    h.get('reason', '')[:30] + '...' if h.get('reason') else ''
                ])
            print_table(headers, rows)

    except Exception as e:
        print_error(f"获取历史失败: {e}")
        sys.exit(1)


@model.command(name='params')
@click.argument('model-id')
@click.option('--format', '-f', 'output_format', type=click.Choice(['table', 'json']), default='json')
def get_params(model_id, output_format):
    """获取模型参数配置"""
    try:
        params = model_registry.get_model_params(model_id)

        if not params:
            print_warning("模型无参数配置")
            return

        if output_format == 'json':
            print_json(params)
        else:
            if params.get('scorecard'):
                print_header("评分卡配置")
                for key, value in params['scorecard'].items():
                    click.echo(f"  {key}: {value}")

            if params.get('risk_config'):
                print_header("风险配置")
                for key, value in params['risk_config'].items():
                    if key == 'levels':
                        click.echo("  levels:")
                        for level, threshold in value.items():
                            click.echo(f"    {level}: {threshold}")
                    else:
                        click.echo(f"  {key}: {value}")

    except Exception as e:
        print_error(f"获取参数失败: {e}")
        sys.exit(1)


@model.command(name='update-params')
@click.argument('model-id')
@click.option('--scorecard', '-s', help='评分卡配置JSON文件')
@click.option('--risk-config', '-r', help='风险配置JSON文件')
@click.option('--reason', help='更新原因')
@click.option('--user', '-u', default='cli_user', help='操作人')
def update_params(model_id, scorecard, risk_config, reason, user):
    """更新模型参数配置"""
    try:
        scorecard_params = None
        if scorecard:
            if scorecard.endswith('.json'):
                with open(scorecard, 'r') as f:
                    scorecard_params = json.load(f)
            else:
                scorecard_params = json.loads(scorecard)

        risk_config_dict = None
        if risk_config:
            if risk_config.endswith('.json'):
                with open(risk_config, 'r') as f:
                    risk_config_dict = json.load(f)
            else:
                risk_config_dict = json.loads(risk_config)

        model_registry.update_model_params(
            model_id=model_id,
            operator=user,
            scorecard_params=scorecard_params,
            risk_config=risk_config_dict,
            reason=reason
        )

        print_success(f"模型 {model_id} 参数已更新")

    except Exception as e:
        print_error(f"更新参数失败: {e}")
        sys.exit(1)