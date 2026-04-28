# datamind/db/models/versions.py

"""模型版本模型

存储模型版本信息，每次模型注册生成一条记录。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表

    属性：
        model_id: 所属模型ID
        version: 版本号
        framework: 框架
        bento_tag: BentoML 标签（格式：模型名:版本）
        model_path: 模型文件存储路径
        params: 模型参数
        metrics: 模型评估指标
        description: 版本说明
        created_by: 创建人
    """

    __tablename__ = "versions"

    __table_args__ = (
        Index("idx_versions_model_id", "model_id"),
        Index("idx_versions_framework", "framework"),
        Index("idx_versions_bento_tag", "bento_tag"),
        Index("idx_versions_created_at", "created_at"),
        Index("uk_versions_model_id_version", "model_id", "version", unique=True),
    )

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    bento_tag = Column(String(100), nullable=False)

    model_path = Column(String(255), nullable=False)

    params = Column(JSONB)
    metrics = Column(JSONB)

    description = Column(Text)
    created_by = Column(String(50))

    def __repr__(self):
        return f"<Version(model_id='{self.model_id}', version='{self.version}')>"