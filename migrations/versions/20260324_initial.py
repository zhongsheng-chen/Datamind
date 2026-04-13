# Datamind/migrations/versions/20260324_initial.py
"""初始迁移

修订版本ID: 20260324_initial
父修订版本:
创建日期: 2026-03-24 10:00:00.000000

包含所有表：
- 枚举类型
- 模型管理表 (model_metadata, model_version_history, model_deployments)
- 监控表 (api_call_logs, model_performance_metrics)
- 审计表 (audit_logs)
- A/B测试表 (ab_test_configs, ab_test_assignments)
- 系统配置表 (system_configs)
- 用户认证表 (users, api_keys)
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import ENUM as PgEnum

revision = '20260324_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库到当前版本"""

    # ===================== 创建枚举类型 =====================
    # 注意：所有枚举值必须与 datamind/core/domain/enums.py 保持一致

    # 任务类型枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_type_enum') THEN
            CREATE TYPE task_type_enum AS ENUM ('scoring', 'fraud_detection');
        END IF;
    END$$;
    """)

    # 模型类型枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_type_enum') THEN
            CREATE TYPE model_type_enum AS ENUM (
                'decision_tree', 'random_forest', 'xgboost',
                'lightgbm', 'logistic_regression', 'catboost', 'neural_network'
            );
        END IF;
    END$$;
    """)

    # 框架枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'framework_enum') THEN
            CREATE TYPE framework_enum AS ENUM (
                'sklearn', 'xgboost', 'lightgbm', 'torch',
                'tensorflow', 'onnx', 'catboost'
            );
        END IF;
    END$$;
    """)

    # 模型状态枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'model_status_enum') THEN
            CREATE TYPE model_status_enum AS ENUM ('active', 'inactive', 'deprecated', 'archived');
        END IF;
    END$$;
    """)

    # 审计操作枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'audit_action_enum') THEN
            CREATE TYPE audit_action_enum AS ENUM (
                -- 模型生命周期
                'model_create', 'model_update', 'model_delete', 'model_query',
                'model_activate', 'model_deactivate', 'model_deprecate', 'model_archive',
                'model_restore', 'model_version_add', 'model_version_delete',
                'model_version_switch', 'model_promote', 'model_rollback',
                -- 模型运行时
                'model_load', 'model_unload', 'model_warm_up', 'model_inference',
                'model_batch_inference', 'model_download', 'model_save', 'model_migrate',
                -- A/B测试
                'ab_test_create', 'ab_test_update', 'ab_test_start', 'ab_test_pause',
                'ab_test_resume', 'ab_test_complete', 'ab_test_terminate',
                'ab_test_assignment', 'ab_test_record', 'ab_test_error',
                -- 认证授权
                'user_login', 'user_logout', 'user_password_change', 'user_password_reset',
                'auth_success', 'auth_failed', 'api_key_create', 'api_key_revoke',
                'api_key_update',
                -- 安全防护
                'cors_preflight', 'rate_limit_exceeded', 'ip_blocked',
                'invalid_signature', 'invalid_timestamp', 'request_too_large',
                -- 系统配置
                'config_create', 'config_update', 'config_delete', 'config_reload',
                -- 数据库管理
                'db_initialize', 'db_create_engine', 'db_get_session', 'db_health_check',
                'db_transaction', 'db_transaction_error', 'db_reconnect', 'db_init_schema',
                -- 复制监控
                'replication_status', 'sync_status', 'replication_slots',
                'replication_metrics', 'replication_alert',
                -- 数据管理
                'database_backup', 'database_restore', 'database_migrate',
                'data_export', 'data_import',
                -- 存储管理
                'file_upload', 'file_download', 'file_delete', 'file_copy',
                'file_move', 'file_list', 'file_metadata',
                -- 监控告警
                'monitoring_collect', 'alert_trigger', 'slow_request', 'slow_query',
                -- 审计日志
                'audit_log_query', 'audit_log_export',
                -- 性能监控
                'performance_metric', 'db_query_stats', 'cache_hit', 'cache_miss'
            );
        END IF;
    END$$;
    """)

    # 部署环境枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deployment_env_enum') THEN
            CREATE TYPE deployment_env_enum AS ENUM ('development', 'testing', 'staging', 'production');
        END IF;
    END$$;
    """)

    # A/B测试状态枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'abtest_status_enum') THEN
            CREATE TYPE abtest_status_enum AS ENUM ('draft', 'running', 'paused', 'completed', 'terminated');
        END IF;
    END$$;
    """)

    # 用户角色枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role_enum') THEN
            CREATE TYPE user_role_enum AS ENUM ('admin', 'developer', 'analyst', 'api_user');
        END IF;
    END$$;
    """)

    # 用户状态枚举
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_status_enum') THEN
            CREATE TYPE user_status_enum AS ENUM ('active', 'inactive', 'suspended');
        END IF;
    END$$;
    """)

    # ===================== 创建核心表 =====================

    # 1. 模型元数据表
    op.create_table(
        'model_metadata',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型唯一标识'),
        sa.Column('model_name', sa.String(length=100), nullable=False, comment='模型名称'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', PgEnum('scoring', 'fraud_detection', name='task_type_enum', create_type=False),
                  nullable=False, comment='任务类型: scoring-评分卡, fraud_detection-反欺诈'),
        sa.Column('model_type', PgEnum('decision_tree', 'random_forest', 'xgboost', 'lightgbm',
                                        'logistic_regression', 'catboost', 'neural_network',
                                        name='model_type_enum', create_type=False),
                  nullable=False, comment='模型算法类型'),
        sa.Column('framework', PgEnum('sklearn', 'xgboost', 'lightgbm', 'torch',
                                       'tensorflow', 'onnx', 'catboost',
                                       name='framework_enum', create_type=False),
                  nullable=False, comment='模型框架'),
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
        sa.Column('status', PgEnum('active', 'inactive', 'deprecated', 'archived',
                                    name='model_status_enum', create_type=False),
                  nullable=False, server_default='inactive', comment='模型状态'),
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
    op.create_index('idx_model_abtest', 'model_metadata', ['ab_test_group', 'status'],
                    schema='public')
    op.create_index('idx_model_created_at', 'model_metadata', ['created_at'],
                    schema='public')
    op.create_index('idx_model_task_type', 'model_metadata', ['task_type'],
                    schema='public')
    op.create_index('idx_model_type_framework', 'model_metadata', ['model_type', 'framework'],
                    schema='public')

    # 2. 模型版本历史表
    op.create_table(
        'model_version_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('operation', PgEnum('model_create', 'model_update', 'model_delete', 'model_query',
                                       'model_activate', 'model_deactivate', 'model_deprecate', 'model_archive',
                                       'model_restore', 'model_version_add', 'model_version_delete',
                                       'model_version_switch', 'model_promote', 'model_rollback',
                                       'model_load', 'model_unload', 'model_warm_up', 'model_inference',
                                       'model_batch_inference', 'model_download', 'model_save', 'model_migrate',
                                       'ab_test_create', 'ab_test_update', 'ab_test_start', 'ab_test_pause',
                                       'ab_test_resume', 'ab_test_complete', 'ab_test_terminate',
                                       'ab_test_assignment', 'ab_test_record', 'ab_test_error',
                                       'user_login', 'user_logout', 'user_password_change', 'user_password_reset',
                                       'auth_success', 'auth_failed', 'api_key_create', 'api_key_revoke',
                                       'api_key_update', 'cors_preflight', 'rate_limit_exceeded', 'ip_blocked',
                                       'invalid_signature', 'invalid_timestamp', 'request_too_large',
                                       'config_create', 'config_update', 'config_delete', 'config_reload',
                                       'db_initialize', 'db_create_engine', 'db_get_session', 'db_health_check',
                                       'db_transaction', 'db_transaction_error', 'db_reconnect', 'db_init_schema',
                                       'replication_status', 'sync_status', 'replication_slots',
                                       'replication_metrics', 'replication_alert',
                                       'database_backup', 'database_restore', 'database_migrate',
                                       'data_export', 'data_import',
                                       'file_upload', 'file_download', 'file_delete', 'file_copy',
                                       'file_move', 'file_list', 'file_metadata',
                                       'monitoring_collect', 'alert_trigger', 'slow_request', 'slow_query',
                                       'audit_log_query', 'audit_log_export',
                                       'performance_metric', 'db_query_stats', 'cache_hit', 'cache_miss',
                                       name='audit_action_enum', create_type=False),
                  nullable=False, comment='操作类型'),
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
    op.create_index('idx_history_operator', 'model_version_history', ['operator'],
                    schema='public')
    op.create_index('idx_history_operation', 'model_version_history', ['operation'],
                    schema='public')

    # 3. 模型部署表
    op.create_table(
        'model_deployments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('deployment_id', sa.String(length=50), nullable=False, comment='部署ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('environment', PgEnum('development', 'testing', 'staging', 'production',
                                         name='deployment_env_enum', create_type=False),
                  nullable=False, comment='部署环境'),
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
    op.create_index('idx_deployment_env', 'model_deployments', ['environment'],
                    schema='public')
    op.create_index('idx_deployment_model_env', 'model_deployments', ['model_id', 'environment'],
                    schema='public')

    # 4. API调用日志表
    op.create_table(
        'api_call_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('request_id', sa.String(length=50), nullable=False, comment='请求ID'),
        sa.Column('application_id', sa.String(length=50), nullable=False, comment='应用/申请ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', PgEnum('scoring', 'fraud_detection', name='task_type_enum', create_type=False),
                  nullable=False, comment='任务类型'),
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
    op.create_index('idx_api_app_model', 'api_call_logs', ['application_id', 'model_id'],
                    schema='public')
    op.create_index('idx_api_request_id', 'api_call_logs', ['request_id'],
                    schema='public')
    op.create_index('idx_api_status', 'api_call_logs', ['status_code'],
                    schema='public')
    op.create_index('idx_api_task_type', 'api_call_logs', ['task_type'],
                    schema='public')

    # 5. 模型性能监控表
    op.create_table(
        'model_performance_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('model_id', sa.String(length=50), nullable=False, comment='模型ID'),
        sa.Column('model_version', sa.String(length=20), nullable=False, comment='模型版本'),
        sa.Column('task_type', PgEnum('scoring', 'fraud_detection', name='task_type_enum', create_type=False),
                  nullable=False, comment='任务类型'),
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
        sa.Column('avg_score', sa.Float(), nullable=True, comment='平均评分'),
        sa.Column('score_distribution', postgresql.JSONB(), nullable=True, comment='评分分布'),
        sa.Column('score_bins', postgresql.JSONB(), nullable=True, comment='评分区间统计'),
        sa.Column('fraud_rate', sa.Float(), nullable=True, comment='欺诈率'),
        sa.Column('fraud_count', sa.Integer(), nullable=True, comment='欺诈数量'),
        sa.Column('risk_distribution', postgresql.JSONB(), nullable=True, comment='风险分布'),
        sa.Column('risk_levels', postgresql.JSONB(), nullable=True, comment='风险等级统计'),
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
    op.create_index('idx_performance_task_type', 'model_performance_metrics', ['task_type'],
                    schema='public')

    # 6. 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('audit_id', sa.String(length=50), nullable=False, comment='审计ID'),
        sa.Column('event_type', sa.String(length=50), nullable=False, comment='事件类型'),
        sa.Column('action', PgEnum('model_create', 'model_update', 'model_delete', 'model_query',
                                    'model_activate', 'model_deactivate', 'model_deprecate', 'model_archive',
                                    'model_restore', 'model_version_add', 'model_version_delete',
                                    'model_version_switch', 'model_promote', 'model_rollback',
                                    'model_load', 'model_unload', 'model_warm_up', 'model_inference',
                                    'model_batch_inference', 'model_download', 'model_save', 'model_migrate',
                                    'ab_test_create', 'ab_test_update', 'ab_test_start', 'ab_test_pause',
                                    'ab_test_resume', 'ab_test_complete', 'ab_test_terminate',
                                    'ab_test_assignment', 'ab_test_record', 'ab_test_error',
                                    'user_login', 'user_logout', 'user_password_change', 'user_password_reset',
                                    'auth_success', 'auth_failed', 'api_key_create', 'api_key_revoke',
                                    'api_key_update', 'cors_preflight', 'rate_limit_exceeded', 'ip_blocked',
                                    'invalid_signature', 'invalid_timestamp', 'request_too_large',
                                    'config_create', 'config_update', 'config_delete', 'config_reload',
                                    'db_initialize', 'db_create_engine', 'db_get_session', 'db_health_check',
                                    'db_transaction', 'db_transaction_error', 'db_reconnect', 'db_init_schema',
                                    'replication_status', 'sync_status', 'replication_slots',
                                    'replication_metrics', 'replication_alert',
                                    'database_backup', 'database_restore', 'database_migrate',
                                    'data_export', 'data_import',
                                    'file_upload', 'file_download', 'file_delete', 'file_copy',
                                    'file_move', 'file_list', 'file_metadata',
                                    'monitoring_collect', 'alert_trigger', 'slow_request', 'slow_query',
                                    'audit_log_query', 'audit_log_export',
                                    'performance_metric', 'db_query_stats', 'cache_hit', 'cache_miss',
                                    name='audit_action_enum', create_type=False),
                  nullable=False, comment='操作类型'),
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
    op.create_index('idx_audit_operator', 'audit_logs', ['operator'],
                    schema='public')
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'],
                    schema='public')
    op.create_index('idx_audit_event', 'audit_logs', ['event_type'],
                    schema='public')
    op.create_index('idx_audit_action', 'audit_logs', ['action'],
                    schema='public')

    # 7. A/B测试配置表
    op.create_table(
        'ab_test_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('test_id', sa.String(length=50), nullable=False, comment='测试ID'),
        sa.Column('test_name', sa.String(length=100), nullable=False, comment='测试名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='测试描述'),
        sa.Column('task_type', PgEnum('scoring', 'fraud_detection', name='task_type_enum', create_type=False),
                  nullable=False, comment='任务类型'),
        sa.Column('groups', postgresql.JSONB(), nullable=False, comment='测试组配置'),
        sa.Column('traffic_allocation', sa.Float(), nullable=False, server_default='100.0',
                  comment='流量分配百分比'),
        sa.Column('assignment_strategy', sa.String(length=20), nullable=False, server_default='random',
                  comment='分配策略'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False, comment='开始时间'),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True, comment='结束时间'),
        sa.Column('status', PgEnum('draft', 'running', 'paused', 'completed', 'terminated',
                                    name='abtest_status_enum', create_type=False),
                  nullable=False, server_default='draft', comment='测试状态'),
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
    op.create_index('idx_abtest_dates', 'ab_test_configs', ['start_date', 'end_date'],
                    schema='public')
    op.create_index('idx_abtest_task_type', 'ab_test_configs', ['task_type'],
                    schema='public')

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
    op.create_index('idx_ab_assign_time', 'ab_test_assignments', ['assigned_at'],
                    schema='public')
    op.create_index('idx_ab_assign_model', 'ab_test_assignments', ['model_id'],
                    schema='public')

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
        sa.Column('tenant_id', sa.String(length=50), nullable=True, comment='租户ID'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True, comment='生效开始时间'),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True, comment='生效结束时间'),
        sa.Column('updated_by', sa.String(length=50), nullable=False, comment='更新人'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.PrimaryKeyConstraint('id', name='pk_system_configs'),
        sa.UniqueConstraint('config_key', name='uq_config_key'),
        schema='public',
        comment='系统配置表'
    )
    op.create_index('idx_config_key', 'system_configs', ['config_key'], unique=True, schema='public')
    op.create_index('idx_config_category', 'system_configs', ['category'], schema='public')
    op.create_index('idx_config_tenant', 'system_configs', ['tenant_id'], schema='public')
    op.create_index('idx_config_updated_at', 'system_configs', ['updated_at'], schema='public')
    op.create_index('idx_config_tenant_key', 'system_configs', ['tenant_id', 'config_key'], unique=True,
                    schema='public')
    op.create_index('idx_config_effective', 'system_configs', ['effective_from', 'effective_to'], schema='public')

    # 10. 用户表
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('user_id', sa.String(length=50), nullable=False, comment='用户唯一标识'),
        sa.Column('username', sa.String(length=50), nullable=False, comment='用户名'),
        sa.Column('email', sa.String(length=100), nullable=False, comment='邮箱'),
        sa.Column('password_hash', sa.String(length=255), nullable=False, comment='密码哈希'),
        sa.Column('full_name', sa.String(length=100), nullable=True, comment='全名'),
        sa.Column('avatar', sa.String(length=500), nullable=True, comment='头像URL'),
        sa.Column('phone', sa.String(length=20), nullable=True, comment='手机号'),
        sa.Column('role', PgEnum('admin', 'developer', 'analyst', 'api_user',
                                   name='user_role_enum', create_type=False),
                  nullable=False, server_default='api_user', comment='用户角色'),
        sa.Column('permissions', postgresql.JSONB(), default=list, nullable=True, comment='额外权限列表'),
        sa.Column('status', PgEnum('active', 'inactive', 'suspended',
                                    name='user_status_enum', create_type=False),
                  nullable=False, server_default='active', comment='用户状态'),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True, comment='最后登录时间'),
        sa.Column('last_login_ip', postgresql.INET(), nullable=True, comment='最后登录IP'),
        sa.Column('last_password_change', sa.DateTime(timezone=True), nullable=True, comment='最后密码修改时间'),
        sa.Column('password_reset_token', sa.String(length=100), nullable=True, comment='密码重置令牌'),
        sa.Column('password_reset_expires', sa.DateTime(timezone=True), nullable=True, comment='密码重置过期时间'),
        sa.Column('email_verification_token', sa.String(length=100), nullable=True, comment='邮箱验证令牌'),
        sa.Column('email_verification_expires', sa.DateTime(timezone=True), nullable=True, comment='邮箱验证过期时间'),
        sa.Column('login_attempts', sa.BigInteger(), nullable=False, server_default='0', comment='登录尝试次数'),
        sa.Column('failed_login_attempts', sa.BigInteger(), nullable=False, server_default='0', comment='失败登录次数'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True, comment='锁定截止时间'),
        sa.Column('extra_metadata', postgresql.JSONB(), nullable=True, comment='扩展元数据'),
        sa.Column('created_by', sa.String(length=50), nullable=True, comment='创建人'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id', name='pk_users'),
        sa.UniqueConstraint('user_id', name='uq_user_id'),
        sa.UniqueConstraint('username', name='uq_username'),
        sa.UniqueConstraint('email', name='uq_email'),
        schema='public',
        comment='用户表'
    )
    op.create_index('idx_user_email', 'users', ['email'], unique=True, schema='public')
    op.create_index('idx_user_username', 'users', ['username'], unique=True, schema='public')
    op.create_index('idx_user_status', 'users', ['status'], schema='public')
    op.create_index('idx_user_role', 'users', ['role'], schema='public')
    op.create_index('idx_user_created_at', 'users', ['created_at'], schema='public')
    op.create_index('idx_user_last_login', 'users', ['last_login_at'], schema='public')

    # 11. API密钥表
    op.create_table(
        'api_keys',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('api_key_id', sa.String(length=50), nullable=False, comment='API密钥唯一标识'),
        sa.Column('user_id', sa.String(length=50), nullable=False, comment='所属用户ID'),
        sa.Column('name', sa.String(length=100), nullable=False, comment='密钥名称'),
        sa.Column('key', sa.String(length=255), nullable=False, comment='API密钥'),
        sa.Column('key_prefix', sa.String(length=10), nullable=True, comment='密钥前缀'),
        sa.Column('permissions', postgresql.JSONB(), default=list, nullable=True, comment='权限列表'),
        sa.Column('roles', postgresql.JSONB(), default=list, nullable=True, comment='角色列表'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true'), comment='是否激活'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True, comment='最后使用时间'),
        sa.Column('allowed_ips', postgresql.JSONB(), default=list, nullable=True, comment='IP白名单'),
        sa.Column('allowed_origins', postgresql.JSONB(), default=list, nullable=True, comment='域名白名单'),
        sa.Column('rate_limit', postgresql.JSONB(), nullable=True, comment='自定义限流配置'),
        sa.Column('extra_metadata', postgresql.JSONB(), nullable=True, comment='扩展元数据'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('created_by', sa.String(length=50), nullable=False, comment='创建人'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['user_id'], ['public.users.user_id'],
                                ondelete='CASCADE', name='fk_api_key_user'),
        sa.PrimaryKeyConstraint('id', name='pk_api_keys'),
        sa.UniqueConstraint('api_key_id', name='uq_api_key_id'),
        sa.UniqueConstraint('key', name='uq_api_key'),
        schema='public',
        comment='API密钥表'
    )
    op.create_index('idx_api_key_key', 'api_keys', ['key'], unique=True, schema='public')
    op.create_index('idx_api_key_user', 'api_keys', ['user_id'], schema='public')
    op.create_index('idx_api_key_active', 'api_keys', ['is_active'], schema='public')
    op.create_index('idx_api_key_expires', 'api_keys', ['expires_at'], schema='public')


def downgrade() -> None:
    """降级数据库到上一个版本"""

    # 删除表（按外键依赖的反向顺序）
    op.drop_table('api_keys', schema='public')
    op.drop_table('users', schema='public')
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
    op.execute('DROP TYPE IF EXISTS public.user_role_enum CASCADE')
    op.execute('DROP TYPE IF EXISTS public.user_status_enum CASCADE')