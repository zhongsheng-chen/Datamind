import asyncio

from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories.metadata import MetadataRepository, MetadataPatch
from datamind.db.repositories.version import VersionRepository, VersionPatch

# import logging
# logging.basicConfig()
# logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

async def runner():
    async with UnitOfWork() as uow:
        repo = MetadataRepository(uow.session)

        # 查询
        model = await repo.get_model(model_id="mdl_a1b2c3d4")
        models = await repo.list_models(status="active", limit=10)

        # 创建
        model = repo.create_model(
            model_id="mdl_a1b2c3d4",
            name="scorecard",
            model_type="logistic_regression",
            task_type="scoring",
            framework="sklearn"
        )

        # 更新
        patch = MetadataPatch(name="scorecard_v2", description="新版本")
        model = repo.update_model(model, patch)

        # 归档
        model = repo.archive_model(model, updated_by="zc")

    async with UnitOfWork() as uow:
        repo = VersionRepository(uow.session)

        # 创建版本
        version = repo.create_version(
            version_id="ver_test",
            model_id="mdl_test",
            version="1.0.0",
            framework="sklearn",
            status="active",
            bento_tag="test:latest",
            model_path="/models/test",
            storage_key="test",
        )
        await uow.session.flush()

        old_updated_at = version.updated_at
        print(f"创建时 updated_at: {old_updated_at}")


        # 更新版本
        patch = VersionPatch(description="新描述")
        version = repo.update_version(version, patch, updated_by="user")

        new_updated_at = version.updated_at
        print(f"更新后 updated_at: {new_updated_at}")

        assert new_updated_at > old_updated_at
        print(f"updated_at 已自动从 {old_updated_at} 更新为 {version.updated_at}")


if __name__ == "__main__":
    asyncio.run(runner())