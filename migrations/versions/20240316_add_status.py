# Datamind/migrations/versions/20240316_add_status.py
"""添加状态字段

修订版本ID: 20240316_add_status
父修订版本: 20240315_initial
创建日期: 2024-03-16 11:30:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20240316_add_status'    # 修订版本标识符
down_revision = '20240315_initial'  # 依赖于初始迁移
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：为模型表添加状态相关字段"""

    # 1. 添加状态索引（如果尚未创建）
    # 使用 IF NOT EXISTS 语法确保索引只创建一次
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_model_status') THEN
            CREATE INDEX idx_model_status ON public.model_metadata (status);
        END IF;
    END$$;
    """)
    op.execute("COMMENT ON INDEX public.idx_model_status IS '模型状态索引';")

    # 2. 为 model_version_history 表添加状态快照字段
    op.add_column('model_version_history',
                  sa.Column('status_snapshot', sa.String(length=20), nullable=True,
                            comment='操作时的状态快照'),
                  schema='public'
                  )

    # 3. 为 model_deployments 表添加部署状态字段
    op.add_column('model_deployments',
                  sa.Column('deployment_status', sa.String(length=20),
                            nullable=True, server_default='pending',
                            comment='部署状态: pending-等待中, deploying-部署中, success-成功, failed-失败'),
                  schema='public'
                  )

    # 4. 添加部署状态索引
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_deployment_status') THEN
            CREATE INDEX idx_deployment_status ON public.model_deployments (deployment_status);
        END IF;
    END$$;
    """)
    op.execute("COMMENT ON INDEX public.idx_deployment_status IS '部署状态索引';")


def downgrade() -> None:
    """降级：移除状态相关字段"""

    # 1. 删除部署状态索引
    op.execute("DROP INDEX IF EXISTS public.idx_deployment_status")

    # 2. 删除 model_deployments 的 deployment_status 字段
    op.drop_column('model_deployments', 'deployment_status', schema='public')

    # 3. 删除 model_version_history 的 status_snapshot 字段
    op.drop_column('model_version_history', 'status_snapshot', schema='public')

    # 4. 删除模型状态索引
    op.execute("DROP INDEX IF EXISTS public.idx_model_status")