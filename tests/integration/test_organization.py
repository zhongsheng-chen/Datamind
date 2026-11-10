"""组织管理数据库集成测试.

使用隔离的 PostgreSQL Schema，验证组织资料、用户归属和并发部门变更。

核心功能：
  - test_user_creation_audit_matches_persisted_timestamps:
    验证创建和恢复用户的审计时间与数据库一致
  - test_user_organization_profile_lifecycle:
    验证资料创建、部分修改和清空
  - test_concurrent_department_moves_cannot_create_cycle:
    验证并发移动不能形成循环
  - test_audit_preserves_actor_organization:
    验证审计身份不会随用户调岗变化
  - test_database_rejects_cross_organization_department:
    验证数据库拒绝跨机构关联
  - test_optional_codes_and_sibling_name_constraints:
    验证业务编码可选，根部门和同级部门不能重名，不同分支可以同名
  - test_delete_empty_directory_and_preserve_audit:
    验证删除空部门和机构后保留删除前路径及历史审计快照
  - test_delete_rejects_assigned_inactive_user:
    验证停用用户仍阻止删除其所属部门和机构，清空归属后允许删除
  - test_delete_missing_directory_record:
    验证重复删除或删除不存在的组织记录时返回明确错误
  - test_concurrent_delete_and_child_creation:
    验证并发删除父部门和创建子部门时仅允许一项操作成功
  - test_delete_reports_reference_counts:
    验证删除冲突准确统计直属用户和子部门，包括停用用户
  - test_disabled_organization_preserves_users_and_blocks_new_links:
    验证停用机构允许维护已有人员资料，阻止新增关联，重新启用后恢复使用
  - test_disabled_parent_applies_to_descendants_and_allows_transfer:
    验证停用上级后阻止新增关联但允许用户调出，重新启用时保留下级停用状态
  - test_migrations_match_current_models:
    验证迁移链匹配当前模型、默认启用组织并支持完整回退
  - test_assignment_refreshes_preloaded_organization_status:
    验证组织资料预加载后发生停用时，关联校验读取锁定后的最新状态
  - test_employee_number_rejects_duplicate_assignment:
    验证创建和修改时工号全局唯一，停用和已删除用户的工号仍受保护
  - test_employee_number_can_be_kept_cleared_and_reassigned:
    验证保留、清空和重新分配工号时保留前导零
  - test_employee_number_is_optional:
    验证多个用户可不填写工号
  - test_database_rejects_duplicate_and_blank_employee_numbers:
    验证数据库拒绝重复和空白工号
  - test_concurrent_employee_number_assignment_returns_conflict:
    验证并发重复工号返回业务冲突且事务完整回滚
  - test_restored_user_can_keep_its_employee_number:
    验证恢复用户时可保留原工号
  - test_directory_order_is_persistent_and_scoped:
    验证持久化排序、同级边界与新增末尾行为
  - test_concurrent_directory_reordering_keeps_unique_positions:
    验证并发新增与排序保持唯一顺序
"""

import asyncio
from datetime import (
    datetime,
    timezone,
)

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from datamind.audit.actor import current_actor
from datamind.audit.recorder import AuditRecorder
from datamind.db.core import UnitOfWork
from datamind.db.models.audit import Audit
from datamind.db.models.users import User
from datamind.db.repositories.organization import OrganizationRepository
from datamind.db.repositories.user import UserRepository
from datamind.services.errors import IdentityConflictError
from datamind.services.identity import IdentityService
from datamind.services.organization import OrganizationService
from datamind.utils.datetime import format_iso_utc


pytestmark = pytest.mark.integration


async def create_directory() -> tuple[dict, dict, dict]:
    """创建两个机构和其中一个机构的部门."""
    service = OrganizationService()
    first = await service.save_organization(
        code="HQ",
        name="总行",
    )
    second = await service.save_organization(
        code="BRANCH",
        name="分行",
    )
    department = await service.save_department(
        organization_id=first["organization_id"],
        code="HR",
        name="人力资源部",
    )
    return (
        first,
        second,
        department,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("restore_existing", [False, True])
async def test_user_creation_audit_matches_persisted_timestamps(
        datamind_database,
        restore_existing: bool,
) -> None:
    """测试创建和恢复用户时审计快照保留数据库生成的时间."""
    service = IdentityService()
    arguments = {
        "username": "audit-user",
        "password": "secret-password",
        "operator_id": "system",
        "operator": "system",
    }
    if restore_existing:
        await service.create_user(**arguments)
        await service.delete_user(
            username="audit-user",
            operator_id="system",
            operator="system",
        )

    created = await service.create_user(**arguments)
    action = "user.restore" if restore_existing else "user.create"

    async with UnitOfWork() as uow:
        result = await uow.session.execute(
            select(User).where(User.user_id == created["user_id"])
        )
        user = result.scalar_one()
        result = await uow.session.execute(
            select(Audit).where(
                Audit.target_id == created["user_id"],
                Audit.action == action,
            )
        )
        audit = result.scalar_one()

        assert user is not None
        for field in ("created_at", "updated_at"):
            expected = format_iso_utc(getattr(user, field))
            assert expected is not None
            assert created[field] == expected
            assert audit.after[field] == expected


@pytest.mark.asyncio
async def test_user_organization_profile_lifecycle(
        datamind_database,
) -> None:
    """测试创建用户、字段保留、跨机构拒绝和显式清空."""
    first, second, department = await create_directory()
    service = IdentityService()

    created = await service.create_user(
        username="alice",
        password="secret-password",
        display_name="张三",
        employee_number=" 001234 ",
        organization_id=first["organization_id"],
        department_id=department["department_id"],
        operator_id="system",
        operator="system",
    )

    assert created["employee_number"] == "001234"
    assert created["organization_name"] == "总行"
    assert created["department_name"] == "人力资源部"
    assert department["department_id"].startswith("dpt_")

    await service.update_user(
        username="alice",
        new_username="alice",
        display_name="张三",
        email="alice@example.com",
        operator_id="system",
        operator="system",
    )
    retained = await service.get_user(username="alice")

    assert retained["department_id"] == department["department_id"]

    with pytest.raises(
        ValueError,
        match="不属于所属机构",
    ):
        await service.update_user(
            username="alice",
            new_username="alice",
            display_name="张三",
            organization_profile={"organization_id": second["organization_id"]},
            operator_id="system",
            operator="system",
        )

    cleared = await service.update_user(
        username="alice",
        new_username="alice",
        display_name="张三",
        organization_profile={
            "organization_id": None,
            "department_id": None,
        },
        operator_id="system",
        operator="system",
    )

    assert cleared["employee_number"] == "001234"
    assert cleared["organization_id"] is None
    assert cleared["department_path"] == []
    assert cleared["organization_name"] is None


@pytest.mark.asyncio
async def test_concurrent_department_moves_cannot_create_cycle(
        datamind_database,
) -> None:
    """测试两个同级部门交叉移动时，行锁保证组织结构不会形成循环."""
    organization, _, first = await create_directory()
    service = OrganizationService()

    second = await service.save_department(
        organization_id=organization["organization_id"],
        code="FINANCE",
        name="财务部",
    )
    results = await asyncio.gather(
        service.save_department(
            organization_id=organization["organization_id"],
            department_id=first["department_id"],
            parent_id=second["department_id"],
            code=first["code"],
            name=first["name"],
        ),
        service.save_department(
            organization_id=organization["organization_id"],
            department_id=second["department_id"],
            parent_id=first["department_id"],
            code=second["code"],
            name=second["name"],
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, ValueError) for result in results) == 1

    directory = await service.catalog()

    assert sorted(len(item["path"]) for item in directory["departments"]) == [
        1,
        2,
    ]


@pytest.mark.asyncio
async def test_audit_preserves_actor_organization(
        datamind_database,
) -> None:
    """测试审计保留操作时的工号、用户 ID 和部门名称."""
    organization, _, department = await create_directory()

    user = await IdentityService().create_user(
        username="alice",
        password="secret-password",
        employee_number="001234",
        organization_id=organization["organization_id"],
        department_id=department["department_id"],
        operator_id="system",
        operator="system",
    )
    async with UnitOfWork() as uow:
        record = await UserRepository(uow.session).get_user(username="alice")

        assert record is not None

        catalog = await OrganizationRepository(uow.session).catalog()
        actor = catalog.profile(record)

    token = current_actor.set(actor)

    try:
        await AuditRecorder().record(
            action="model.register",
            target_type="model",
            target_id="mdl_test",
            context={
                "user": "alice",
                "source": "cli",
            },
        )
    finally:
        current_actor.reset(token)

    await OrganizationService().save_department(
        organization_id=organization["organization_id"],
        department_id=department["department_id"],
        code="HR",
        name="人力资源管理部",
    )
    async with UnitOfWork() as uow:
        audit = (
            await uow.session.execute(
                select(Audit).where(Audit.action == "model.register"),
            )
        ).scalar_one()
        snapshot = audit.context["actor"]

    assert snapshot["user_id"] == user["user_id"]
    assert snapshot["employee_number"] == "001234"
    assert snapshot["department_path"][0]["name"] == "人力资源部"


@pytest.mark.asyncio
async def test_database_rejects_cross_organization_department(
        datamind_database,
) -> None:
    """测试绕过服务直接写入时，数据库也会拒绝跨机构的用户部门."""
    _, second, department = await create_directory()

    with pytest.raises(IntegrityError):
        async with UnitOfWork() as uow:
            uow.session.add(
                User(
                    user_id="usr_invalid",
                    username="invalid",
                    password_hash="test-only-hash",
                    organization_id=second["organization_id"],
                    department_id=department["department_id"],
                )
            )
            await uow.session.flush()


@pytest.mark.asyncio
async def test_optional_codes_and_sibling_name_constraints(
        datamind_database,
) -> None:
    """测试业务编码可选，根部门和同级部门不能重名，不同分支可以同名."""
    from datamind.services.errors import IdentityConflictError

    service = OrganizationService()

    organization = await service.save_organization(name="总行")

    assert organization["code"] is None

    first = await service.save_department(
        organization_id=organization["organization_id"],
        name="个人金融部",
    )
    second = await service.save_department(
        organization_id=organization["organization_id"],
        name="公司金融部",
    )

    assert first["code"] is None

    with pytest.raises(IdentityConflictError):
        await service.save_department(
            organization_id=organization["organization_id"],
            name="个人金融部",
        )

    child = await service.save_department(
        organization_id=organization["organization_id"],
        parent_id=first["department_id"],
        name="运营组",
        code="OPERATIONS",
    )

    with pytest.raises(IdentityConflictError):
        await service.save_department(
            organization_id=organization["organization_id"],
            parent_id=first["department_id"],
            name="运营组",
        )

    other = await service.save_department(
        organization_id=organization["organization_id"],
        parent_id=second["department_id"],
        name="运营组",
    )

    assert other["department_id"] != child["department_id"]

    renamed = await service.save_department(
        organization_id=organization["organization_id"],
        department_id=child["department_id"],
        parent_id=first["department_id"],
        name="业务运营组",
    )

    assert renamed["code"] == "OPERATIONS"

    cleared = await service.save_department(
        organization_id=organization["organization_id"],
        department_id=child["department_id"],
        parent_id=first["department_id"],
        name="业务运营组",
        code=None,
    )

    assert cleared["code"] is None


@pytest.mark.asyncio
async def test_delete_empty_directory_and_preserve_audit(datamind_database):
    """测试删除空部门和机构后保留删除前路径及历史审计快照."""
    service = OrganizationService()
    organization, empty, parent = await create_directory()

    child = await service.save_department(
        organization_id=organization["organization_id"],
        parent_id=parent["department_id"],
        name="招聘组",
    )
    from datamind.services.errors import IdentityConflictError

    with pytest.raises(IdentityConflictError, match="下级部门"):
        await service.delete_department(department_id=parent["department_id"])
    with pytest.raises(IdentityConflictError, match="0 名用户、2 个部门"):
        await service.delete_organization(
            organization_id=organization["organization_id"],
        )

    deleted = await service.delete_department(department_id=child["department_id"])

    assert [node["name"] for node in deleted["path"]] == ["人力资源部", "招聘组"]

    await service.delete_department(department_id=parent["department_id"])
    await service.delete_organization(organization_id=organization["organization_id"])
    await service.delete_organization(organization_id=empty["organization_id"])

    assert await service.catalog() == {"organizations": [], "departments": []}
    async with UnitOfWork() as uow:
        records = (
            (
                await uow.session.execute(
                    select(Audit).where(Audit.action == "department.delete"),
                )
            )
            .scalars()
            .all()
        )
        assert len(records) == 2
        snapshot = next(
            record for record in records if record.target_id == child["department_id"]
        )
        assert snapshot.before["path"][-1]["name"] == "招聘组"
        assert snapshot.after is None
        created = (
            await uow.session.execute(
                select(Audit).where(
                    Audit.action == "department.create",
                    Audit.target_id == child["department_id"],
                )
            )
        ).scalar_one()
        assert created.after["path"][-1]["name"] == "招聘组"


@pytest.mark.asyncio
async def test_delete_rejects_assigned_inactive_user(datamind_database):
    """测试停用用户仍阻止删除其所属部门和机构，清空归属后允许删除."""
    from datamind.auth.enums import UserStatus
    from datamind.services.errors import IdentityConflictError

    organization, _, department = await create_directory()
    async with UnitOfWork() as uow:
        uow.session.add(
            User(
                user_id="usr_assigned",
                username="assigned",
                password_hash="test-only-hash",
                status=UserStatus.DISABLED,
                organization_id=organization["organization_id"],
                department_id=department["department_id"],
            )
        )
    service = OrganizationService()

    with pytest.raises(IdentityConflictError, match="用户"):
        await service.delete_department(department_id=department["department_id"])
    async with UnitOfWork() as uow:
        user = await UserRepository(uow.session).get_user(username="assigned")
        user.department_id = None

    await service.delete_department(department_id=department["department_id"])

    with pytest.raises(IdentityConflictError, match="用户"):
        await service.delete_organization(
            organization_id=organization["organization_id"],
        )
    async with UnitOfWork() as uow:
        user = await UserRepository(uow.session).get_user(username="assigned")
        user.organization_id = None

    await service.delete_organization(organization_id=organization["organization_id"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, key",
    [
        ("delete_organization", "organization_id"),
        ("delete_department", "department_id"),
    ],
)
async def test_delete_missing_directory_record(datamind_database, method, key):
    """测试重复删除或删除不存在的组织记录时返回明确错误."""
    with pytest.raises(ValueError, match="不存在"):
        await getattr(OrganizationService(), method)(**{key: "missing"})


@pytest.mark.asyncio
async def test_concurrent_delete_and_child_creation(datamind_database):
    """测试并发删除父部门和创建子部门时仅允许一项操作成功."""
    from datamind.services.errors import IdentityConflictError

    organization, _, parent = await create_directory()
    service = OrganizationService()
    results = await asyncio.gather(
        service.delete_department(department_id=parent["department_id"]),
        service.save_department(
            organization_id=organization["organization_id"],
            parent_id=parent["department_id"],
            name="招聘组",
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert (
        sum(
            isinstance(result, (ValueError, IdentityConflictError))
            for result in results
        )
        == 1
    )

    directory = await service.catalog()
    ids = {item["department_id"] for item in directory["departments"]}
    assert all(
        item["parent_id"] is None or item["parent_id"] in ids
        for item in directory["departments"]
    )


@pytest.mark.asyncio
async def test_delete_reports_reference_counts(datamind_database):
    """测试删除冲突准确统计直属用户和子部门，包括停用用户."""
    from datamind.auth.enums import UserStatus
    from datamind.services.errors import IdentityConflictError

    organization, _, parent = await create_directory()
    service = OrganizationService()
    for name in ("招聘组", "薪酬组"):
        await service.save_department(
            organization_id=organization["organization_id"],
            parent_id=parent["department_id"],
            name=name,
        )
    async with UnitOfWork() as uow:
        for index in range(3):
            uow.session.add(
                User(
                    user_id=f"usr_count_{index}",
                    username=f"count-{index}",
                    password_hash="test-only",
                    status=UserStatus.DISABLED,
                    organization_id=organization["organization_id"],
                    department_id=parent["department_id"],
                )
            )
    with pytest.raises(IdentityConflictError, match="3 名用户、2 个直属下级部门"):
        await service.delete_department(department_id=parent["department_id"])
    with pytest.raises(IdentityConflictError, match="3 名用户、3 个部门"):
        await service.delete_organization(
            organization_id=organization["organization_id"],
        )


@pytest.mark.asyncio
async def test_disabled_organization_preserves_users_and_blocks_new_links(
        datamind_database,
):
    """测试停用机构允许维护已有人员资料，阻止新增关联，重新启用后恢复使用."""
    organization, _, department = await create_directory()
    service = OrganizationService()
    identity = IdentityService()

    await identity.create_user(
        username="existing",
        password="secret-password",
        organization_id=organization["organization_id"],
        department_id=department["department_id"],
        operator_id="system",
        operator="system",
    )
    await service.set_organization_active(
        organization_id=organization["organization_id"],
        is_active=False,
    )
    updated = await identity.update_user(
        username="existing",
        new_username="existing",
        display_name="更新姓名",
        organization_profile={
            "employee_number": "00123",
            "organization_id": organization["organization_id"],
            "department_id": department["department_id"],
        },
        operator_id="system",
        operator="system",
    )

    assert updated["department_id"] == department["department_id"]
    assert updated["employee_number"] == "00123"
    assert updated["department_path"][0]["name"] == "人力资源部"
    with pytest.raises(ValueError, match="机构已停用"):
        await identity.create_user(
            username="new",
            password="secret-password",
            organization_id=organization["organization_id"],
            operator_id="system",
            operator="system",
        )
    with pytest.raises(ValueError, match="机构已停用"):
        await service.save_department(
            organization_id=organization["organization_id"],
            name="新增部门",
        )

    directory = await service.catalog()

    assert (
        next(
            item
            for item in directory["departments"]
            if item["department_id"] == department["department_id"]
        )["is_available"]
        is False
    )

    await service.set_organization_active(
        organization_id=organization["organization_id"],
        is_active=True,
    )
    await identity.create_user(
        username="new",
        password="secret-password",
        organization_id=organization["organization_id"],
        operator_id="system",
        operator="system",
    )
    async with UnitOfWork() as uow:
        audit = (
            await uow.session.execute(
                select(Audit).where(Audit.action == "organization.disable"),
            )
        ).scalar_one()
        assert audit.before["is_active"] is True
        assert audit.after["is_active"] is False
        created = (
            await uow.session.execute(
                select(Audit).where(
                    Audit.action == "user.create",
                    Audit.target_id == updated["user_id"],
                )
            )
        ).scalar_one()
        assert created.after["department_id"] == department["department_id"]


@pytest.mark.asyncio
async def test_disabled_parent_applies_to_descendants_and_allows_transfer(
        datamind_database,
):
    """测试停用上级后阻止新增关联但允许用户调出，重新启用时保留下级停用状态."""
    organization, _, parent = await create_directory()
    service = OrganizationService()

    child = await service.save_department(
        organization_id=organization["organization_id"],
        parent_id=parent["department_id"],
        name="招聘组",
    )
    identity = IdentityService()

    await identity.create_user(
        username="existing",
        password="secret-password",
        organization_id=organization["organization_id"],
        department_id=child["department_id"],
        operator_id="system",
        operator="system",
    )
    await service.set_department_active(
        department_id=parent["department_id"],
        is_active=False,
    )

    with pytest.raises(ValueError, match="已停用"):
        await identity.create_user(
            username="new",
            password="secret-password",
            organization_id=organization["organization_id"],
            department_id=child["department_id"],
            operator_id="system",
            operator="system",
        )
    with pytest.raises(ValueError, match="上级部门.*已停用"):
        await service.save_department(
            organization_id=organization["organization_id"],
            parent_id=child["department_id"],
            name="校园招聘小组",
        )

    updated = await identity.update_user(
        username="existing",
        new_username="existing",
        display_name="调出人员",
        organization_profile={"department_id": None},
        operator_id="system",
        operator="system",
    )

    assert updated["department_id"] is None

    await service.set_department_active(
        department_id=child["department_id"],
        is_active=False,
    )
    await service.set_department_active(
        department_id=parent["department_id"],
        is_active=True,
    )
    directory = await service.catalog()
    departments = {item["department_id"]: item for item in directory["departments"]}
    assert departments[parent["department_id"]]["is_available"] is True
    assert departments[child["department_id"]]["is_active"] is False
    assert departments[child["department_id"]]["is_available"] is False

    await service.delete_department(department_id=child["department_id"])


@pytest.mark.asyncio
async def test_migrations_match_current_models(datamind_database):
    """测试迁移链匹配当前模型、默认启用组织并支持完整回退."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect

    from datamind.db.core import Base
    from datamind.db.migration import _migration_config

    scripts = ScriptDirectory.from_config(_migration_config())
    head = scripts.get_current_head()
    assert head is not None

    migrations = [revision.module for revision in reversed(list(scripts.walk_revisions()))]

    def rebuild(sync_connection: Connection) -> None:
        Base.metadata.drop_all(sync_connection)

        context = MigrationContext.configure(
            sync_connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
            },
        )

        with Operations.context(context):
            for migration in migrations:
                migration.upgrade()

        assert compare_metadata(context, Base.metadata) == []

    async with datamind_database.begin() as connection:
        await connection.run_sync(rebuild)

    organization, _, department = await create_directory()

    assert organization["is_active"] is True
    assert department["is_active"] is True
    assert department["is_available"] is True

    def rollback(sync_connection: Connection) -> None:
        with Operations.context(MigrationContext.configure(sync_connection)):
            for migration in reversed(migrations):
                migration.downgrade()

        inspector = inspect(sync_connection)
        assert inspector is not None
        assert inspector.get_table_names() == []

    async with datamind_database.begin() as connection:
        await connection.run_sync(rollback)


@pytest.mark.asyncio
async def test_assignment_refreshes_preloaded_organization_status(datamind_database):
    """测试组织资料预加载后发生停用时，关联校验读取锁定后的最新状态."""
    organization, _, department = await create_directory()
    async with UnitOfWork() as uow:
        directory = await OrganizationRepository(uow.session).catalog()
        assert (
            directory.organizations[organization["organization_id"]].is_active is True
        )
        await OrganizationService().set_organization_active(
            organization_id=organization["organization_id"],
            is_active=False,
        )
        with pytest.raises(ValueError, match="机构已停用"):
            await OrganizationService.validate_profile(
                uow.session,
                {
                    "organization_id": organization["organization_id"],
                    "department_id": department["department_id"],
                },
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
@pytest.mark.parametrize("owner_state", ["active", "disabled", "deleted"])
async def test_employee_number_rejects_duplicate_assignment(
        datamind_database,
        operation: str,
        owner_state: str,
) -> None:
    """测试工号全局唯一，停用或已删除用户的工号仍受保护."""
    first, second, _ = await create_directory()
    service = IdentityService()

    owner = await service.create_user(
        username="alice",
        password="secret-password",
        employee_number="001234",
        organization_id=first["organization_id"],
        operator_id="system",
        operator="system",
    )

    if owner_state != "active":
        async with UnitOfWork() as uow:
            user = await UserRepository(uow.session).get_user(user_id=owner["user_id"])
            assert user is not None
            user.status = "disabled"

            if owner_state == "deleted":
                user.deleted_at = datetime.now(timezone.utc)

    if operation == "update":
        await service.create_user(
            username="bob",
            password="secret-password",
            organization_id=second["organization_id"],
            operator_id="system",
            operator="system",
        )

    with pytest.raises(IdentityConflictError, match="工号已被使用"):
        if operation == "create":
            await service.create_user(
                username="bob",
                password="secret-password",
                employee_number=" 001234 ",
                organization_id=second["organization_id"],
                operator_id="system",
                operator="system",
            )
        else:
            await service.update_user(
                username="bob",
                new_username="bob",
                organization_profile={"employee_number": " 001234 "},
                operator_id="system",
                operator="system",
            )


@pytest.mark.asyncio
async def test_employee_number_can_be_kept_cleared_and_reassigned(
        datamind_database,
) -> None:
    """测试原工号可保留，清空后可授予其他用户，且前导零保持不变."""
    service = IdentityService()

    await service.create_user(
        username="alice",
        password="secret-password",
        employee_number=" 001234 ",
        operator_id="system",
        operator="system",
    )
    await service.create_user(
        username="bob",
        password="secret-password",
        operator_id="system",
        operator="system",
    )
    retained = await service.update_user(
        username="alice",
        new_username="alice",
        organization_profile={"employee_number": "001234"},
        operator_id="system",
        operator="system",
    )

    assert retained["employee_number"] == "001234"

    omitted = await service.update_user(
        username="alice",
        new_username="alice",
        display_name="Alice",
        operator_id="system",
        operator="system",
    )

    assert omitted["employee_number"] == "001234"

    cleared = await service.update_user(
        username="alice",
        new_username="alice",
        organization_profile={"employee_number": ""},
        operator_id="system",
        operator="system",
    )
    reassigned = await service.update_user(
        username="bob",
        new_username="bob",
        organization_profile={"employee_number": "001234"},
        operator_id="system",
        operator="system",
    )

    assert cleared["employee_number"] is None
    assert reassigned["employee_number"] == "001234"


@pytest.mark.asyncio
async def test_employee_number_is_optional(
        datamind_database,
) -> None:
    """测试多个用户可不填写工号，空白工号按未填写处理."""
    service = IdentityService()

    for name, number in (("alice", None), ("bob", ""), ("carol", "   ")):
        user = await service.create_user(
            username=name,
            password="secret-password",
            employee_number=number,
            operator_id="system",
            operator="system",
        )
        assert user["employee_number"] is None


@pytest.mark.asyncio
async def test_database_rejects_duplicate_and_blank_employee_numbers(
        datamind_database,
) -> None:
    """测试直接写入数据库时也不能重复工号或保存空白工号."""
    async with UnitOfWork() as uow:
        repo = UserRepository(uow.session)
        repo.create_user(
            user_id="usr_alice",
            username="alice",
            password_hash="password-hash",
            employee_number="001234",
        )

    for name, number, constraint in (
        ("bob", "001234", "uk_users_employee_number"),
        ("carol", "   ", "employee_number_not_blank"),
    ):
        with pytest.raises(IntegrityError, match=constraint):
            async with UnitOfWork() as uow:
                UserRepository(uow.session).create_user(
                    user_id=f"usr_{name}",
                    username=name,
                    password_hash="password-hash",
                    employee_number=number,
                )


@pytest.mark.asyncio
async def test_concurrent_employee_number_assignment_returns_conflict(
        datamind_database,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试并发申请相同工号时仅一项成功，另一项返回明确的业务冲突."""
    ready = asyncio.Event()
    arrivals = 0

    class ConcurrentUserRepository(UserRepository):
        """同步并发工号查询的测试仓储."""

        async def get_user(
                self,
                **arguments: str | None,
        ) -> User | None:
            """执行真实查询，并等待两个工号查询均完成."""
            nonlocal arrivals
            user = await super().get_user(**arguments)

            if "employee_number" in arguments:
                arrivals += 1

                if arrivals == 2:
                    ready.set()

                await asyncio.wait_for(ready.wait(), timeout=10)

            return user

    monkeypatch.setattr(
        "datamind.services.identity.UserRepository",
        ConcurrentUserRepository,
    )
    service = IdentityService()
    results = await asyncio.gather(
        *(
            service.create_user(
                username=name,
                password="secret-password",
                employee_number="001234",
                operator_id="system",
                operator="system",
            )
            for name in ("alice", "bob")
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, dict) for result in results) == 1
    errors = [result for result in results if isinstance(result, BaseException)]
    assert len(errors) == 1
    assert isinstance(errors[0], IdentityConflictError)
    assert "工号已被使用" in str(errors[0])

    async with UnitOfWork() as uow:
        users = await UserRepository(uow.session).list_users()
        audits = list((await uow.session.execute(select(Audit))).scalars())

    assert len(users) == 1
    assert users[0].employee_number == "001234"
    assert len(audits) == 1


@pytest.mark.asyncio
async def test_restored_user_can_keep_its_employee_number(
        datamind_database,
) -> None:
    """测试恢复已删除用户时可保留原有工号."""
    service = IdentityService()

    first = await service.create_user(
        username="alice",
        password="secret-password",
        employee_number="001234",
        operator_id="system",
        operator="system",
    )
    await service.delete_user(
        username="alice",
        operator_id="system",
        operator="system",
    )
    restored = await service.create_user(
        username="alice",
        password="new-secret-password",
        employee_number="001234",
        operator_id="system",
        operator="system",
    )

    assert restored["user_id"] == first["user_id"]
    assert restored["employee_number"] == "001234"
    assert restored["action"] == "restore"


@pytest.mark.asyncio
async def test_directory_order_is_persistent_and_scoped(datamind_database) -> None:
    """测试排序持久化、同级范围、边界与新增末尾行为."""
    service = OrganizationService()
    first, second, parent = await create_directory()

    sibling = await service.save_department(organization_id=first["organization_id"], name="财务部")
    child = await service.save_department(
        organization_id=first["organization_id"], parent_id=parent["department_id"], name="招聘组",
    )
    await service.move(resource="organization", target_id=second["organization_id"], direction="up")
    await service.move(resource="department", target_id=sibling["department_id"], direction="up")
    directory = await service.catalog()

    assert [item["organization_id"] for item in directory["organizations"]] == [
        second["organization_id"], first["organization_id"],
    ]
    assert [item["department_id"] for item in directory["departments"]] == [
        sibling["department_id"], parent["department_id"], child["department_id"],
    ]
    with pytest.raises(ValueError, match="边界"):
        await service.move(resource="department", target_id=child["department_id"], direction="up")
    with pytest.raises(ValueError, match="边界"):
        await service.move(resource="organization", target_id=second["organization_id"], direction="up")

    await service.move(resource="department", target_id=sibling["department_id"], direction="down")
    added = await service.save_department(organization_id=first["organization_id"], name="信息科技部")
    directory = await service.catalog()

    assert [item["department_id"] for item in directory["departments"]] == [
        parent["department_id"], child["department_id"], sibling["department_id"], added["department_id"],
    ]
    async with UnitOfWork() as uow:
        audits = list((await uow.session.execute(select(Audit).where(Audit.action.like("%.reorder")))).scalars())
    assert len(audits) == 3
    assert all(item.before["sibling_ids"] != item.after["sibling_ids"] for item in audits)


@pytest.mark.asyncio
async def test_concurrent_directory_reordering_keeps_unique_positions(datamind_database) -> None:
    """测试并发排序与新增串行化，顺序不丢失、不重复."""
    service = OrganizationService()
    first, second, _ = await create_directory()
    results = await asyncio.gather(
        service.move(resource="organization", target_id=second["organization_id"], direction="up"),
        service.save_organization(name="第三机构"),
    )

    directory = await service.catalog()

    assert [item["organization_id"] for item in directory["organizations"]] == [
        second["organization_id"], first["organization_id"], results[1]["organization_id"],
    ]
    assert [item["sort_order"] for item in directory["organizations"]] == [1, 2, 3]
