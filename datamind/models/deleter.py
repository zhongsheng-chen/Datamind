# datamind/models/deleter.py

"""模型删除服务

支持：
  - 软删除（标记 deprecated / inactive）
  - 硬删除（force=True）
  - 删除指定版本 / 全版本
  - 清理 storage + bentoml + DB

核心规则：
  - 默认 soft delete（只改状态）
  - force=True 才做 hard delete
"""

import structlog

from datamind.db.core.uow import UnitOfWork
from datamind.db.readers import MetadataReader, VersionReader
from datamind.db.writers import MetadataWriter, VersionWriter
from datamind.storage import get_storage

logger = structlog.getLogger(__name__)


class ModelDeleter:
    """模型删除器"""

    def __init__(self):
        self.storage = get_storage()
        self.bento = get_bento()

    async def delete(
        self,
        *,
        model_id: str,
        version: str | None = None,
        force: bool = False,
    ) -> dict:
        """删除模型或版本"""

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_reader = MetadataReader(session)
            version_reader = VersionReader(session)

            metadata_writer = MetadataWriter(session)
            version_writer = VersionWriter(session)

            # =========================
            # 1. 查询模型
            # =========================
            metadata = await metadata_reader.get_model(model_id)
            if not metadata:
                raise ValueError(f"模型不存在: {model_id}")

            # =========================
            # 2. 删除指定版本
            # =========================
            if version:

                v = await version_reader.get_version(model_id, version)
                if not v:
                    raise ValueError(f"版本不存在: {model_id}:{version}")

                if force:
                    # -------------------------
                    # HARD DELETE
                    # -------------------------

                    # 1) 删除 storage 文件
                    try:
                        self.storage.delete(model_id, version, "scorecard.pkl")
                    except Exception as e:
                        logger.warning("storage 删除失败", error=str(e))

                    # 2) 删除 bentoml
                    try:
                        import bentoml

                        for m in bentoml.models.list():
                            if model_id in str(m.tag):
                                bentoml.models.delete(m.tag)
                    except Exception as e:
                        logger.warning("bento 删除失败", error=str(e))

                    # 3) 删除 DB version
                    await version_writer.delete(v)

                    logger.info(
                        "版本硬删除完成",
                        model_id=model_id,
                        version=version,
                    )

                else:
                    # -------------------------
                    # SOFT DELETE
                    # -------------------------
                    await version_writer.update(
                        v,
                        status="deprecated",
                    )

                    logger.info(
                        "版本软删除完成",
                        model_id=model_id,
                        version=version,
                    )

                return {
                    "model_id": model_id,
                    "version": version,
                    "deleted": True,
                    "mode": "hard" if force else "soft",
                }

            # =========================
            # 3. 删除整个模型
            # =========================
            versions = await version_reader.list_versions(model_id)

            if force:
                # -------------------------
                # HARD DELETE MODEL
                # -------------------------

                # 1) 删除所有版本 storage
                for v in versions:
                    try:
                        self.storage.delete(model_id, v.version, "model.pkl")
                    except Exception as e:
                        logger.warning("storage 删除失败", error=str(e))

                # 2) 删除 bentoml
                try:
                    import bentoml

                    for m in bentoml.models.list():
                        if model_id in str(m.tag):
                            bentoml.models.delete(m.tag)
                except Exception as e:
                    logger.warning("bento 删除失败", error=str(e))

                # 3) 删除 versions
                for v in versions:
                    await version_writer.delete(v)

                # 4) 删除 metadata
                await metadata_writer.delete(metadata)

                logger.info("模型硬删除完成", model_id=model_id)

            else:
                # -------------------------
                # SOFT DELETE MODEL
                # -------------------------
                await metadata_writer.update(
                    metadata,
                    status="deprecated",
                )

                for v in versions:
                    await version_writer.update(
                        v,
                        status="deprecated",
                    )

                logger.info("模型软删除完成", model_id=model_id)

            return {
                "model_id": model_id,
                "deleted": True,
                "mode": "hard" if force else "soft",
            }