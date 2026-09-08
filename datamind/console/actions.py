"""管理控制台资源动作分派。

将资源生命周期动作与 ASGI 请求处理解耦，避免控制台应用入口持续膨胀。
"""

from collections.abc import Callable
from typing import Any

from datamind.audit.enums import AuditSource


ServiceFactory = Callable[..., Any]


async def dispatch_resource_action(
        *,
        resource: str,
        identifier: str,
        action: str,
        reason: str | None,
        user_id: str,
        username: str,
        model_lifecycle_factory: ServiceFactory,
        model_deletion_factory: ServiceFactory,
        deployment_factory: ServiceFactory,
        routing_factory: ServiceFactory,
        experiment_factory: ServiceFactory,
        identity_factory: ServiceFactory,
) -> dict[str, Any]:
    """根据资源和动作调用相应领域服务。"""
    if resource == "models":
        if action in {"activate", "deactivate", "deprecate", "archive"}:
            lifecycle_service = model_lifecycle_factory()
            lifecycle_action = getattr(lifecycle_service, action)
            return await lifecycle_action(
                model_id=identifier,
                updated_by=username,
            )

        deletion_service = model_deletion_factory()
        if action == "delete":
            return await deletion_service.delete(
                model_id=identifier,
                reason=reason,
                operator=username,
            )
        if action == "restore":
            return await deletion_service.restore(
                model_id=identifier,
                operator=username,
            )
        if action == "purge":
            return await deletion_service.purge(
                model_id=identifier,
                reason=reason,
                operator=username,
            )
        raise ValueError(f"不支持的模型操作: {action}")

    if resource == "versions":
        return await _dispatch_version_action(
            identifier=identifier,
            action=action,
            reason=reason,
            username=username,
            lifecycle_factory=model_lifecycle_factory,
            deletion_factory=model_deletion_factory,
        )

    if resource == "deployments":
        service = deployment_factory()

        if action == "enable":
            return await service.enable_deployment(
                deployment_id=identifier,
                updated_by=username,
            )
        if action == "disable":
            return await service.disable_deployment(
                deployment_id=identifier,
                updated_by=username,
            )
        if action == "delete":
            return await service.delete_deployment(
                deployment_id=identifier,
                reason=reason,
                deleted_by=username,
            )
        if action == "restore":
            return await service.restore_deployment(
                deployment_id=identifier,
                restored_by=username,
            )
        raise ValueError(f"不支持的部署操作: {action}")

    if resource == "routings":
        service = routing_factory()

        if action == "enable":
            return await service.enable_routing(
                routing_id=identifier,
                updated_by=username,
            )
        if action == "disable":
            return await service.disable_routing(
                routing_id=identifier,
                updated_by=username,
            )
        if action == "delete":
            return await service.delete_routing(
                routing_id=identifier,
                reason=reason,
                deleted_by=username,
            )
        if action == "restore":
            return await service.restore_routing(
                routing_id=identifier,
                restored_by=username,
            )
        raise ValueError(f"不支持的路由操作: {action}")

    if resource == "experiments":
        service = experiment_factory()

        if action == "delete":
            return await service.delete_experiment(
                experiment_id=identifier,
                reason=reason,
                deleted_by=username,
            )
        if action == "restore":
            return await service.restore_experiment(
                experiment_id=identifier,
                restored_by=username,
            )
        return await service.transition_experiment(
            experiment_id=identifier,
            action=action,
            updated_by=username,
        )

    if resource == "variants":
        service = experiment_factory()

        if action == "delete":
            return await service.delete_variant(
                variant_id=identifier,
                reason=reason,
                deleted_by=username,
            )
        if action == "restore":
            return await service.restore_variant(
                variant_id=identifier,
                restored_by=username,
            )
        if action in {"enable", "disable"}:
            return await service.set_variant_active(
                variant_id=identifier,
                active=action == "enable",
                updated_by=username,
            )
        raise ValueError(f"不支持的分组操作: {action}")

    if resource in {"users", "roles"}:
        return await _dispatch_identity_action(
            resource=resource,
            identifier=identifier,
            action=action,
            reason=reason,
            user_id=user_id,
            username=username,
            identity_factory=identity_factory,
        )

    raise ValueError(f"不支持的管理资源: {resource}")


async def _dispatch_version_action(
        *,
        identifier: str,
        action: str,
        reason: str | None,
        username: str,
        lifecycle_factory: ServiceFactory,
        deletion_factory: ServiceFactory,
) -> dict[str, Any]:
    """分派模型版本生命周期和删除动作。"""
    if action in {"activate", "deactivate", "deprecate", "archive"}:
        service = lifecycle_factory()
        handler = getattr(service, action)
        return await handler(
            version_id=identifier,
            updated_by=username,
        )

    service = deletion_factory()

    if action == "delete":
        return await service.delete(
            version_id=identifier,
            reason=reason,
            operator=username,
        )
    if action == "restore":
        return await service.restore(
            version_id=identifier,
            operator=username,
        )
    if action == "purge":
        return await service.purge(
            version_id=identifier,
            reason=reason,
            operator=username,
        )
    raise ValueError(f"不支持的模型版本操作: {action}")


async def _dispatch_identity_action(
        *,
        resource: str,
        identifier: str,
        action: str,
        reason: str | None,
        user_id: str,
        username: str,
        identity_factory: ServiceFactory,
) -> dict[str, Any]:
    """分派用户和角色管理动作。"""
    service = identity_factory(
        audit_source=AuditSource.HTTP,
    )
    arguments = {
        "operator_id": user_id,
        "operator": username,
    }

    if resource == "users":
        arguments["username"] = identifier
        resource_label = "用户"
        method_suffix = "user"
    else:
        arguments["name"] = identifier
        resource_label = "角色"
        method_suffix = "role"

    if action in {"enable", "disable"}:
        handler = getattr(service, f"{action}_{method_suffix}")
        return await handler(**arguments)
    if action == "delete":
        handler = getattr(service, f"delete_{method_suffix}")
        return await handler(
            **arguments,
            reason=reason,
        )
    raise ValueError(f"不支持的{resource_label}操作: {action}")
