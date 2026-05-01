"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

说明：
本文件由 Alembic 自动生成，请谨慎修改。
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    """升级数据库结构（upgrade）"""
    ${upgrades if upgrades else "raise NotImplementedError('未定义 upgrade 操作')"}


def downgrade() -> None:
    """回滚数据库结构（downgrade）"""
    ${downgrades if downgrades else "raise NotImplementedError('未定义 downgrade 操作')"}