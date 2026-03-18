# datamind/api/routes/model_api.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Request
from typing import Optional
import os
import tempfile

from datamind.core.ml.model_registry import model_registry
from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.exceptions import (
    ModelNotFoundException, ModelAlreadyExistsException,
    ModelValidationException, ModelFileException
)
from datamind.core import log_manager, get_request_id
from datamind.core import TaskType, ModelType, Framework
from datamind.api.dependencies import get_current_user, get_api_key
from datamind.config import settings

router = APIRouter()


@router.post("/register")
async def register_model(
        request: Request,
        model_name: str = Form(...),
        model_version: str = Form(...),
        task_type: str = Form(...),
        model_type: str = Form(...),
        framework: str = Form(...),
        input_features: str = Form(...),  # JSON string
        output_schema: str = Form(...),  # JSON string
        description: Optional[str] = Form(None),
        model_params: Optional[str] = Form(None),  # JSON string
        tags: Optional[str] = Form(None),  # JSON string
        model_file: UploadFile = File(...),
        current_user: str = Depends(get_current_user),
        api_key: str = Depends(get_api_key)
):
    """
    注册新模型

    - **model_name**: 模型名称
    - **model_version**: 模型版本
    - **task_type**: 任务类型 (scoring/fraud_detection)
    - **model_type**: 模型类型
    - **framework**: 模型框架
    - **input_features**: 输入特征列表 (JSON数组)
    - **output_schema**: 输出格式定义 (JSON对象)
    - **description**: 模型描述
    - **model_params**: 模型参数 (JSON对象)
    - **tags**: 标签 (JSON对象)
    - **model_file**: 模型文件
    """
    request_id = get_request_id()

    try:
        # 解析JSON字段
        import json
        input_features_list = json.loads(input_features)
        output_schema_dict = json.loads(output_schema)
        model_params_dict = json.loads(model_params) if model_params else None
        tags_dict = json.loads(tags) if tags else None

        # 验证文件大小
        file_size = 0
        content = await model_file.read()
        file_size = len(content)

        if file_size > settings.MODEL_FILE_MAX_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"模型文件过大，最大允许 {settings.MODEL_FILE_MAX_SIZE / 1024 / 1024}MB"
            )

        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(model_file.filename)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # 注册模型
            model_id = model_registry.register_model(
                model_name=model_name,
                model_version=model_version,
                task_type=task_type,
                model_type=model_type,
                framework=framework,
                input_features=input_features_list,
                output_schema=output_schema_dict,
                created_by=current_user,
                model_file=open(tmp_path, 'rb'),
                description=description,
                model_params=model_params_dict,
                tags=tags_dict,
                ip_address=request.client.host if request.client else None
            )

            return {
                "success": True,
                "model_id": model_id,
                "message": f"模型 {model_name} v{model_version} 注册成功",
                "request_id": request_id
            }

        finally:
            # 清理临时文件
            os.unlink(tmp_path)

    except ModelAlreadyExistsException as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ModelValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelFileException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON格式错误: {str(e)}")
    except Exception as e:
        log_manager.log_audit(
            action="MODEL_REGISTER_API_ERROR",
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.get("/{model_id}")
async def get_model(
        model_id: str,
        request: Request,
        current_user: str = Depends(get_current_user)
):
    """获取模型信息"""
    try:
        model_info = model_registry.get_model_info(model_id)
        if not model_info:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")

        # 添加加载状态
        model_info['is_loaded'] = model_loader.is_loaded(model_id)

        return model_info

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型信息失败: {str(e)}")


@router.get("/")
async def list_models(
        request: Request,
        task_type: Optional[str] = None,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        framework: Optional[str] = None,
        is_production: Optional[bool] = None,
        current_user: str = Depends(get_current_user)
):
    """列出模型"""
    try:
        models = model_registry.list_models(
            task_type=task_type,
            status=status,
            model_type=model_type,
            framework=framework,
            is_production=is_production
        )

        # 添加加载状态
        for model in models:
            model['is_loaded'] = model_loader.is_loaded(model['model_id'])

        return {
            "total": len(models),
            "models": models,
            "request_id": get_request_id()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.post("/{model_id}/activate")
async def activate_model(
        model_id: str,
        request: Request,
        reason: Optional[str] = None,
        current_user: str = Depends(get_current_user)
):
    """激活模型"""
    try:
        model_registry.activate_model(
            model_id=model_id,
            operator=current_user,
            reason=reason,
            ip_address=request.client.host if request.client else None
        )

        return {
            "success": True,
            "message": f"模型 {model_id} 已激活",
            "request_id": get_request_id()
        }

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"激活模型失败: {str(e)}")


@router.post("/{model_id}/deactivate")
async def deactivate_model(
        model_id: str,
        request: Request,
        reason: Optional[str] = None,
        current_user: str = Depends(get_current_user)
):
    """停用模型"""
    try:
        model_registry.deactivate_model(
            model_id=model_id,
            operator=current_user,
            reason=reason,
            ip_address=request.client.host if request.client else None
        )

        return {
            "success": True,
            "message": f"模型 {model_id} 已停用",
            "request_id": get_request_id()
        }

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停用模型失败: {str(e)}")


@router.post("/{model_id}/promote")
async def promote_model(
        model_id: str,
        request: Request,
        reason: Optional[str] = None,
        current_user: str = Depends(get_current_user)
):
    """提升为生产模型"""
    try:
        model_registry.set_production_model(
            model_id=model_id,
            operator=current_user,
            reason=reason,
            ip_address=request.client.host if request.client else None
        )

        return {
            "success": True,
            "message": f"模型 {model_id} 已设置为生产模型",
            "request_id": get_request_id()
        }

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"设置生产模型失败: {str(e)}")


@router.post("/{model_id}/load")
async def load_model(
        model_id: str,
        request: Request,
        current_user: str = Depends(get_current_user)
):
    """加载模型到内存"""
    try:
        success = model_loader.load_model(
            model_id=model_id,
            operator=current_user,
            ip_address=request.client.host if request.client else None
        )

        if success:
            return {
                "success": True,
                "message": f"模型 {model_id} 加载成功",
                "request_id": get_request_id()
            }
        else:
            raise HTTPException(status_code=500, detail=f"模型加载失败")

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载模型失败: {str(e)}")


@router.post("/{model_id}/unload")
async def unload_model(
        model_id: str,
        request: Request,
        current_user: str = Depends(get_current_user)
):
    """从内存卸载模型"""
    try:
        model_loader.unload_model(
            model_id=model_id,
            operator=current_user,
            ip_address=request.client.host if request.client else None
        )

        return {
            "success": True,
            "message": f"模型 {model_id} 已卸载",
            "request_id": get_request_id()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"卸载模型失败: {str(e)}")


@router.get("/{model_id}/history")
async def get_model_history(
        model_id: str,
        request: Request,
        current_user: str = Depends(get_current_user)
):
    """获取模型历史"""
    try:
        history = model_registry.get_model_history(model_id)

        return {
            "model_id": model_id,
            "history": history,
            "request_id": get_request_id()
        }

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型历史失败: {str(e)}")


@router.delete("/{model_id}")
async def delete_model(
        model_id: str,
        request: Request,
        reason: Optional[str] = None,
        current_user: str = Depends(get_current_user)
):
    """删除模型（软删除）"""
    try:
        # 先卸载模型
        if model_loader.is_loaded(model_id):
            model_loader.unload_model(model_id, current_user)

        # 归档模型
        model_registry.delete_model(
            model_id=model_id,
            operator=current_user,
            reason=reason,
            ip_address=request.client.host if request.client else None
        )

        return {
            "success": True,
            "message": f"模型 {model_id} 已删除",
            "request_id": get_request_id()
        }

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除模型失败: {str(e)}")


@router.get("/types/task")
async def get_task_types():
    """获取任务类型列表"""
    return {
        "task_types": [{"value": t.value, "name": t.name} for t in TaskType],
        "request_id": get_request_id()
    }


@router.get("/types/model")
async def get_model_types(framework: Optional[str] = None):
    """获取模型类型列表"""
    from datamind.core import get_compatible_model_types

    if framework:
        try:
            framework_enum = Framework(framework)
            model_types = get_compatible_model_types(framework_enum)
            return {
                "framework": framework,
                "model_types": [{"value": mt.value, "name": mt.name} for mt in model_types],
                "request_id": get_request_id()
            }
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的框架: {framework}")

    return {
        "model_types": [{"value": t.value, "name": t.name} for t in ModelType],
        "request_id": get_request_id()
    }


@router.get("/types/framework")
async def get_frameworks(model_type: Optional[str] = None):
    """获取框架列表"""
    from datamind.core import get_compatible_frameworks

    if model_type:
        try:
            model_type_enum = ModelType(model_type)
            frameworks = get_compatible_frameworks(model_type_enum)
            return {
                "model_type": model_type,
                "frameworks": [{"value": f.value, "name": f.name} for f in frameworks],
                "request_id": get_request_id()
            }
        except ValueError:
            raise HTTPException(status_code=400, detail=f"不支持的模型类型: {model_type}")

    return {
        "frameworks": [{"value": f.value, "name": f.name} for f in Framework],
        "request_id": get_request_id()
    }


@router.get("/stats/loaded")
async def get_loaded_models(
        current_user: str = Depends(get_current_user)
):
    """获取已加载的模型列表"""
    loaded_models = model_loader.get_loaded_models()

    return {
        "total": len(loaded_models),
        "models": loaded_models,
        "request_id": get_request_id()
    }