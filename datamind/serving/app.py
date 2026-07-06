# datamind/serving/app.py

"""模型服务 HTTP 应用

提供常驻模型服务进程。

核心功能：
  - /health: 健康检查
  - /admin/deployments/{deployment_id}/load: 加载部署
  - /admin/deployments/{deployment_id}/unload: 卸载部署
  - /admin/deployments/{deployment_id}/reload: 重载部署
  - /admin/deployments/{deployment_id}: 查看部署运行状态
  - /admin/deployments: 查看当前进程已加载部署
"""

import os

from fastapi import FastAPI, HTTPException, Query

from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    RuntimeRouteError,
    VersionNotFoundError,
)
from datamind.runtime.manager import RuntimeManager

ERROR_STATUS_MAP = {
    DeploymentNotFoundError: 404,
    VersionNotFoundError: 404,
    InvalidDeploymentStateError: 409,
    RuntimeRouteError: 400,
    BackendError: 500,
}


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    worker_id = os.getenv("DATAMIND_WORKER_ID", "default")

    manager = RuntimeManager(
        worker_id=worker_id,
    )

    app = FastAPI(
        title="Datamind Serving",
        version="0.1.0",
    )

    app.state.manager = manager

    @app.get("/health")
    async def health():
        """健康检查"""
        return {
            "status": "ok",
            "worker_id": manager.worker_id,
            "loaded_count": manager.count(),
        }

    @app.post("/admin/deployments/{deployment_id}/load")
    async def load_deployment(
        deployment_id: str,
        operator: str = Query("system"),
        force: bool = Query(False),
    ):
        """加载部署"""
        try:
            runtime_model = await manager.start(
                deployment_id=deployment_id,
                operator=operator,
                force=force,
            )
        except Exception as exc:
            raise _to_http_exception(exc) from exc

        result = runtime_model.to_dict()
        result["loaded_in_memory"] = True
        result["worker_id"] = manager.worker_id

        return result

    @app.post("/admin/deployments/{deployment_id}/unload")
    async def unload_deployment(
        deployment_id: str,
        operator: str = Query("system"),
    ):
        """卸载部署"""
        try:
            runtime_model = await manager.stop(
                deployment_id=deployment_id,
                operator=operator,
            )
        except Exception as exc:
            raise _to_http_exception(exc) from exc

        return {
            "deployment_id": deployment_id,
            "worker_id": manager.worker_id,
            "unloaded": runtime_model is not None,
        }

    @app.post("/admin/deployments/{deployment_id}/reload")
    async def reload_deployment(
        deployment_id: str,
        operator: str = Query("system"),
    ):
        """重载部署"""
        try:
            runtime_model = await manager.restart(
                deployment_id=deployment_id,
                operator=operator,
            )
        except Exception as exc:
            raise _to_http_exception(exc) from exc

        result = runtime_model.to_dict()
        result["loaded_in_memory"] = True
        result["worker_id"] = manager.worker_id

        return result

    @app.get("/admin/deployments/{deployment_id}")
    async def show_deployment(
        deployment_id: str,
    ):
        """查看部署运行状态"""
        try:
            return await manager.status(
                deployment_id=deployment_id,
            )
        except Exception as exc:
            raise _to_http_exception(exc) from exc

    @app.get("/admin/deployments")
    async def list_deployments():
        """查看当前进程已加载部署"""
        items = manager.to_dicts()

        return {
            "worker_id": manager.worker_id,
            "count": len(items),
            "items": items,
        }

    return app


def _to_http_exception(
    error: Exception,
) -> HTTPException:
    """转换为 HTTP 异常"""
    status_code = 500

    for error_type, mapped_status in ERROR_STATUS_MAP.items():
        if isinstance(error, error_type):
            status_code = mapped_status
            break

    message = getattr(error, "message", str(error))

    return HTTPException(
        status_code=status_code,
        detail=message,
    )


app = create_app()