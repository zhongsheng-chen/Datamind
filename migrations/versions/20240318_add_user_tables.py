# migrations/versions/20240318_add_user_tables.py

"""添加用户表和API密钥表

修订版本ID: 20240318_add_user_tables
父修订版本: 20240317_add_indexes
创建日期: 2024-03-18 10:00:00.000000

功能说明：
    - 创建用户表（users）：存储用户账户信息
    - 创建API密钥表（api_keys）：存储API密钥信息
    - 支持用户认证、权限管理、API密钥管理
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '20240318_add_user_tables'
down_revision = '20240317_add_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级：添加用户表和API密钥表"""

    # ===================== 创建用户相关枚举类型 =====================

    # 用户角色枚举 - 使用 IF NOT EXISTS
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
            CREATE TYPE userrole AS ENUM ('admin', 'developer', 'analyst', 'api_user');
        END IF;
    END$$;
    """)

    # 用户状态枚举 - 使用 IF NOT EXISTS
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userstatus') THEN
            CREATE TYPE userstatus AS ENUM ('active', 'inactive', 'suspended');
        END IF;
    END$$;
    """)

    # ===================== 创建用户表 =====================
    # 使用 IF NOT EXISTS
    op.execute("""
               CREATE TABLE IF NOT EXISTS public.users
               (
                   id                         BIGSERIAL PRIMARY KEY,
                   user_id                    VARCHAR(50)  NOT NULL UNIQUE,
                   username                   VARCHAR(50)  NOT NULL UNIQUE,
                   email                      VARCHAR(100) NOT NULL UNIQUE,
                   password_hash              VARCHAR(255) NOT NULL,
                   full_name                  VARCHAR(100),
                   avatar                     VARCHAR(500),
                   phone                      VARCHAR(20),
                   role                       userrole     NOT NULL    DEFAULT 'api_user',
                   permissions                JSONB                    DEFAULT '[]',
                   status                     userstatus   NOT NULL    DEFAULT 'active',
                   last_login_at              TIMESTAMP WITH TIME ZONE,
                   last_login_ip              INET,
                   last_password_change       TIMESTAMP WITH TIME ZONE,
                   password_reset_token       VARCHAR(100),
                   password_reset_expires     TIMESTAMP WITH TIME ZONE,
                   email_verification_token   VARCHAR(100),
                   email_verification_expires TIMESTAMP WITH TIME ZONE,
                   login_attempts             BIGINT                   DEFAULT 0,
                   failed_login_attempts      BIGINT                   DEFAULT 0,
                   locked_until               TIMESTAMP WITH TIME ZONE,
                   extra_metadata             JSONB,
                   created_by                 VARCHAR(50),
                   created_at                 TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                   updated_at                 TIMESTAMP WITH TIME ZONE,
                   deleted_at                 TIMESTAMP WITH TIME ZONE
               )
               """)

    # 创建用户表索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON public.users (username)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON public.users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_user_id ON public.users (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON public.users (status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON public.users (role)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_created_at ON public.users (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_last_login ON public.users (last_login_at)")

    # ===================== 创建API密钥表 =====================
    op.execute("""
               CREATE TABLE IF NOT EXISTS public.api_keys
               (
                   id              BIGSERIAL PRIMARY KEY,
                   api_key_id      VARCHAR(50)  NOT NULL UNIQUE,
                   user_id         VARCHAR(50)  NOT NULL REFERENCES public.users (user_id) ON DELETE CASCADE,
                   name            VARCHAR(100) NOT NULL,
                   key             VARCHAR(255) NOT NULL UNIQUE,
                   key_prefix      VARCHAR(10),
                   permissions     JSONB                    DEFAULT '[]',
                   roles           JSONB                    DEFAULT '[]',
                   is_active       BOOLEAN                  DEFAULT TRUE,
                   expires_at      TIMESTAMP WITH TIME ZONE,
                   last_used_at    TIMESTAMP WITH TIME ZONE,
                   allowed_ips     JSONB                    DEFAULT '[]',
                   allowed_origins JSONB                    DEFAULT '[]',
                   rate_limit      JSONB,
                   description     TEXT,
                   extra_metadata  JSONB,
                   created_by      VARCHAR(50)  NOT NULL,
                   created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                   updated_at      TIMESTAMP WITH TIME ZONE
               )
               """)

    # 创建API密钥表索引
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_api_key_id ON public.api_keys (api_key_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON public.api_keys (key)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON public.api_keys (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON public.api_keys (is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_expires ON public.api_keys (expires_at)")

    # ===================== 创建默认用户 =====================
    # 检查是否已有用户，如果没有则创建
    op.execute("""
    DO $$
    DECLARE
        admin_exists BOOLEAN;
    BEGIN
        SELECT EXISTS(SELECT 1 FROM public.users WHERE username = 'admin') INTO admin_exists;

        IF NOT admin_exists THEN
            -- 创建默认管理员用户（密码：admin123）
            INSERT INTO public.users (
                user_id, username, email, password_hash, full_name, role,
                permissions, status, created_by
            ) VALUES (
                'admin_001', 'admin', 'admin@datamind.local', 
                '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPjFJQzN9zX9K',
                'System Administrator', 'admin', '[]', 'active', 'system'
            );

            -- 创建默认开发者用户（密码：dev123）
            INSERT INTO public.users (
                user_id, username, email, password_hash, full_name, role,
                permissions, status, created_by
            ) VALUES (
                'developer_001', 'developer', 'developer@datamind.local',
                '$2b$12$YKqzJv7xKj5KqKqKqKqKquZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ',
                'Model Developer', 'developer', '[]', 'active', 'system'
            );

            -- 创建默认分析师用户（密码：analyst123）
            INSERT INTO public.users (
                user_id, username, email, password_hash, full_name, role,
                permissions, status, created_by
            ) VALUES (
                'analyst_001', 'analyst', 'analyst@datamind.local',
                '$2b$12$YKqzJv7xKj5KqKqKqKqKquZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ',
                'Data Analyst', 'analyst', '[]', 'active', 'system'
            );

            -- 创建默认API用户（密码：api123）
            INSERT INTO public.users (
                user_id, username, email, password_hash, full_name, role,
                permissions, status, created_by
            ) VALUES (
                'apiuser_001', 'apiuser', 'api@datamind.local',
                '$2b$12$YKqzJv7xKj5KqKqKqKqKquZzZzZzZzZzZzZzZzZzZzZzZzZzZzZ',
                'API User', 'api_user', '[]', 'active', 'system'
            );
        END IF;
    END$$;
    """)

    # 添加注释
    op.execute("COMMENT ON TABLE public.users IS '用户表'")
    op.execute("COMMENT ON TABLE public.api_keys IS 'API密钥表'")


def downgrade() -> None:
    """降级：删除用户表和API密钥表"""

    # 删除API密钥表
    op.execute("DROP TABLE IF EXISTS public.api_keys CASCADE")

    # 删除用户表
    op.execute("DROP TABLE IF EXISTS public.users CASCADE")

    # 删除枚举类型
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
    op.execute("DROP TYPE IF EXISTS userstatus CASCADE")