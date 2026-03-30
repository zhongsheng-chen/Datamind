# datamind/api/routes/v2/model_api.py

"""模型管理 API 路由 v2 版本

v2 版本改进：
  - 统一响应格式
  - 更详细的模型信息
  - 支持模型统计信息
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Request
from pydantic import BaseModel

from datamind.core.ml.model.registry import model_registry
from datamind.core.ml.model.loader import model_loader
from datamind.core.logging import log_audit, context
from datamind.core.domain.enums import AuditAction
from datamind.api.dependencies import get_current_user
from datamind.config import get_settings

router = APIRouter()
settings = get_settings()


class ModelInfoV2(BaseModel):
    """模型信息响应 v2"""
    id: str
    name: str
    version: str
    task_type: str
    model_type: str
    framework: str
    status: str
    is_production: bool
    is_loaded: bool
    created_by: str
    created_at: str
    description: Optional[str] = None
    file_size_mb: Optional[float] = None
    input_features_count: Optional[int] = None
    output_schema: Optional[dict] = None


class ModelListResponseV2(BaseModel):
    """模型列表响应 v2"""
    total: int
    models: List[ModelInfoV2]
    request_id: str
    trace_id: str


@router.get("/", response_model=ModelListResponseV2)
async def list_models(
        request: Request,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        framework: Optional[str] = None,
        is_production: Optional[bool] = None,
        current_user: str = Depends(get_current_user)
):
    """列出模型 v2"""
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        models = model_registry.list_models(
            task_type=task_type,
            status=status,
            model_type=model_type,
            framework=framework,
            is_production=is_production
        )

        # 转换为 v2 格式
        model_list = []
        for model in models:
            # 获取文件大小
            file_size_mb = None
            input_features_count = None
            output_schema = None
            model_detail = model_registry.get_model_info(model['model_id'])
            if model_detail:
                file_size_mb = model_detail.get('file_size', 0) / 1024 / 1024
                input_features_count = len(model_detail.get('input_features', []))
                output_schema = model_detail.get('output_schema')

            model_list.append(ModelInfoV2(
                id=model['model_id'],
                name=model['model_name'],
                version=model['model_version'],
                task_type=model['task_type'],
                model_type=model['model_type'],
                framework=model['framework'],
                status=model['status'],
                is_production=model['is_production'],
                is_loaded=model.get('is_loaded', False),
                created_by=model['created_by'],
                created_at=model['created_at'],
                file_size_mb=round(file_size_mb, 2) if file_size_mb else None,
                input_features_count=input_features_count,
                output_schema=output_schema
            ))

        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "task_type": task_type,
                "status": status,
                "model_type": model_type,
                "framework": framework,
                "is_production": is_production,
                "result_count": len(model_list),
                "api_version": "v2",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return ModelListResponseV2(
            total=len(model_list),
            models=model_list,
            request_id=request_id,
            trace_id=trace_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")