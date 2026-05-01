# datamind/models/loader.py

"""模型加载器（Model Loader - Runtime Layer）

职责说明：
  ModelLoader 是在线推理链路中的“执行入口”，负责：
    1. 根据 model_id + version 定位模型元信息
    2. 从 Repository 获取 BentoML 绑定信息（bento_tag）
    3. 调用 BentoBackend 加载模型实例

设计原则：
  - 仅负责“加载”，不参与任何决策逻辑（routing / experiment / fallback）
  - 不写数据库（Read-only）
  - 不管理事务（不使用 UnitOfWork）
  - 不关心模型来源（只依赖 repository 提供的元数据）

数据流：
  model_id + version
        ↓
    ModelRepository (DB read)
        ↓
    bento_tag
        ↓
    BentoBackend.load()
        ↓
    model instance

适用场景：
  - 在线推理服务
  - 模型热加载
  - API inference gateway
"""

from dataclasses import dataclass

from datamind.logging import get_logger
from datamind.models.backend import BentoBackend
from datamind.models.repository import ModelRepository
from datamind.db.core.session import get_session

logger = get_logger(__name__)


@dataclass
class ModelLoader:
    """模型加载器（运行时组件）"""

    backend: BentoBackend = BentoBackend()

    # =========================
    # public API
    # =========================

    def load(self, *, model_id: str, version: str):
        """加载模型实例

        参数：
            model_id: 模型ID
            version: 模型版本号

        返回：
            BentoML 加载的模型实例
        """

        session = get_session()
        repo = ModelRepository(session)

        try:
            # 1. 查询模型版本元数据
            record = repo.get_version(model_id, version)

            if not record:
                raise ValueError(
                    f"模型版本不存在: {model_id}:{version}"
                )

            bento_tag = record.bento_tag

            logger.info(
                "开始加载模型",
                model_id=model_id,
                version=version,
                bento_tag=bento_tag,
            )

            # 2. 加载 BentoML 模型
            model = self.backend.load(bento_tag)

            logger.info(
                "模型加载成功",
                model_id=model_id,
                version=version,
            )

            return model

        finally:
            # 释放 session（避免连接泄漏）
            session.close()

    # =========================
    # convenience API
    # =========================

    def load_by_tag(self, bento_tag: str):
        """直接通过 Bento tag 加载模型（绕过 DB）"""

        logger.info(
            "通过 bento_tag 加载模型",
            bento_tag=bento_tag,
        )

        return self.backend.load(bento_tag)