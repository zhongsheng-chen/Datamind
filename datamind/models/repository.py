# datamind/models/repository.py

"""模型查询仓储

提供模型领域对象的查询能力，用于运行时解析模型版本与加载信息。

核心功能：
  - ModelRepository: 模型查询仓储

使用示例：
  from datamind.models.repository import ModelRepository

  repo = ModelRepository(session)
  version = repo.get_version("mdl_001", "1.0.0")
  bento_tag = repo.get_bento_tag("mdl_001", "1.0.0")
"""

from typing import Optional
from sqlalchemy.orm import Session

from datamind.db.models.versions import Version


class ModelRepository:
    """模型查询仓储"""

    def __init__(self, session: Session):
        """初始化查询仓储

        参数：
            session: 数据库会话
        """
        self.session = session

    def get_version(
        self,
        model_id: str,
        version: str,
    ) -> Optional[Version]:
        """获取模型版本记录

        参数：
            model_id: 模型ID
            version: 版本号

        返回：
            Version 对象，不存在时返回 None
        """
        return (
            self.session.query(Version)
            .filter(
                Version.model_id == model_id,
                Version.version == version,
            )
            .one_or_none()
        )

    def get_bento_tag(
        self,
        model_id: str,
        version: str,
    ) -> Optional[str]:
        """获取 BentoML 标签

        参数：
            model_id: 模型ID
            version: 版本号

        返回：
            BentoML 标签，不存在时返回 None
        """
        record = self.get_version(model_id, version)
        return record.bento_tag if record else None