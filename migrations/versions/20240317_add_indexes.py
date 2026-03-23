# migrations/versions/20240317_add_indexes.py

"""添加性能优化索引

修订版本ID: 20240317_add_indexes
父修订版本: 20240316_add_status
创建日期: 2024-03-17 14:20:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20240317_add_indexes'
down_revision = '20240316_add_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：添加各种性能优化索引"""

    # ==================== 安装必要的扩展 ====================
    # pg_trgm 扩展需要在事务外执行
    op.execute("COMMIT")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("BEGIN")

    # ==================== 模型表索引 ====================

    # 1. 模型名称模糊搜索索引（GIN）- CONCURRENTLY 需要在事务外执行
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_model_name_gin
        ON public.model_metadata USING gin (model_name gin_trgm_ops)
    """)
    op.execute("BEGIN")
    op.execute("COMMENT ON INDEX idx_model_name_gin IS '模型名称模糊搜索索引（基于 trigram）';")

    # 2. 创建时间和状态复合索引 - 普通索引可以在事务内创建
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_created_status
        ON public.model_metadata (created_at, status)
    """)
    op.execute("COMMENT ON INDEX public.idx_model_created_status IS '创建时间和状态复合索引';")

    # 3. 生产模型和部署时间索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_production_deployed
        ON public.model_metadata (is_production, deployed_at)
    """)
    op.execute("COMMENT ON INDEX public.idx_model_production_deployed IS '生产模型和部署时间复合索引';")

    # ==================== API调用日志表索引 ====================

    # 4. 应用ID和创建时间复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_app_created
        ON public.api_call_logs (application_id, created_at)
    """)
    op.execute("COMMENT ON INDEX public.idx_api_app_created IS '应用ID和创建时间复合索引';")

    # 5. 模型ID和状态码复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_model_status
        ON public.api_call_logs (model_id, status_code)
    """)
    op.execute("COMMENT ON INDEX public.idx_api_model_status IS '模型ID和状态码复合索引';")

    # 6. 处理时间索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_processing_time
        ON public.api_call_logs (processing_time_ms)
    """)
    op.execute("COMMENT ON INDEX public.idx_api_processing_time IS '处理时间索引';")

    # 7. 请求数据的 GIN 索引 - CONCURRENTLY 需要在事务外执行
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_request_data_gin
        ON public.api_call_logs USING gin (request_data)
    """)
    op.execute("BEGIN")
    op.execute("COMMENT ON INDEX idx_api_request_data_gin IS '请求数据JSON字段GIN索引';")

    # 8. 响应数据的 GIN 索引 - CONCURRENTLY 需要在事务外执行
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_api_response_data_gin
        ON public.api_call_logs USING gin (response_data)
    """)
    op.execute("BEGIN")
    op.execute("COMMENT ON INDEX idx_api_response_data_gin IS '响应数据JSON字段GIN索引';")

    # ==================== 审计日志表索引 ====================

    # 9. 操作类型和结果复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_action_result
        ON public.audit_logs (action, result)
    """)
    op.execute("COMMENT ON INDEX public.idx_audit_action_result IS '操作类型和结果复合索引';")

    # 10. 资源类型和创建时间复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_resource_time
        ON public.audit_logs (resource_type, created_at)
    """)
    op.execute("COMMENT ON INDEX public.idx_audit_resource_time IS '资源类型和创建时间复合索引';")

    # 11. 详情字段的 GIN 索引 - CONCURRENTLY 需要在事务外执行
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_details_gin
        ON public.audit_logs USING gin (details)
    """)
    op.execute("BEGIN")
    op.execute("COMMENT ON INDEX idx_audit_details_gin IS '审计详情JSON字段GIN索引';")

    # ==================== 性能监控表索引 ====================

    # 12. 日期和任务类型复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_date_task
        ON public.model_performance_metrics (date, task_type)
    """)
    op.execute("COMMENT ON INDEX public.idx_performance_date_task IS '日期和任务类型复合索引';")

    # 13. 平均响应时间索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_performance_avg_response
        ON public.model_performance_metrics (avg_response_time_ms)
    """)
    op.execute("COMMENT ON INDEX public.idx_performance_avg_response IS '平均响应时间索引';")

    # ==================== A/B测试表索引 ====================

    # 14. 测试ID和分配时间复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_test_assign
        ON public.ab_test_assignments (test_id, assigned_at)
    """)
    op.execute("COMMENT ON INDEX public.idx_ab_test_assign IS '测试ID和分配时间复合索引';")

    # 15. 过期时间索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ab_expires_at
        ON public.ab_test_assignments (expires_at)
    """)
    op.execute("COMMENT ON INDEX public.idx_ab_expires_at IS '过期时间索引';")

    # ==================== 系统配置表索引 ====================

    # 16. 分类和版本复合索引
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_config_category_version
        ON public.system_configs (category, version)
    """)
    op.execute("COMMENT ON INDEX public.idx_config_category_version IS '分类和版本复合索引';")

    # 17. 配置值的 GIN 索引 - CONCURRENTLY 需要在事务外执行
    op.execute("COMMIT")
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_config_value_gin
        ON public.system_configs USING gin (config_value)
    """)
    op.execute("BEGIN")
    op.execute("COMMENT ON INDEX idx_config_value_gin IS '配置值JSON字段GIN索引';")


def downgrade() -> None:
    """降级：删除所有添加的索引"""

    # 删除索引（不需要 CONCURRENTLY）
    op.execute('DROP INDEX IF EXISTS idx_config_value_gin')
    op.execute('DROP INDEX IF EXISTS idx_audit_details_gin')
    op.execute('DROP INDEX IF EXISTS idx_api_response_data_gin')
    op.execute('DROP INDEX IF EXISTS idx_api_request_data_gin')
    op.execute('DROP INDEX IF EXISTS idx_model_name_gin')
    op.execute('DROP INDEX IF EXISTS public.idx_config_category_version')
    op.execute('DROP INDEX IF EXISTS public.idx_ab_expires_at')
    op.execute('DROP INDEX IF EXISTS public.idx_ab_test_assign')
    op.execute('DROP INDEX IF EXISTS public.idx_performance_avg_response')
    op.execute('DROP INDEX IF EXISTS public.idx_performance_date_task')
    op.execute('DROP INDEX IF EXISTS public.idx_audit_resource_time')
    op.execute('DROP INDEX IF EXISTS public.idx_audit_action_result')
    op.execute('DROP INDEX IF EXISTS public.idx_api_processing_time')
    op.execute('DROP INDEX IF EXISTS public.idx_api_model_status')
    op.execute('DROP INDEX IF EXISTS public.idx_api_app_created')
    op.execute('DROP INDEX IF EXISTS public.idx_model_production_deployed')
    op.execute('DROP INDEX IF EXISTS public.idx_model_created_status')

    op.execute("DROP EXTENSION IF EXISTS pg_trgm")