# datamind/db/models/assignments.py

"""实验分配表

记录实验主体与实验分组之间的固定分配关系，
用于保证同一个主体在同一个实验中稳定命中同一个分组。
"""

from sqlalchemy import Column, String, Float, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """实验分配表"""

    __tablename__ = "assignments"

    __table_args__ = (
        Index(
            "idx_assignments_experiment_id",
            "experiment_id"
        ),
        Index(
            "idx_assignments_variant_id",
            "variant_id"
        ),
        Index(
            "idx_assignments_subject_key",
            "subject_key"
        ),
        Index(
            "idx_assignments_created_at",
            "created_at"
        ),
        Index(
            "idx_assignments_assigned_at",
            "assigned_at"
        ),
        Index(
            "uk_assignments_assignment_id",
            "assignment_id",
            unique=True
        ),
        Index(
            "uk_assignments_experiment_subject",
            "experiment_id",
            "subject_key",
            unique=True),
    )

    assignment_id = Column(
        String(64),
        nullable=False,
        comment="分配 ID，实验分配记录的唯一标识"
    )
    experiment_id = Column(
        String(64),
        nullable=False,
        comment="实验 ID"
    )
    variant_id = Column(
        String(64),
        nullable=False,
        comment="实验分组 ID"
    )
    subject_key = Column(
        String(128),
        nullable=False,
        comment="分桶主体标识，例如客户号、订单号、申请单号"
    )
    subject_type = Column(
        String(32),
        nullable=True,
        comment="分桶主体类型，例如 customer / order / application"
    )
    strategy = Column(
        String(20),
        nullable=False,
        comment="分配策略，可选值：hash / manual"
    )
    bucket = Column(
        String(32),
        nullable=True,
        comment="分桶标识"
    )
    weight = Column(
        Float,
        nullable=True,
        comment="命中分组的权重"
    )
    context = Column(
        JSONB,
        nullable=True,
        comment="分配上下文，JSON 格式。包含实验曝光比例、分组名称、分桶过程等信息"
    )
    assigned_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="分配时间，表示主体首次固定进入实验分组的时间"
    )

    def __repr__(self):
        return (
            f"<Assignment("
            f"assignment_id='{self.assignment_id}', "
            f"experiment_id='{self.experiment_id}', "
            f"variant_id='{self.variant_id}', "
            f"subject_key='{self.subject_key}'"
            f")>"
        )
