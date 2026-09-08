"""模型制品仓储

提供模型制品修订的查询、创建、切换和清理状态管理能力。

核心功能：
  - get_artifact: 获取指定制品
  - get_current_artifact: 获取版本当前生效制品
  - list_artifacts: 获取版本制品修订列表
  - create_artifact: 创建制品修订
  - retire_artifact: 停止使用制品
  - request_purge: 请求永久清理制品
  - mark_purged: 标记制品已永久清理
  - mark_purge_failed: 标记制品清理失败

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.artifact import ArtifactRepository

  async with UnitOfWork() as uow:
      repo = ArtifactRepository(
          uow.session
      )

      artifact = repo.create_artifact(
          artifact_id="art_0123456789abcdef",
          version_id="ver_0123456789abcdef",
          revision=1,
          sha256="4f7c2a8d...c91e",
          digest="9b3e1f6a...72d4",
          source_path="models/scorecard.pkl",
          model_key=(
              "models/mdl_0123456789abcdef/1.0.0/"
              "artifacts/art_0123456789abcdef/scorecard.pkl"
          ),
          bento_tag="scorecard:abcdefgh",
          created_by="admin",
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.db.models.artifacts import Artifact
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import ArtifactStatus


class ArtifactRepository(BaseRepository):
    """模型制品仓储"""

    async def get_artifact(
            self,
            artifact_id: str,
            *,
            for_update: bool = False,
    ) -> Artifact | None:
        """获取模型制品"""
        stmt = select(
            Artifact
        ).where(
            Artifact.artifact_id
            == artifact_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_current_artifact(
            self,
            version_id: str,
            *,
            for_update: bool = False,
    ) -> Artifact | None:
        """获取版本当前生效制品"""
        stmt = select(
            Artifact
        ).where(
            Artifact.version_id
            == version_id,
            Artifact.status
            == str(ArtifactStatus.ACTIVE),
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_artifacts(
            self,
            *,
            version_id: str,
            include_purged: bool = True,
            for_update: bool = False,
    ) -> list[Artifact]:
        """获取版本全部制品修订"""
        stmt = select(
            Artifact
        ).where(
            Artifact.version_id
            == version_id
        )

        if not include_purged:
            stmt = stmt.where(
                Artifact.status
                != str(ArtifactStatus.PURGED)
            )

        stmt = stmt.order_by(
            Artifact.revision.asc()
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    def create_artifact(
            self,
            *,
            artifact_id: str,
            version_id: str,
            revision: int,
            sha256: str,
            digest: str,
            source_path: str,
            model_key: str,
            bento_tag: str,
            created_by: str | None = None,
    ) -> Artifact:
        """创建 active 模型制品修订"""
        artifact = Artifact(
            artifact_id=artifact_id,
            version_id=version_id,
            revision=revision,
            sha256=sha256,
            digest=digest,
            source_path=source_path,
            model_key=model_key,
            bento_tag=bento_tag,
            status=str(ArtifactStatus.ACTIVE),
            purge_attempts=0,
        )

        if created_by is not None:
            artifact.created_by = created_by

        self.add(
            artifact
        )

        return artifact

    @staticmethod
    def retire_artifact(
            artifact: Artifact,
            *,
            retired_by: str | None = None,
    ) -> Artifact:
        """停止使用模型制品"""
        artifact.status = str(
            ArtifactStatus.RETIRED
        )
        artifact.retired_at = datetime.now(
            timezone.utc
        )

        if retired_by is not None:
            artifact.retired_by = retired_by

        return artifact

    @staticmethod
    def request_purge(
            artifact: Artifact,
            *,
            reason: str | None = None,
            requested_by: str | None = None,
    ) -> Artifact:
        """请求永久清理模型制品"""
        if artifact.status == str(ArtifactStatus.PURGED):
            return artifact

        artifact.status = str(
            ArtifactStatus.PURGE_PENDING
        )
        artifact.purge_requested_at = datetime.now(
            timezone.utc
        )
        artifact.purge_reason = reason
        artifact.purge_error = None

        if requested_by is not None:
            artifact.purge_requested_by = requested_by

        return artifact

    @staticmethod
    def mark_purged(
            artifact: Artifact,
            *,
            purged_by: str | None = None,
    ) -> Artifact:
        """标记模型制品已永久清理"""
        artifact.status = str(
            ArtifactStatus.PURGED
        )
        artifact.purged_at = datetime.now(
            timezone.utc
        )
        artifact.purge_error = None
        artifact.purge_attempts = int(
            artifact.purge_attempts or 0
        ) + 1

        if purged_by is not None:
            artifact.purged_by = purged_by

        return artifact

    @staticmethod
    def mark_purge_failed(
            artifact: Artifact,
            *,
            error: str,
    ) -> Artifact:
        """标记模型制品清理失败"""
        artifact.status = str(
            ArtifactStatus.PURGE_FAILED
        )
        artifact.purge_error = error
        artifact.purge_attempts = int(
            artifact.purge_attempts or 0
        ) + 1

        return artifact
