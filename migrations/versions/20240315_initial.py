# datamind/migrations/versions/20240315_initial.py
"""初始迁移

修订版本ID: 20240315_initial
父修订版本:
创建日期: 2024-03-15 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20240315_initial'  # 修订版本标识符
down_revision = None           # 初始版本，没有父版本
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库到当前版本"""

    # ===================== 创建枚举类型 =====================
    bind = op.get_bind()

    # 任务类型枚举
    task_type_enum = sa.Enum(
        'scoring', 'fraud_detection',
        name='task_type_enum',
        schema='public',
        create_type=False
    )
    # task_type_enum.create(bind, checkfirst=True)

    # 模型类型枚举
    model_type_enum = sa.Enum(
        'decision_tree', 'random_forest', 'xgboost',
        'lightgbm', 'logistic_regression', 'catboost', 'neural_network',
        name='model_type_enum',
        schema='public',
        create_type=False
    )
    # model_type_enum.create(bind, checkfirst=True)

    # 框架枚举
    framework_enum = sa.Enum(
        'sklearn', 'xgboost', 'lightgbm', 'torch',
        'tensorflow', 'onnx', 'catboost',
        name='framework_enum',
        schema='public',
        create_type=False
    )
    # framework_enum.create(bind, checkfirst=True)

    # 模型状态枚举
    model_status_enum = sa.Enum(
        'active', 'inactive', 'deprecated', 'archived',
        name='model_status_enum',
        schema='public',
        create_type=False
    )
    # model_status_enum.create(bind, checkfirst=True)

    # 审计操作枚举
    audit_action_enum = sa.Enum(
        'CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE',
        'DEPRECATE', 'ARCHIVE', 'RESTORE', 'VERSION_ADD',
        'VERSION_SWITCH', 'DOWNLOAD', 'INFERENCE', 'PROMOTE',
        'ROLLBACK', 'CONFIG_CHANGE',
        name='audit_action_enum',
        schema='public',
        create_type=False
    )
    # audit_action_enum.create(bind, checkfirst=True)

    # 部署环境枚举
    deployment_env_enum = sa.Enum(
        'development', 'testing', 'staging', 'production',
        name='deployment_env_enum',
        schema='public',
        create_type=False
    )
    # deployment_env_enum.create(bind, checkfirst=True)

    # A/B测试状态枚举
    abtest_status_enum = sa.Enum(
        'draft', 'running', 'paused', 'completed', 'terminated',
        name='abtest_status_enum',
        schema='public',
        create_type=False
    )
    # abtest_status_enum.create(bind, checkfirst=True)

    # ===================== 创建核心表 =====================

    # 1. 模型元数据表
    op.create_table(
        'model_metadata',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型唯一标识'),
        sa.Column('model_name', sa.String(length=100), nullable=False, comment='模型名称'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', task_type_enum, nullable=False,
                  comment='任务类型: scoring-评分卡, fraud_detection-反欺诈'),
        sa.Column('model_type', model_type_enum, nullable=False, comment='模型算法类型'),
        sa.Column('framework', framework_enum, nullable=False, comment='模型框架'),
        sa.Column('file_path', sa.String(length=500), nullable=False, comment='模型文件路径'),
        sa.Column('file_hash', sa.String(length=64), nullable=False, comment='文件SHA256哈希值'),
        sa.Column('file_size', sa.BigInteger(), nullable=False, comment='文件大小(字节)'),
        sa.Column('input_features', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb"), comment='输入特征列表'),
        sa.Column('output_schema', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb"), comment='输出格式定义'),
        sa.Column('model_params', postgresql.JSONB(), nullable=True, comment='模型参数'),
        sa.Column('feature_importance', postgresql.JSONB(), nullable=True, comment='特征重要性'),
        sa.Column('performance_metrics', postgresql.JSONB(), nullable=True, comment='性能指标'),
        sa.Column('status', model_status_enum, nullable=False, server_default='inactive', comment='模型状态'),
        sa.Column('is_production', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                  comment='是否为生产模型'),
        sa.Column('ab_test_group', sa.String(length=50), nullable=True, comment='A/B测试组标识'),
        sa.Column('created_by', sa.String(length=50), nullable=False, comment='创建人'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True, comment='部署时间'),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True, comment='废弃时间'),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True, comment='归档时间'),
        sa.Column('description', sa.Text(), nullable=True, comment='模型描述'),
        sa.Column('tags', postgresql.JSONB(), nullable=True, comment='标签'),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True, comment='额外元数据'),
        sa.PrimaryKeyConstraint('id', name='pk_model_metadata'),
        sa.UniqueConstraint('model_id', name='uq_model_id'),
        sa.UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
        schema='public',
        comment='模型元数据表'
    )

    # 模型表索引
    op.create_index('idx_model_status', 'model_metadata', ['status', 'is_production'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_model_status IS '状态和是否生产复合索引';")

    op.create_index('idx_model_abtest', 'model_metadata', ['ab_test_group', 'status'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_model_abtest IS 'A/B测试组和状态复合索引';")

    op.create_index('idx_model_created_at', 'model_metadata', ['created_at'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_model_created_at IS '创建时间索引';")

    op.create_index('idx_model_task_type', 'model_metadata', ['task_type'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_model_task_type IS '任务类型索引';")

    op.create_index('idx_model_type_framework', 'model_metadata', ['model_type', 'framework'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_model_type_framework IS '模型类型和框架复合索引';")

    # 2. 模型版本历史表
    op.create_table(
        'model_version_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('operation', audit_action_enum, nullable=False, comment='操作类型'),
        sa.Column('operator', sa.String(length=50), nullable=False, comment='操作人'),
        sa.Column('operator_ip', postgresql.INET(), nullable=True, comment='操作人IP'),
        sa.Column('operation_time', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='操作时间'),
        sa.Column('reason', sa.Text(), nullable=True, comment='操作原因'),
        sa.Column('metadata_snapshot', postgresql.JSONB(), nullable=True, comment='元数据快照'),
        sa.Column('details', postgresql.JSONB(), nullable=True, comment='额外详情'),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'],
                                ondelete='CASCADE', name='fk_history_model'),
        sa.PrimaryKeyConstraint('id', name='pk_model_version_history'),
        schema='public',
        comment='模型版本历史表'
    )
    op.create_index('idx_history_model_time', 'model_version_history', ['model_id', 'operation_time'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_history_model_time IS '模型和操作时间复合索引';")

    op.create_index('idx_history_operator', 'model_version_history', ['operator'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_history_operator IS '操作人索引';")

    op.create_index('idx_history_operation', 'model_version_history', ['operation'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_history_operation IS '操作类型索引';")

    # 3. 模型部署表
    op.create_table(
        'model_deployments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('deployment_id', sa.String(length=50), nullable=False, comment='部署ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('environment', deployment_env_enum, nullable=False, comment='部署环境'),
        sa.Column('endpoint_url', sa.String(length=200), nullable=True, comment='服务端点URL'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='是否活跃'),
        sa.Column('deployment_config', postgresql.JSONB(), nullable=True, comment='部署配置'),
        sa.Column('resources', postgresql.JSONB(), nullable=True, comment='资源配置'),
        sa.Column('deployed_by', sa.String(length=50), nullable=False, comment='部署人'),
        sa.Column('deployed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='部署时间'),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True, comment='最后健康检查时间'),
        sa.Column('health_status', sa.String(length=20), nullable=True, comment='健康状态'),
        sa.Column('health_check_details', postgresql.JSONB(), nullable=True, comment='健康检查详情'),
        sa.Column('traffic_weight', sa.Integer(), nullable=False, server_default='100', comment='流量权重'),
        sa.Column('canary_config', postgresql.JSONB(), nullable=True, comment='灰度发布配置'),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'],
                                ondelete='CASCADE', name='fk_deployment_model'),
        sa.PrimaryKeyConstraint('id', name='pk_model_deployments'),
        sa.UniqueConstraint('deployment_id', name='uq_deployment_id'),
        schema='public',
        comment='模型部署表'
    )
    op.create_index('idx_deployment_active', 'model_deployments', ['is_active'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_deployment_active IS '活跃状态索引';")

    op.create_index('idx_deployment_env', 'model_deployments', ['environment'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_deployment_env IS '环境索引';")

    op.create_index('idx_deployment_model_env', 'model_deployments', ['model_id', 'environment'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_deployment_model_env IS '模型和环境复合索引';")

    # 4. API调用日志表
    op.create_table(
        'api_call_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('request_id', sa.String(length=50), nullable=False, comment='请求ID'),
        sa.Column('application_id', sa.String(length=50), nullable=False, comment='应用/申请ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', task_type_enum, nullable=False, comment='任务类型'),
        sa.Column('endpoint', sa.String(length=100), nullable=False, comment='API端点'),
        sa.Column('request_data', postgresql.JSONB(), nullable=True, comment='请求数据'),
        sa.Column('response_data', postgresql.JSONB(), nullable=True, comment='响应数据'),
        sa.Column('request_headers', postgresql.JSONB(), nullable=True, comment='请求头'),
        sa.Column('response_headers', postgresql.JSONB(), nullable=True, comment='响应头'),
        sa.Column('processing_time_ms', sa.Integer(), nullable=False, comment='处理时间(毫秒)'),
        sa.Column('model_inference_time_ms', sa.Integer(), nullable=True, comment='模型推理时间(毫秒)'),
        sa.Column('total_time_ms', sa.Integer(), nullable=True, comment='总耗时(毫秒)'),
        sa.Column('status_code', sa.Integer(), nullable=False, comment='HTTP状态码'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误消息'),
        sa.Column('error_traceback', sa.Text(), nullable=True, comment='错误堆栈'),
        sa.Column('error_code', sa.String(length=50), nullable=True, comment='错误代码'),
        sa.Column('ip_address', postgresql.INET(), nullable=True, comment='客户端IP'),
        sa.Column('user_agent', sa.String(length=200), nullable=True, comment='用户代理'),
        sa.Column('api_key', sa.String(length=100), nullable=True, comment='API密钥'),
        sa.Column('user_id', sa.String(length=50), nullable=True, comment='用户ID'),
        sa.Column('cost_credits', sa.Numeric(10, 4), nullable=True, comment='消耗积分'),
        sa.Column('billing_info', postgresql.JSONB(), nullable=True, comment='计费信息'),
        sa.Column('business_metrics', postgresql.JSONB(), nullable=True, comment='业务指标'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('partition_date', sa.DateTime(), server_default=sa.text('date_trunc(\'day\', now())'),
                  nullable=False, comment='分区日期'),
        sa.PrimaryKeyConstraint('id', name='pk_api_call_logs'),
        sa.UniqueConstraint('request_id', name='uq_request_id'),
        schema='public',
        comment='API调用日志表'
    )
    op.create_index('idx_api_time', 'api_call_logs', ['created_at'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_api_time IS '创建时间索引';")

    op.create_index('idx_api_app_model', 'api_call_logs', ['application_id', 'model_id'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_api_app_model IS '应用和模型复合索引';")

    op.create_index('idx_api_request_id', 'api_call_logs', ['request_id'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_api_request_id IS '请求ID索引';")

    op.create_index('idx_api_status', 'api_call_logs', ['status_code'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_api_status IS '状态码索引';")

    op.create_index('idx_api_task_type', 'api_call_logs', ['task_type'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_api_task_type IS '任务类型索引';")

    # 5. 模型性能监控表
    op.create_table(
        'model_performance_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', task_type_enum, nullable=False, comment='任务类型'),
        sa.Column('date', sa.DateTime(), nullable=False, comment='统计日期'),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0', comment='总请求数'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0', comment='成功数'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0', comment='错误数'),
        sa.Column('timeout_count', sa.Integer(), nullable=False, server_default='0', comment='超时数'),
        sa.Column('avg_response_time_ms', sa.Float(), nullable=True, comment='平均响应时间'),
        sa.Column('p50_response_time_ms', sa.Float(), nullable=True, comment='P50响应时间'),
        sa.Column('p95_response_time_ms', sa.Float(), nullable=True, comment='P95响应时间'),
        sa.Column('p99_response_time_ms', sa.Float(), nullable=True, comment='P99响应时间'),
        sa.Column('max_response_time_ms', sa.Integer(), nullable=True, comment='最大响应时间'),
        sa.Column('min_response_time_ms', sa.Integer(), nullable=True, comment='最小响应时间'),
        # 评分卡专用指标
        sa.Column('avg_score', sa.Float(), nullable=True, comment='平均评分'),
        sa.Column('score_distribution', postgresql.JSONB(), nullable=True, comment='评分分布'),
        sa.Column('score_bins', postgresql.JSONB(), nullable=True, comment='评分区间统计'),
        # 反欺诈专用指标
        sa.Column('fraud_rate', sa.Float(), nullable=True, comment='欺诈率'),
        sa.Column('fraud_count', sa.Integer(), nullable=True, comment='欺诈数量'),
        sa.Column('risk_distribution', postgresql.JSONB(), nullable=True, comment='风险分布'),
        sa.Column('risk_levels', postgresql.JSONB(), nullable=True, comment='风险等级统计'),
        # 通用指标
        sa.Column('feature_importance_drift', postgresql.JSONB(), nullable=True, comment='特征重要性漂移'),
        sa.Column('avg_cpu_usage', sa.Float(), nullable=True, comment='平均CPU使用率'),
        sa.Column('avg_memory_usage', sa.Float(), nullable=True, comment='平均内存使用率'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'],
                                ondelete='CASCADE', name='fk_performance_model'),
        sa.PrimaryKeyConstraint('id', name='pk_model_performance_metrics'),
        sa.UniqueConstraint('model_id', 'model_version', 'date', name='uq_model_metric_date'),
        schema='public',
        comment='模型性能监控表'
    )
    op.create_index('idx_performance_model_date', 'model_performance_metrics', ['model_id', 'date'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_performance_model_date IS '模型和日期复合索引';")

    op.create_index('idx_performance_task_type', 'model_performance_metrics', ['task_type'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_performance_task_type IS '任务类型索引';")

    # 6. 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('audit_id', sa.String(length=50), nullable=False, comment='审计ID'),
        sa.Column('event_type', sa.String(length=50), nullable=False, comment='事件类型'),
        sa.Column('action', audit_action_enum, nullable=False, comment='操作类型'),
        sa.Column('operator', sa.String(length=50), nullable=False, comment='操作人'),
        sa.Column('operator_ip', postgresql.INET(), nullable=True, comment='操作人IP'),
        sa.Column('operator_role', sa.String(length=50), nullable=True, comment='操作人角色'),
        sa.Column('session_id', sa.String(length=100), nullable=True, comment='会话ID'),
        sa.Column('resource_type', sa.String(length=50), nullable=False, comment='资源类型'),
        sa.Column('resource_id', sa.String(length=50), nullable=True, comment='资源ID'),
        sa.Column('resource_name', sa.String(length=100), nullable=True, comment='资源名称'),
        sa.Column('before_state', postgresql.JSONB(), nullable=True, comment='操作前状态'),
        sa.Column('after_state', postgresql.JSONB(), nullable=True, comment='操作后状态'),
        sa.Column('changes', postgresql.JSONB(), nullable=True, comment='变更内容'),
        sa.Column('details', postgresql.JSONB(), nullable=True, comment='详细信息'),
        sa.Column('result', sa.String(length=20), nullable=True, comment='操作结果'),
        sa.Column('reason', sa.Text(), nullable=True, comment='原因'),
        sa.Column('error_code', sa.String(length=50), nullable=True, comment='错误代码'),
        sa.Column('model_id', sa.String(length=50), nullable=True, comment='关联模型ID'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'],
                                ondelete='SET NULL', name='fk_audit_model'),
        sa.PrimaryKeyConstraint('id', name='pk_audit_logs'),
        sa.UniqueConstraint('audit_id', name='uq_audit_id'),
        schema='public',
        comment='审计日志表'
    )
    op.create_index('idx_audit_time', 'audit_logs', ['created_at'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_audit_time IS '创建时间索引';")

    op.create_index('idx_audit_operator', 'audit_logs', ['operator'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_audit_operator IS '操作人索引';")

    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_audit_resource IS '资源类型和ID复合索引';")

    op.create_index('idx_audit_event', 'audit_logs', ['event_type'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_audit_event IS '事件类型索引';")

    op.create_index('idx_audit_action', 'audit_logs', ['action'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_audit_action IS '操作类型索引';")

    # 7. A/B测试配置表
    op.create_table(
        'ab_test_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('test_id', sa.String(length=50), nullable=False, comment='测试ID'),
        sa.Column('test_name', sa.String(length=100), nullable=False, comment='测试名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='测试描述'),
        sa.Column('task_type', task_type_enum, nullable=False, comment='任务类型'),
        sa.Column('groups', postgresql.JSONB(), nullable=False, comment='测试组配置'),
        sa.Column('traffic_allocation', sa.Float(), nullable=False, server_default='100.0',
                  comment='流量分配百分比'),
        sa.Column('assignment_strategy', sa.String(length=20), nullable=False, server_default='random',
                  comment='分配策略'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False, comment='开始时间'),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True, comment='结束时间'),
        sa.Column('status', abtest_status_enum, nullable=False, server_default='draft',
                  comment='测试状态'),
        sa.Column('created_by', sa.String(length=50), nullable=False, comment='创建人'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('metrics', postgresql.JSONB(), nullable=True, comment='监控指标'),
        sa.Column('winning_criteria', postgresql.JSONB(), nullable=True, comment='获胜标准'),
        sa.Column('results', postgresql.JSONB(), nullable=True, comment='测试结果'),
        sa.Column('winning_group', sa.String(length=50), nullable=True, comment='获胜组'),
        sa.PrimaryKeyConstraint('id', name='pk_ab_test_configs'),
        sa.UniqueConstraint('test_id', name='uq_test_id'),
        schema='public',
        comment='A/B测试配置表'
    )
    op.create_index('idx_abtest_status', 'ab_test_configs', ['status'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_abtest_status IS '状态索引';")

    op.create_index('idx_abtest_dates', 'ab_test_configs', ['start_date', 'end_date'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_abtest_dates IS '开始和结束时间复合索引';")

    op.create_index('idx_abtest_task_type', 'ab_test_configs', ['task_type'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_abtest_task_type IS '任务类型索引';")

    # 8. A/B测试分配表
    op.create_table(
        'ab_test_assignments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('test_id', sa.String(length=50), nullable=False, comment='测试ID'),
        sa.Column('user_id', sa.String(length=50), nullable=False, comment='用户ID'),
        sa.Column('group_name', sa.String(length=50), nullable=False, comment='组名'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='分配时间'),
        sa.Column('assignment_hash', sa.String(length=64), nullable=True, comment='分配哈希'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'],
                                ondelete='CASCADE', name='fk_assignment_model'),
        sa.ForeignKeyConstraint(['test_id'], ['public.ab_test_configs.test_id'],
                                ondelete='CASCADE', name='fk_assignment_test'),
        sa.PrimaryKeyConstraint('id', name='pk_ab_test_assignments'),
        schema='public',
        comment='A/B测试分配表'
    )
    op.create_index('idx_ab_assign_test_user', 'ab_test_assignments', ['test_id', 'user_id'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_ab_assign_test_user IS '测试和用户复合索引';")

    op.create_index('idx_ab_assign_time', 'ab_test_assignments', ['assigned_at'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_ab_assign_time IS '分配时间索引';")

    op.create_index('idx_ab_assign_model', 'ab_test_assignments', ['model_id'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_ab_assign_model IS '模型ID索引';")

    # 9. 系统配置表
    op.create_table(
        'system_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('config_key', sa.String(length=100), nullable=False, comment='配置键'),
        sa.Column('config_value', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb"), comment='配置值'),
        sa.Column('description', sa.Text(), nullable=True, comment='配置描述'),
        sa.Column('category', sa.String(length=50), nullable=True, comment='配置分类'),
        sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default=sa.text('false'),
                  comment='是否加密'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='配置版本'),
        sa.Column('updated_by', sa.String(length=50), nullable=False, comment='更新人'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.PrimaryKeyConstraint('id', name='pk_system_configs'),
        sa.UniqueConstraint('config_key', name='uq_config_key'),
        schema='public',
        comment='系统配置表'
    )
    op.create_index('idx_config_category', 'system_configs', ['category'],
                    schema='public')
    op.execute("COMMENT ON INDEX public.idx_config_category IS '配置分类索引';")


def downgrade() -> None:
    """降级数据库到上一个版本"""

    # 删除表（按外键依赖的反向顺序）
    op.drop_table('ab_test_assignments', schema='public')
    op.drop_table('model_version_history', schema='public')
    op.drop_table('model_deployments', schema='public')
    op.drop_table('model_performance_metrics', schema='public')
    op.drop_table('audit_logs', schema='public')
    op.drop_table('ab_test_configs', schema='public')
    op.drop_table('api_call_logs', schema='public')
    op.drop_table('system_configs', schema='public')
    op.drop_table('model_metadata', schema='public')

    # 删除枚举类型（使用 CASCADE 确保安全删除）
    op.execute('DROP TYPE IF EXISTS public.task_type_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.model_type_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.framework_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.model_status_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.audit_action_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.deployment_env_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.abtest_status_enum CASCADE')