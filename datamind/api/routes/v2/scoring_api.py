# datamind/api/routes/v2/scoring_api.py

"""评分卡 API 路由 v2 版本

v2 版本改进：
  - 响应结构更加扁平化
  - 统一字段命名：score, probability, feature_contributions
  - 新增 feature_importance 支持
  - 更好的错误信息格式
  - 增加更多元数据

与 v1 响应对比：
  v1: {"total_score": 685.42, "default_probability": 0.023, "feature_scores": {...}}
  v2: {"score": 685.42, "probability": 0.023, "feature_contributions": {...}, "feature_importance": {...}}
"""

import time
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from datamind.core.ml.inference import inference_engine
from datamind.core.ml.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core.logging import log_audit, context, log_performance
from datamind.core.logging.debug import debug_print
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.config import get_settings
from datamind.api.dependencies import get_api_key, get_current_user

router = APIRouter()
settings = get_settings()


# ==================== 请求模型 ====================

class ScorecardRequestV2(BaseModel):
    """评分卡请求模型 v2"""
    application_id: str = Field(..., description="申请ID")
    features: Dict[str, Any] = Field(..., description="特征字典")
    model_id: Optional[str] = Field(None, description="指定模型ID（可选）")

    # v2 新增：统一实验配置
    experiment: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="实验配置，包含 ab_test_id 等"
    )

    # v2 新增：可选参数
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="可选参数，如 return_feature_importance 等"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "application_id": "APP_001",
                "features": {"age": 35, "income": 50000, "debt_ratio": 0.35},
                "model_id": "MDL_001",
                "experiment": {"ab_test_id": "ABT_001"},
                "options": {"return_feature_importance": True}
            }
        }


# ==================== 响应模型 ====================

class ModelInfoV2(BaseModel):
    """模型信息"""
    id: str = Field(..., description="模型ID")
    version: str = Field(..., description="模型版本")
    type: str = Field(..., description="模型类型")
    framework: Optional[str] = Field(None, description="模型框架")


class RequestInfoV2(BaseModel):
    """请求信息"""
    id: str = Field(..., description="请求ID")
    trace_id: str = Field(..., description="链路追踪ID")
    span_id: str = Field(..., description="当前Span ID")
    application_id: str = Field(..., description="申请ID")


class PerformanceInfoV2(BaseModel):
    """性能信息"""
    processing_time_ms: float = Field(..., description="总处理耗时（毫秒）")
    inference_time_ms: float = Field(..., description="模型推理耗时（毫秒）")
    feature_extraction_time_ms: Optional[float] = Field(None, description="特征提取耗时（毫秒）")


class ExperimentInfoV2(BaseModel):
    """实验信息"""
    test_id: str = Field(..., description="A/B测试ID")
    group_name: str = Field(..., description="实验组名称")
    in_test: bool = Field(..., description="是否在测试中")


class ScorecardResponseV2(BaseModel):
    """评分卡响应模型 v2"""
    # 核心结果
    score: float = Field(..., description="信用评分")
    probability: float = Field(..., description="违约概率 (0-1)")

    # 特征贡献
    feature_contributions: Dict[str, float] = Field(..., description="特征贡献分")

    # 特征重要性（可选）
    feature_importance: Optional[Dict[str, float]] = Field(None, description="特征重要性")

    # 模型信息
    model: ModelInfoV2 = Field(..., description="模型信息")

    # 请求信息
    request: RequestInfoV2 = Field(..., description="请求追踪信息")

    # 性能信息
    performance: PerformanceInfoV2 = Field(..., description="性能指标")

    # 实验信息
    experiment: Optional[ExperimentInfoV2] = Field(None, description="A/B测试信息")

    # 版本信息
    version: str = Field(default="v2", description="API版本")

    class Config:
        json_schema_extra = {
            "example": {
                "score": 685.42,
                "probability": 0.023,
                "feature_contributions": {
                    "age": 85.2,
                    "income": 120.5,
                    "debt_ratio": 45.3
                },
                "feature_importance": {
                    "income": 0.45,
                    "age": 0.32,
                    "debt_ratio": 0.23
                },
                "model": {
                    "id": "MDL_001",
                    "version": "1.0.0",
                    "type": "xgboost",
                    "framework": "xgboost"
                },
                "request": {
                    "id": "req_12345",
                    "trace_id": "trace_12345",
                    "span_id": "span_67890",
                    "application_id": "APP_001"
                },
                "performance": {
                    "processing_time_ms": 12.5,
                    "inference_time_ms": 8.3
                },
                "experiment": {
                    "test_id": "ABT_001",
                    "group_name": "A",
                    "in_test": True
                },
                "version": "v2"
            }
        }


# ==================== 错误响应模型 ====================

class ErrorDetailV2(BaseModel):
    """错误详情"""
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")


class ErrorResponseV2(BaseModel):
    """错误响应模型 v2"""
    error: ErrorDetailV2 = Field(..., description="错误信息")
    request_id: str = Field(..., description="请求ID")
    trace_id: str = Field(..., description="链路追踪ID")


# ==================== API 端点 ====================

@router.post(
    "/predict",
    response_model=ScorecardResponseV2,
    responses={
        400: {"model": ErrorResponseV2, "description": "请求参数错误"},
        404: {"model": ErrorResponseV2, "description": "模型不存在"},
        422: {"model": ErrorResponseV2, "description": "模型推理失败"},
        429: {"description": "请求过于频繁"},
        500: {"model": ErrorResponseV2, "description": "服务器内部错误"}
    }
)
async def predict_scorecard(
        request: Request,
        score_request: ScorecardRequestV2,
        api_key: str = Depends(get_api_key),
        current_user: str = Depends(get_current_user)
):
    """
    评分卡模型预测 v2

    返回信用评分、违约概率和特征贡献分。

    改进特性：
      - 响应结构扁平化
      - 支持返回特征重要性（通过 options.return_feature_importance）
      - 更详细的性能指标
      - 统一的错误响应格式
    """
    start_time = time.time()
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        model_id = score_request.model_id
        ab_test_info = None

        # 从 experiment 字段获取 A/B 测试 ID
        ab_test_id = score_request.experiment.get("ab_test_id") if score_request.experiment else None

        # A/B 测试分流
        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    user_id=score_request.application_id,
                    ip_address=client_ip
                )
                if assignment.get('in_test') and assignment.get('model_id'):
                    model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name'],
                        'in_test': True
                    }
            except Exception as e:
                log_audit(
                    action=AuditAction.AB_TEST_ERROR.value,
                    user_id=current_user,
                    ip_address=client_ip,
                    details={
                        "error": str(e),
                        "ab_test_id": ab_test_id,
                        "application_id": score_request.application_id,
                        "api_version": "v2",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

        # 如果没有指定 model_id，使用生产模型
        if not model_id:
            from datamind.core.ml.model_registry import model_registry
            models = model_registry.list_models(
                task_type=TaskType.SCORING.value,
                is_production=True
            )
            if models:
                model_id = models[0]['model_id']
            else:
                error_response = ErrorResponseV2(
                    error=ErrorDetailV2(
                        code="NO_PRODUCTION_MODEL",
                        message="未配置生产模型，请指定 model_id",
                        details={"supported_models": []}
                    ),
                    request_id=request_id,
                    trace_id=trace_id
                )
                raise HTTPException(
                    status_code=400,
                    detail=error_response.model_dump()
                )

        # 执行预测
        result = inference_engine.predict_scorecard(
            model_id=model_id,
            features=score_request.features,
            application_id=score_request.application_id,
            user_id=current_user,
            ip_address=client_ip,
            api_key=api_key
        )

        processing_time_ms = (time.time() - start_time) * 1000

        # 获取模型元数据
        from datamind.core.ml.model_registry import model_registry as registry
        model_meta = registry.get_model_info(model_id) or {}

        # 构建 v2 响应
        response_data = {
            "score": result['total_score'],
            "probability": result['default_probability'],
            "feature_contributions": result['feature_scores'],
            "model": {
                "id": result['model_id'],
                "version": result['model_version'],
                "type": model_meta.get('model_type', 'unknown'),
                "framework": model_meta.get('framework', 'unknown')
            },
            "request": {
                "id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "application_id": score_request.application_id
            },
            "performance": {
                "processing_time_ms": round(processing_time_ms, 2),
                "inference_time_ms": result.get('processing_time_ms', 0)
            },
            "version": "v2"
        }

        # 可选：返回特征重要性
        if score_request.options.get("return_feature_importance", False):
            response_data["feature_importance"] = result.get('feature_importance', {})

        # 可选：返回实验信息
        if ab_test_info:
            response_data["experiment"] = {
                "test_id": ab_test_info['test_id'],
                "group_name": ab_test_info['group_name'],
                "in_test": ab_test_info['in_test']
            }

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "application_id": score_request.application_id,
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "total_score": result['total_score'],
                "processing_time_ms": round(processing_time_ms, 2),
                "api_version": "v2",
                "return_feature_importance": score_request.options.get("return_feature_importance", False),
                "ab_test_id": ab_test_id,
                "ab_test_group": ab_test_info.get('group_name') if ab_test_info else None,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        # 性能日志
        log_performance(
            operation=AuditAction.MODEL_INFERENCE.value,
            duration_ms=processing_time_ms,
            extra={
                "model_id": result['model_id'],
                "application_id": score_request.application_id,
                "api_version": "v2",
                "trace_id": trace_id,
                "span_id": span_id
            }
        )

        return response_data

    except ModelNotFoundException as e:
        error_response = ErrorResponseV2(
            error=ErrorDetailV2(
                code="MODEL_NOT_FOUND",
                message=str(e),
                details={"model_id": score_request.model_id}
            ),
            request_id=request_id,
            trace_id=trace_id
        )
        raise HTTPException(status_code=404, detail=error_response.model_dump())

    except ModelInferenceException as e:
        error_response = ErrorResponseV2(
            error=ErrorDetailV2(
                code="INFERENCE_ERROR",
                message=str(e),
                details={
                    "model_id": score_request.model_id,
                    "application_id": score_request.application_id
                }
            ),
            request_id=request_id,
            trace_id=trace_id
        )
        raise HTTPException(status_code=422, detail=error_response.model_dump())

    except HTTPException:
        raise

    except Exception as e:
        error_response = ErrorResponseV2(
            error=ErrorDetailV2(
                code="INTERNAL_ERROR",
                message=f"预测失败: {str(e)}",
                details={
                    "error_type": type(e).__name__,
                    "application_id": score_request.application_id
                }
            ),
            request_id=request_id,
            trace_id=trace_id
        )
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "application_id": score_request.application_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "api_version": "v2",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=error_response.model_dump())