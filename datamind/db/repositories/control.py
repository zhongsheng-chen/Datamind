"""模型运行控制仓储

提供模型运行期望状态的查询与管理能力。

核心功能：
  - get_control: 获取运行控制记录
  - get_deployment_control: 获取部署对应的运行控制记录
  - list_controls: 获取运行控制记录列表
  - list_loaded_controls: 获取期望加载的控制记录
  - create_control: 创建运行控制记录
  - set_loaded: 设置期望状态为 loaded
  - set_unloaded: 设置期望状态为 unloaded
  - request_reload: 请求重新加载模型

说明：
  Control 记录模型部署的期望运行状态。

  Runtime 记录各 Worker 的实际运行状态。

  Control 按 environment 进行环境隔离，
  各 Worker 只处理所属运行环境的控制记录。

  新创建的 Control 默认状态为 unloaded，
  初始 generation 为 1。

  状态变化规则：

    unloaded -> loaded
        desired_status 设置为 loaded
        generation 递增

    loaded -> unloaded
        desired_status 设置为 unloaded
        generation 递增

    loaded -> reload
        desired_status 保持 loaded
        generation 递增

    重复执行 load 或 unload
        保持幂等
        generation 不变

使用示例：
  from datamind.constants import Environment
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.control import ControlRepository

  async with UnitOfWork() as uow:
      repo = ControlRepository(
          uow.session
      )

      control = repo.create_control(
          control_id="ctl_0123456789abcdef",
          deployment_id="dep_0123456789abcdef",
          environment=Environment.PRODUCTION,
          created_by="system",
      )

      repo.set_loaded(
          control,
          updated_by="system",
      )
"""

from sqlalchemy import select

from datamind.constants import Environment
from datamind.db.models.controls import Control
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import RuntimeControlStatus


class ControlRepository(BaseRepository):
    """模型运行控制仓储"""

    async def get_control(
            self,
            control_id: str,
    ) -> Control | None:
        """获取运行控制记录

        参数：
            control_id: 控制 ID

        返回：
            运行控制记录对象，不存在时返回 None
        """
        stmt = select(
            Control
        ).where(
            Control.control_id
            == control_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_deployment_control(
            self,
            deployment_id: str,
    ) -> Control | None:
        """获取部署对应的运行控制记录

        参数：
            deployment_id: 部署 ID

        返回：
            运行控制记录对象，不存在时返回 None
        """
        stmt = select(
            Control
        ).where(
            Control.deployment_id
            == deployment_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_controls(
            self,
            *,
            control_id: str | None = None,
            deployment_id: str | None = None,
            environment: Environment | None = None,
            desired_status: RuntimeControlStatus | None = None,
            created_by: str | None = None,
            updated_by: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Control]:
        """获取运行控制记录列表

        参数：
            control_id: 控制 ID（可选）
            deployment_id: 部署 ID（可选）
            environment: 运行环境（可选）
            desired_status: 期望运行状态（可选）
            created_by: 创建人（可选）
            updated_by: 更新人（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            运行控制记录列表，按更新时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        if (
                limit is not None
                and limit < 0
        ):
            raise ValueError(
                "limit 不能小于 0"
            )

        if (
                offset is not None
                and offset < 0
        ):
            raise ValueError(
                "offset 不能小于 0"
            )

        stmt = select(
            Control
        )

        if control_id is not None:
            stmt = stmt.where(
                Control.control_id
                == control_id
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Control.deployment_id
                == deployment_id
            )

        if environment is not None:
            stmt = stmt.where(
                Control.environment
                == str(
                    environment
                )
            )

        if desired_status is not None:
            stmt = stmt.where(
                Control.desired_status
                == str(
                    desired_status
                )
            )

        if created_by is not None:
            stmt = stmt.where(
                Control.created_by
                == created_by
            )

        if updated_by is not None:
            stmt = stmt.where(
                Control.updated_by
                == updated_by
            )

        stmt = stmt.order_by(
            Control.updated_at.desc(),
            Control.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def list_loaded_controls(
            self,
            *,
            environment: Environment | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Control]:
        """获取期望加载的运行控制记录

        参数：
            environment: 运行环境（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            desired_status 为 loaded 的运行控制记录列表
        """
        return await self.list_controls(
            environment=environment,
            desired_status=(
                RuntimeControlStatus.LOADED
            ),
            limit=limit,
            offset=offset,
        )

    def create_control(
            self,
            *,
            control_id: str,
            deployment_id: str,
            environment: Environment,
            created_by: str | None = None,
    ) -> Control:
        """创建运行控制记录

        新创建的运行控制记录默认状态为 unloaded，
        初始控制版本号为 1。

        参数：
            control_id: 控制 ID
            deployment_id: 部署 ID
            environment: 运行环境
            created_by: 创建人（可选）

        返回：
            创建后的运行控制记录对象
        """
        new_control = Control(
            control_id=control_id,
            deployment_id=deployment_id,
            environment=str(
                environment
            ),
            desired_status=str(
                RuntimeControlStatus.UNLOADED
            ),
            generation=1,
        )

        if created_by is not None:
            new_control.created_by = created_by
            new_control.updated_by = created_by

        self.add(
            new_control
        )

        return new_control

    def set_loaded(
            self,
            control: Control,
            *,
            updated_by: str | None = None,
    ) -> Control:
        """设置期望状态为 loaded

        当当前状态不是 loaded 时：

          - desired_status 设置为 loaded
          - generation 递增
          - 更新 updated_by

        当当前状态已经是 loaded 时保持幂等，
        不修改 generation 和 updated_by。

        参数：
            control: 运行控制对象
            updated_by: 更新人（可选）

        返回：
            更新后的运行控制对象
        """
        target_status = str(
            RuntimeControlStatus.LOADED
        )

        if control.desired_status == target_status:
            return control

        control.desired_status = target_status
        control.generation += 1

        if updated_by is not None:
            control.updated_by = updated_by

        return control

    def set_unloaded(
            self,
            control: Control,
            *,
            updated_by: str | None = None,
    ) -> Control:
        """设置期望状态为 unloaded

        当当前状态不是 unloaded 时：

          - desired_status 设置为 unloaded
          - generation 递增
          - 更新 updated_by

        当当前状态已经是 unloaded 时保持幂等，
        不修改 generation 和 updated_by。

        参数：
            control: 运行控制对象
            updated_by: 更新人（可选）

        返回：
            更新后的运行控制对象
        """
        target_status = str(
            RuntimeControlStatus.UNLOADED
        )

        if control.desired_status == target_status:
            return control

        control.desired_status = target_status
        control.generation += 1

        if updated_by is not None:
            control.updated_by = updated_by

        return control

    def request_reload(
            self,
            control: Control,
            *,
            updated_by: str | None = None,
    ) -> Control:
        """请求重新加载模型

        reload 不改变 desired_status，
        通过 generation 递增通知各 Worker
        重新加载模型。

        仅允许对 desired_status 为 loaded
        的运行控制记录执行 reload。

        参数：
            control: 运行控制对象
            updated_by: 更新人（可选）

        返回：
            更新后的运行控制对象

        异常：
            ValueError: 当前期望状态不是 loaded
        """
        loaded_status = str(
            RuntimeControlStatus.LOADED
        )

        if control.desired_status != loaded_status:
            raise ValueError(
                "只有期望状态为 loaded 的部署"
                "才能执行 reload"
            )

        control.generation += 1

        if updated_by is not None:
            control.updated_by = updated_by

        return control
