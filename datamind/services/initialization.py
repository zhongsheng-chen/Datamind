"""系统初始化服务.

在单个事务中创建部署时指定的首个管理员、内置系统管理员角色、
角色授予和初始化审计记录。

核心功能：
  - initialize: 一次性初始化系统

使用示例：
  from datamind.services.initialization import InitializationService

  result = await InitializationService().initialize(
      username="admin",
      password="P@ssw1rd",
  )

  print(result.username)
"""

from dataclasses import dataclass
from datetime import (
    datetime,
    timezone,
)

import structlog

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.auth.password import hash_password
from datamind.constants.identity import (
    ADMINISTRATOR_DISPLAY_NAME,
    ADMINISTRATOR_PERMISSIONS,
    ADMINISTRATOR_ROLE_NAME,
    SYSTEM_BOOTSTRAP_ACTOR,
)
from datamind.context import generate_trace_id
from datamind.context.core import get_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AuditRepository,
    GrantRepository,
    RoleRepository,
    SystemStateRepository,
    UserRepository,
)
from datamind.services.errors import (
    AlreadyInitializedError,
    InitializationError,
)
from datamind.utils import generate_random_id


SYSTEM_ID = "datamind"
SYSTEM_ACTOR = SYSTEM_BOOTSTRAP_ACTOR
logger = structlog.get_logger(__name__)


@dataclass(
    slots=True,
    frozen=True,
)
class InitializationResult:
    """系统初始化结果."""

    system_id: str
    username: str
    user_id: str
    role_id: str
    initialized_at: datetime


class InitializationService:
    """系统初始化服务."""

    @staticmethod
    async def is_initialized(
    ) -> bool:
        """查询系统是否已经完成初始化."""
        async with UnitOfWork() as uow:
            state = await SystemStateRepository(
                uow.session
            ).get_state(
                system_id=SYSTEM_ID
            )

            return (
                state is not None
                and bool(
                    state.initialized
                )
            )

    async def initialize(
            self,
            *,
            username: str,
            password: str,
            ip: str | None = None,
            hostname: str | None = None,
            current_time: datetime | None = None,
    ) -> InitializationResult:
        """一次性初始化系统.

        创建首个管理员、拥有全部权限的 administrator 角色及角色授予，
        同时写入初始化状态和审计记录。所有变更由同一个工作单元提交。

        参数：
            username: 首个管理员用户名
            password: 首个管理员明文密码
            ip: 初始化主机 IP（可选）
            hostname: 初始化主机名称（可选）
            current_time: 初始化时间（可选）

        返回：
            系统初始化结果

        异常：
            InitializationError: 已存在用户或系统管理员角色
            AlreadyInitializedError: 系统已经完成初始化
            ValueError: 用户名、密码或时间不合法
        """
        normalized_username = self._validate_username(
            username
        )
        self._validate_password(
            password
        )
        initialized_at = self._normalize_time(
            current_time
        )
        context = get_context()
        request_id = context.get("request_id") or generate_random_id(
            prefix="req"
        )
        trace_id = context.get("trace_id") or generate_trace_id()

        async with UnitOfWork() as uow:
            state_repo = SystemStateRepository(
                uow.session
            )
            user_repo = UserRepository(
                uow.session
            )
            role_repo = RoleRepository(
                uow.session
            )
            grant_repo = GrantRepository(
                uow.session
            )
            audit_repo = AuditRepository(
                uow.session
            )

            state = await state_repo.get_or_create_state(
                system_id=SYSTEM_ID,
            )

            if bool(state.initialized):
                raise AlreadyInitializedError(
                    "Datamind 已经完成初始化"
                )

            if await user_repo.list_users(
                    limit=1
            ):
                raise InitializationError(
                    "检测到已有用户，拒绝初始化"
                )

            existing_role = await role_repo.get_role(
                name=ADMINISTRATOR_ROLE_NAME
            )

            if existing_role is not None:
                raise InitializationError(
                    "administrator 角色已经存在，拒绝初始化"
                )

            user_id = generate_random_id(
                prefix="usr"
            )
            role_id = generate_random_id(
                prefix="rol"
            )

            user = user_repo.create_user(
                user_id=user_id,
                username=normalized_username,
                password_hash=hash_password(
                    password
                ),
                display_name=ADMINISTRATOR_DISPLAY_NAME,
                created_by=SYSTEM_ACTOR,
            )
            user.password_changed_at = initialized_at

            role_repo.create_role(
                role_id=role_id,
                name=ADMINISTRATOR_ROLE_NAME,
                description="系统管理员角色",
                permissions=list(
                    ADMINISTRATOR_PERMISSIONS
                ),
                created_by=SYSTEM_ACTOR,
            )

            grant_repo.create_grant(
                grant_id=generate_random_id(
                    prefix="grt"
                ),
                user_id=user_id,
                role_id=role_id,
                granted_by=SYSTEM_ACTOR,
                granted_at=initialized_at,
            )

            state_repo.mark_initialized(
                state,
                initialized_at=initialized_at,
                initialized_by=SYSTEM_ACTOR,
            )

            audit_repo.create_audit(
                audit_id=generate_random_id(
                    prefix="aud"
                ),
                action="system.initialize",
                resource="system",
                operation="initialize",
                target_type="system",
                target_id=SYSTEM_ID,
                source=AuditSource.CLI,
                trace_id=trace_id,
                request_id=request_id,
                user=SYSTEM_ACTOR,
                ip=ip,
                hostname=hostname,
                status=AuditStatus.SUCCESS,
                after={
                    "initialized": True,
                    "admin_user_id": user_id,
                    "admin_username": normalized_username,
                    "admin_role_id": role_id,
                },
                occurred_at=initialized_at,
            )

        logger.info(
            "Datamind 初始化完成",
            action="system.initialize",
            target_type="system",
            target_id=SYSTEM_ID,
            source=AuditSource.CLI,
            user=SYSTEM_ACTOR,
            request_id=request_id,
            trace_id=trace_id,
            ip=ip,
            hostname=hostname,
            status="success",
        )

        return InitializationResult(
            system_id=SYSTEM_ID,
            username=normalized_username,
            user_id=user_id,
            role_id=role_id,
            initialized_at=initialized_at,
        )

    @staticmethod
    def _validate_username(
            username: str,
    ) -> str:
        """校验管理员用户名."""
        normalized = username.strip()

        if normalized == "":
            raise ValueError(
                "管理员用户名不能为空"
            )

        if len(normalized) > 64:
            raise ValueError(
                "管理员用户名长度不能超过 64"
            )

        return normalized

    @staticmethod
    def _validate_password(
            password: str,
    ) -> None:
        """校验管理员密码."""
        if password == "":
            raise ValueError(
                "管理员密码不能为空"
            )

        if len(password) > 1024:
            raise ValueError(
                "管理员密码长度不能超过 1024"
            )

    @staticmethod
    def _normalize_time(
            value: datetime | None,
    ) -> datetime:
        """获取 UTC 初始化时间."""
        if value is None:
            return datetime.now(
                timezone.utc
            )

        if (
                value.tzinfo is None
                or value.utcoffset() is None
        ):
            raise ValueError(
                "current_time 必须包含时区信息"
            )

        return value.astimezone(
            timezone.utc
        )
