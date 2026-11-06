"""部门表.

记录机构内的部门及其上级部门，支持任意层级的组织结构。

核心功能：
  - Department: 部门记录

使用示例：
  from datamind.db.models.departments import Department

  department = Department(
      department_id="dpt_0123456789abcdef",
      organization_id="org_0123456789abcdef",
      parent_id=None,
      code="HR",
      name="人力资源部",
  )
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Integer,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    true,
    UniqueConstraint,
    text,
)

from datamind.db.core import (
    Base,
    IdMixin,
    TimestampMixin,
)


class Department(
    IdMixin,
    TimestampMixin,
    Base,
):
    """部门表."""

    __tablename__ = "departments"

    __table_args__ = (
        Index(
            "uk_departments_root_name",
            "organization_id",
            "name",
            unique=True,
            postgresql_where=text(
                "parent_id IS NULL"
            ),
        ),
        Index(
            "uk_departments_sibling_name",
            "organization_id",
            "parent_id",
            "name",
            unique=True,
            postgresql_where=text(
                "parent_id IS NOT NULL"
            ),
        ),
        UniqueConstraint(
            "organization_id",
            "code",
            name="uq_departments_org_code",
        ),
        UniqueConstraint(
            "organization_id",
            "department_id",
            name="uq_departments_org_id",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "parent_id",
            ],
            [
                "departments.organization_id",
                "departments.department_id",
            ],
            name="fk_departments_parent_organization",
        ),
        CheckConstraint(
            "parent_id IS NULL OR parent_id <> department_id",
            name="parent_not_self",
        ),
        CheckConstraint(
            "code IS NULL OR btrim(code) <> ''",
            name="code_not_blank",
        ),
        CheckConstraint(
            "btrim(name) <> ''",
            name="name_not_blank",
        ),
    )

    department_id = Column(
        String(64),
        nullable=False,
        unique=True,
        comment="部门 ID",
    )

    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id"
        ),
        nullable=False,
        index=True,
        comment="所属机构 ID",
    )

    parent_id = Column(
        String(64),
        nullable=True,
        index=True,
        comment="上级部门 ID",
    )

    code = Column(
        String(64),
        nullable=True,
        comment="部门编码",
    )

    name = Column(
        String(128),
        nullable=False,
        comment="部门名称",
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
        """返回部门字符串表示."""
        return (
            f"<Department("
            f"department_id='{self.department_id}', "
            f"organization_id='{self.organization_id}', "
            f"code='{self.code}', "
            f"name='{self.name}'"
            f")>"
        )
