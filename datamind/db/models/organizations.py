"""机构表.

记录用户所属机构的稳定标识、业务编码和显示名称。

核心功能：
  - Organization: 机构记录

使用示例：
  from datamind.db.models.organizations import Organization

  organization = Organization(
      organization_id="org_0123456789abcdef",
      code="HQ",
      name="总行",
  )
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    String,
    true,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Organization(
    IdMixin,
    TimestampMixin,
    Base,
):
    """机构表."""

    __tablename__ = "organizations"

    __table_args__ = (
        CheckConstraint(
            "code IS NULL OR btrim(code) <> ''",
            name="code_not_blank",
        ),
        CheckConstraint(
            "btrim(name) <> ''",
            name="name_not_blank",
        ),
    )

    organization_id = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="机构 ID",
    )

    code = Column(
        String(64),
        nullable=True,
        unique=True,
        comment="机构编码",
    )

    name = Column(
        String(128),
        nullable=False,
        comment="机构名称",
    )

    sort_order = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="排序值",
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        comment="是否启用",
    )

    def __repr__(
            self,
    ) -> str:
        """返回机构字符串表示."""
        return (
            f"<Organization("
            f"organization_id='{self.organization_id}', "
            f"code='{self.code}', "
            f"name='{self.name}'"
            f")>"
        )
