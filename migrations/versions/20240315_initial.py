# datamind/migrations/versions/20240315_initial.py
"""initial migration

Revision ID: 20240315_initial
Revises:
Create Date: 2024-03-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20240315_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建枚举类型
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE task_type_enum AS ENUM ('scoring', 'fraud_detection');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE model_type_enum AS ENUM (
            'decision_tree', 'random_forest', 'xgboost', 
            'lightgbm', 'logistic_regression', 'catboost', 'neural_network'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE framework_enum AS ENUM (
            'sklearn', 'xgboost', 'lightgbm', 'torch', 
            'tensorflow', 'onnx', 'catboost'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE model_status_enum AS ENUM ('active', 'inactive', 'deprecated', 'archived');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE audit_action_enum AS ENUM (
            'CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE',
            'DEPRECATE', 'ARCHIVE', 'RESTORE', 'VERSION_ADD',
            'VERSION_SWITCH', 'DOWNLOAD', 'INFERENCE', 'PROMOTE',
            'ROLLBACK', 'CONFIG_CHANGE'
        );
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE deployment_env_enum AS ENUM ('development', 'testing', 'staging', 'production');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    op.execute("""
    DO $$ BEGIN
        CREATE TYPE abtest_status_enum AS ENUM ('draft', 'running', 'paused', 'completed', 'terminated');
    EXCEPTION
        WHEN duplicate_object THEN null;
    END $$;
    """)

    # 创建模型元数据表
    op.create_table(
        'model_metadata',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('task_type', sa.Enum('scoring', 'fraud_detection', name='task_type_enum'), nullable=False),
        sa.Column('model_type', sa.Enum(
            'decision_tree', 'random_forest', 'xgboost', 'lightgbm',
            'logistic_regression', 'catboost', 'neural_network',
            name='model_type_enum'
        ), nullable=False),
        sa.Column('framework', sa.Enum(
            'sklearn', 'xgboost', 'lightgbm', 'torch',
            'tensorflow', 'onnx', 'catboost', name='framework_enum'
        ), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('input_features', postgresql.JSONB(), nullable=False),
        sa.Column('output_schema', postgresql.JSONB(), nullable=False),
        sa.Column('model_params', postgresql.JSONB(), nullable=True),
        sa.Column('feature_importance', postgresql.JSONB(), nullable=True),
        sa.Column('performance_metrics', postgresql.JSONB(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'deprecated', 'archived', name='model_status_enum'),
                  nullable=True, server_default='inactive'),
        sa.Column('is_production', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('ab_test_group', sa.String(length=50), nullable=True),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deprecated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('metadata_json', postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_name', 'model_version', name='uq_model_name_version'),
        schema='public'
    )
    op.create_index('idx_model_status', 'model_metadata', ['status', 'is_production'], schema='public')
    op.create_index('idx_model_name_version', 'model_metadata', ['model_name', 'model_version'],
                    unique=True, schema='public')
    op.create_index('idx_model_created_at', 'model_metadata', ['created_at'], schema='public')
    op.create_index('idx_model_task_type', 'model_metadata', ['task_type'], schema='public')
    op.create_index('idx_model_type_framework', 'model_metadata', ['model_type', 'framework'], schema='public')

    # 创建模型版本历史表
    op.create_table(
        'model_version_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('operation', sa.Enum(
            'CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE',
            'DEPRECATE', 'ARCHIVE', 'RESTORE', 'VERSION_ADD',
            'VERSION_SWITCH', 'DOWNLOAD', 'INFERENCE', 'PROMOTE',
            'ROLLBACK', 'CONFIG_CHANGE', name='audit_action_enum'
        ), nullable=False),
        sa.Column('operator', sa.String(length=50), nullable=False),
        sa.Column('operator_ip', postgresql.INET(), nullable=True),
        sa.Column('operation_time', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('metadata_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )
    op.create_index('idx_history_model_time', 'model_version_history', ['model_id', 'operation_time'], schema='public')
    op.create_index('idx_history_operator', 'model_version_history', ['operator'], schema='public')
    op.create_index('idx_history_operation', 'model_version_history', ['operation'], schema='public')

    # 创建部署表
    op.create_table(
        'model_deployments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('deployment_id', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('environment', sa.Enum('development', 'testing', 'staging', 'production',
                                         name='deployment_env_enum'), nullable=False),
        sa.Column('endpoint_url', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('deployment_config', postgresql.JSONB(), nullable=True),
        sa.Column('resources', postgresql.JSONB(), nullable=True),
        sa.Column('deployed_by', sa.String(length=50), nullable=False),
        sa.Column('deployed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_status', sa.String(length=20), nullable=True),
        sa.Column('health_check_details', postgresql.JSONB(), nullable=True),
        sa.Column('traffic_weight', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('canary_config', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('deployment_id'),
        schema='public'
    )
    op.create_index('idx_deployment_active', 'model_deployments', ['is_active'], schema='public')
    op.create_index('idx_deployment_env', 'model_deployments', ['environment'], schema='public')
    op.create_index('idx_deployment_model_env', 'model_deployments', ['model_id', 'environment'], schema='public')

    # 创建API调用日志表
    op.create_table(
        'api_call_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('request_id', sa.String(length=50), nullable=False),
        sa.Column('application_id', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('task_type', sa.Enum('scoring', 'fraud_detection', name='task_type_enum'), nullable=False),
        sa.Column('endpoint', sa.String(length=100), nullable=False),
        sa.Column('request_data', postgresql.JSONB(), nullable=True),
        sa.Column('response_data', postgresql.JSONB(), nullable=True),
        sa.Column('request_headers', postgresql.JSONB(), nullable=True),
        sa.Column('response_headers', postgresql.JSONB(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=False),
        sa.Column('model_inference_time_ms', sa.Integer(), nullable=True),
        sa.Column('total_time_ms', sa.Integer(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('user_agent', sa.String(length=200), nullable=True),
        sa.Column('api_key', sa.String(length=100), nullable=True),
        sa.Column('user_id', sa.String(length=50), nullable=True),
        sa.Column('cost_credits', sa.Numeric(10, 4), nullable=True),
        sa.Column('billing_info', postgresql.JSONB(), nullable=True),
        sa.Column('business_metrics', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('partition_date', sa.DateTime(), server_default=sa.text('date_trunc(\'day\', now())'),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_id'),
        schema='public'
    )
    op.create_index('idx_api_time', 'api_call_logs', ['created_at'], schema='public')
    op.create_index('idx_api_app_model', 'api_call_logs', ['application_id', 'model_id'], schema='public')
    op.create_index('idx_api_request_id', 'api_call_logs', ['request_id'], schema='public')
    op.create_index('idx_api_status', 'api_call_logs', ['status_code'], schema='public')
    op.create_index('idx_api_task_type', 'api_call_logs', ['task_type'], schema='public')

    # 创建性能监控表
    op.create_table(
        'model_performance_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('model_version', sa.String(length=20), nullable=False),
        sa.Column('task_type', sa.Enum('scoring', 'fraud_detection', name='task_type_enum'), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('total_requests', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('error_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('timeout_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('avg_response_time_ms', sa.Float(), nullable=True),
        sa.Column('p50_response_time_ms', sa.Float(), nullable=True),
        sa.Column('p95_response_time_ms', sa.Float(), nullable=True),
        sa.Column('p99_response_time_ms', sa.Float(), nullable=True),
        sa.Column('max_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('min_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('avg_score', sa.Float(), nullable=True),
        sa.Column('score_distribution', postgresql.JSONB(), nullable=True),
        sa.Column('score_bins', postgresql.JSONB(), nullable=True),
        sa.Column('fraud_rate', sa.Float(), nullable=True),
        sa.Column('fraud_count', sa.Integer(), nullable=True),
        sa.Column('risk_distribution', postgresql.JSONB(), nullable=True),
        sa.Column('risk_levels', postgresql.JSONB(), nullable=True),
        sa.Column('feature_importance_drift', postgresql.JSONB(), nullable=True),
        sa.Column('avg_cpu_usage', sa.Float(), nullable=True),
        sa.Column('avg_memory_usage', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('model_id', 'model_version', 'date', name='uq_model_metric_date'),
        schema='public'
    )
    op.create_index('idx_performance_model_date', 'model_performance_metrics', ['model_id', 'date'], schema='public')
    op.create_index('idx_performance_task_type', 'model_performance_metrics', ['task_type'], schema='public')

    # 创建审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('audit_id', sa.String(length=50), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.Enum(
            'CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE',
            'DEPRECATE', 'ARCHIVE', 'RESTORE', 'VERSION_ADD',
            'VERSION_SWITCH', 'DOWNLOAD', 'INFERENCE', 'PROMOTE',
            'ROLLBACK', 'CONFIG_CHANGE', name='audit_action_enum'
        ), nullable=False),
        sa.Column('operator', sa.String(length=50), nullable=False),
        sa.Column('operator_ip', postgresql.INET(), nullable=True),
        sa.Column('operator_role', sa.String(length=50), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=50), nullable=True),
        sa.Column('resource_name', sa.String(length=100), nullable=True),
        sa.Column('before_state', postgresql.JSONB(), nullable=True),
        sa.Column('after_state', postgresql.JSONB(), nullable=True),
        sa.Column('changes', postgresql.JSONB(), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('model_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audit_id'),
        schema='public'
    )
    op.create_index('idx_audit_time', 'audit_logs', ['created_at'], schema='public')
    op.create_index('idx_audit_operator', 'audit_logs', ['operator'], schema='public')
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'], schema='public')
    op.create_index('idx_audit_action', 'audit_logs', ['action'], schema='public')

    # 创建A/B测试配置表
    op.create_table(
        'ab_test_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('test_id', sa.String(length=50), nullable=False),
        sa.Column('test_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.Enum('scoring', 'fraud_detection', name='task_type_enum'), nullable=False),
        sa.Column('groups', postgresql.JSONB(), nullable=False),
        sa.Column('traffic_allocation', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('assignment_strategy', sa.String(length=20), nullable=True, server_default='random'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.Enum('draft', 'running', 'paused', 'completed', 'terminated',
                                    name='abtest_status_enum'), nullable=True, server_default='draft'),
        sa.Column('created_by', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metrics', postgresql.JSONB(), nullable=True),
        sa.Column('winning_criteria', postgresql.JSONB(), nullable=True),
        sa.Column('results', postgresql.JSONB(), nullable=True),
        sa.Column('winning_group', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('test_id'),
        schema='public'
    )
    op.create_index('idx_abtest_status', 'ab_test_configs', ['status'], schema='public')
    op.create_index('idx_abtest_dates', 'ab_test_configs', ['start_date', 'end_date'], schema='public')
    op.create_index('idx_abtest_task_type', 'ab_test_configs', ['task_type'], schema='public')

    # 创建A/B测试分配表
    op.create_table(
        'ab_test_assignments',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('test_id', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=50), nullable=False),
        sa.Column('group_name', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=50), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('assignment_hash', sa.String(length=64), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['public.model_metadata.model_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_id'], ['public.ab_test_configs.test_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='public'
    )
    op.create_index('idx_ab_assign_test_user', 'ab_test_assignments', ['test_id', 'user_id'], schema='public')
    op.create_index('idx_ab_assign_time', 'ab_test_assignments', ['assigned_at'], schema='public')
    op.create_index('idx_ab_assign_model', 'ab_test_assignments', ['model_id'], schema='public')

    # 创建系统配置表
    op.create_table(
        'system_configs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('config_key', sa.String(length=100), nullable=False),
        sa.Column('config_value', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('is_encrypted', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('updated_by', sa.String(length=50), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('config_key'),
        schema='public'
    )
    op.create_index('idx_config_key', 'system_configs', ['config_key'], unique=True, schema='public')
    op.create_index('idx_config_category', 'system_configs', ['category'], schema='public')


def downgrade() -> None:
    # 删除表
    op.drop_table('ab_test_assignments', schema='public')
    op.drop_table('ab_test_configs', schema='public')
    op.drop_table('audit_logs', schema='public')
    op.drop_table('model_performance_metrics', schema='public')
    op.drop_table('api_call_logs', schema='public')
    op.drop_table('model_deployments', schema='public')
    op.drop_table('model_version_history', schema='public')
    op.drop_table('model_metadata', schema='public')
    op.drop_table('system_configs', schema='public')

    # 删除枚举类型
    op.execute('DROP TYPE IF EXISTS abtest_status_enum')
    op.execute('DROP TYPE IF EXISTS deployment_env_enum')
    op.execute('DROP TYPE IF EXISTS audit_action_enum')
    op.execute('DROP TYPE IF EXISTS model_status_enum')
    op.execute('DROP TYPE IF EXISTS framework_enum')
    op.execute('DROP TYPE IF EXISTS model_type_enum')
    op.execute('DROP TYPE IF EXISTS task_type_enum')