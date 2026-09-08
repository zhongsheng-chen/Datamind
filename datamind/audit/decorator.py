"""审计装饰器

提供简单的函数级审计能力，自动记录操作成功和失败事件。

核心功能：
  - audit: 审计装饰器，仅支持异步函数

说明：
  - 适用于创建、注册等无需记录变更前状态的操作
  - 操作成功时，before 为 None，after 为函数返回结果
  - 操作失败时，before 和 after 均为 None，并记录错误信息
  - 需要记录 before 和 after 的状态变更操作，应在服务层显式调用 AuditRecorder
  - 采用 Fail-open 策略，审计记录失败不会覆盖业务结果或业务异常

使用示例：
  from datamind.audit import audit

  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  async def register_model(
      model_id: str,
      name: str,
  ):
      ...
"""

from collections.abc import Awaitable, Callable
from functools import wraps
from inspect import iscoroutinefunction, signature
from typing import Any, ParamSpec, TypeVar

import structlog

from datamind.audit.errors import AuditValidationError
from datamind.audit.policy import AuditFailureMode
from datamind.audit.recorder import AuditRecorder

logger = structlog.get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")

AuditData = dict[str, Any]


def _normalize_target_id(value: object | None) -> str | None:
    """将目标 ID 规范化为非空字符串"""
    if value is None:
        return None

    if not isinstance(value, str):
        raise AuditValidationError(
            "target_id 必须是字符串"
        )

    target_id = value.strip()

    return target_id or None


async def _record_audit_safely(
    recorder: AuditRecorder,
    *,
    action: str,
    target_type: str,
    target_id: str,
    status: str,
    error: str | None = None,
    after: Any | None = None,
    failure_mode: AuditFailureMode | None = None,
) -> None:
    """根据失败策略记录审计事件"""
    try:
        await recorder.record(
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            error=error,
            before=None,
            after=after,
            failure_mode=failure_mode,
        )

    except Exception as exc:
        mode = failure_mode or recorder.failure_mode

        if mode is AuditFailureMode.CLOSED:
            raise

        logger.error(
            "审计事件记录失败",
            audit_error=str(exc),
            action=action,
            target_type=target_type,
            target_id=target_id,
            status=status,
            exc_info=True,
        )


def audit(
    *,
    action: str,
    target_type: str,
    target_id_from: str | None = None,
    target_id_func: Callable[[AuditData, R], object | None] | None = None,
    failure_mode: AuditFailureMode | None = None,
) -> Callable[
    [Callable[P, Awaitable[R]]],
    Callable[P, Awaitable[R]],
]:
    """审计装饰器

    参数：
        action: 操作类型，格式为 resource.operation
        target_type: 目标类型
        target_id_from: 从函数参数中提取目标 ID 的参数名
        target_id_func: 从函数参数和返回值中生成目标 ID
        failure_mode: 审计失败处理策略，默认使用全局配置

    返回：
        包装后的异步函数

    异常：
        ValueError: 装饰器参数不合法
        TypeError: 装饰的函数不是异步函数
        AuditValidationError: 无法解析目标 ID
    """
    action = action.strip()
    target_type = target_type.strip()

    if not action:
        raise ValueError(
            "action 不能为空"
        )

    resource, separator, operation = action.partition(".")

    if (
        not separator
        or not resource.strip()
        or not operation.strip()
    ):
        raise ValueError(
            "action 必须采用 resource.operation 格式"
        )

    if not target_type:
        raise ValueError(
            "target_type 不能为空"
        )

    if target_id_from is not None:
        target_id_from = target_id_from.strip()

        if not target_id_from:
            raise ValueError(
                "target_id_from 不能为空字符串"
            )

    if target_id_from is None and target_id_func is None:
        raise ValueError(
            "target_id_from 和 target_id_func 至少需要提供一个"
        )

    def decorator(
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        """包装异步函数"""
        if not iscoroutinefunction(func):
            raise TypeError(
                f"装饰器仅支持 async 函数：{func.__name__}"
            )

        func_signature = signature(func)

        if (
            target_id_from is not None
            and target_id_from not in func_signature.parameters
        ):
            raise ValueError(
                f"函数 {func.__name__} "
                f"不包含参数：{target_id_from}"
            )

        recorder = AuditRecorder()

        @wraps(func)
        async def wrapper(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R:
            if not recorder.enabled:
                return await func(
                    *args,
                    **kwargs,
                )

            bound = func_signature.bind(
                *args,
                **kwargs,
            )
            bound.apply_defaults()

            params: AuditData = {
                name: value
                for name, value in bound.arguments.items()
                if name != "self"
            }

            target_id = (
                _normalize_target_id(
                    params.get(target_id_from)
                )
                if target_id_from
                else None
            )

            if target_id is None and target_id_func is None:
                raise AuditValidationError(
                    "缺少 target_id，"
                    f"参数 {target_id_from} 的值为空"
                )

            try:
                result = await func(
                    *args,
                    **kwargs,
                )

            except Exception as exc:
                await _record_audit_safely(
                    recorder,
                    action=action,
                    target_type=target_type,
                    target_id=(
                        target_id
                        or f"{target_type}:unknown"
                    ),
                    status="failed",
                    error=str(exc),
                    failure_mode=AuditFailureMode.OPEN,
                )

                raise

            if target_id is None and target_id_func:
                try:
                    target_id = _normalize_target_id(
                        target_id_func(
                            params,
                            result,
                        )
                    )

                except Exception as exc:
                    logger.error(
                        "审计目标 ID 解析失败",
                        audit_error=str(exc),
                        action=action,
                        target_type=target_type,
                        function=func.__name__,
                        exc_info=True,
                    )

                    return result

            if target_id is None:
                logger.error(
                    "审计目标 ID 为空",
                    action=action,
                    target_type=target_type,
                    function=func.__name__,
                )

                return result

            await _record_audit_safely(
                recorder,
                action=action,
                target_type=target_type,
                target_id=target_id,
                status="success",
                after=result,
                failure_mode=failure_mode,
            )

            return result

        return wrapper

    return decorator
