# datamind/db/models/system.py

"""系统状态表

保存 Datamind 的一次性初始化状态，防止系统通过删除用户重新开放初始化入口。

核心功能：
  - SystemState: 系统初始化状态表

使用示例：
  from datamind.db.models.system import SystemState

  state = SystemState(
      system_id="datamind",
      initialized=False,
  )
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Index,
    String,
    text,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class SystemState(
    IdMixin,
    TimestampMixin,
    Base,
):
    """系统状态表"""

    __tablename__ = "systems"

    __table_args__ = (
        Index(
            "uk_systems_system_id",
            "system_id",
            unique=True,
        ),
        CheckConstraint(
            "system_id = 'datamind'",
            name="system_id_valid",
        ),
        CheckConstraint(
            (
                "(initialized = false "
                "AND initialized_at IS NULL "
                "AND initialized_by IS NULL) "
                "OR "
                "(initialized = true "
                "AND initialized_at IS NOT NULL "
                "AND initialized_by IS NOT NULL)"
            ),
            name="initialization_state_valid",
        ),
    )

    system_id = Column(
        String(32),
        nullable=False,
        comment="系统标识",
    )

    initialized = Column(
        Boolean,
        nullable=False,
        server_default=text(
            "false"
        ),
        comment="是否已完成系统初始化",
    )

    initialized_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        comment="系统初始化完成时间",
    )

    initialized_by = Column(
        String(64),
        nullable=True,
        comment="系统初始化操作者",
    )

    def __repr__(
            self,
    ) -> str:
        """返回系统状态字符串表示"""
        return (
            f"<SystemState("
            f"system_id='{self.system_id}', "
            f"initialized={self.initialized}"
            f")>"
        )
