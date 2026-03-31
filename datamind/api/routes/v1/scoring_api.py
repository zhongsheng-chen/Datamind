# datamind/api/routes/v1/scoring_api.py

"""评分卡 API 路由

提供评分卡模型预测的 RESTful API 接口，支持单次预测和批量预测。

功能特性：
  - 单次评分预测：实时返回信用评分、违约概率和特征分
  - 批量评分预测：批量处理多个评分请求
  - A/B 测试支持：集成 A/B 测试分流
  - 生产模型自动选择：未指定模型时使用生产模型
  - 完整的审计日志：记录所有预测请求
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

API 端点：
  - POST /api/v1/scoring/predict - 单次评分预测
  - POST /api/v1/scoring/batch - 批量评分预测

请求模型（ScorecardRequest）：
  - application_id: 申请ID（必填），用于标识唯一申请
  - features: 特征字典（必填），包含模型所需的特征值
  - model_id: 模型ID（可选），不指定则使用生产模型
  - ab_test_id: A/B测试ID（可选），用于流量分流

响应模型（ScorecardResponse）：
  - total_score: 总评分
  - default_probability: 违约概率 (0-1)
  - feature_scores: 特征分详情
  - model_id: 使用的模型ID
  - model_version: 模型版本
  - application_id: 申请ID
  - processing_time_ms: 处理耗时（毫秒）
  - timestamp: 响应时间戳
  - request_id: 请求追踪ID
  - trace_id: 链路追踪ID
  - span_id: 当前Span ID
  - ab_test_info: A/B测试信息（如果启用）

错误处理：
  - 404: 模型不存在
  - 422: 模型推理失败（特征缺失、格式错误等）
  - 500: 服务器内部错误

A/B 测试集成：
  - 如果请求中指定了 ab_test_id，调用 A/B 测试管理器获取分组
  - 根据分组确定使用的模型
  - 在响应中返回 A/B 测试信息
  - 异步记录测试结果用于后续分析
"""

import time
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from datamind.core.ml.model import inference_engine
from datamind.core.common.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core.logging import log_audit, context, log_performance
from datamind.core.logging.debug import debug_print
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.config import get_settings
from datamind.api.dependencies import get_api_key, get_current_user

router = APIRouter()
settings = get_settings()


class ScorecardRequest(BaseModel):
    """评分卡请求模型"""
    application_id: str = Field(..., description="申请ID")
    features: Dict[str, Any] = Field(..., description="特征字典")
    model_id: Optional[str] = Field(None, description="指定模型ID（可选）")
    ab_test_id: Optional[str] = Field(None, description="A/B测试ID（可选）")


class ScorecardResponse(BaseModel):
    """评分卡响应模型"""
    total_score: float = Field(..., description="信用评分")
    default_probability: float = Field(..., description="违约概率 (0-1)")
    feature_scores: Dict[str, float] = Field(..., description="特征分详情")
    model_id: str = Field(..., description="使用的模型ID")
    model_version: str = Field(..., description="模型版本")
    application_id: str = Field(..., description="申请ID")
    processing_time_ms: float = Field(..., description="处理耗时（毫秒）")
    timestamp: str = Field(..., description="响应时间戳")
    request_id: str = Field(..., description="请求追踪ID")
    trace_id: str = Field(..., description="链路追踪ID")
    span_id: str = Field(..., description="当前Span ID")
    ab_test_info: Optional[Dict[str, Any]] = Field(None, description="A/B测试信息")


@router.post("/predict", response_model=ScorecardResponse)
async def predict_scorecard(
        request: Request,
        score_request: ScorecardRequest,
        api_key: str = Depends(get_api_key),
        current_user: str = Depends(get_current_user)
):
    """
    评分卡模型预测

    - **application_id**: 申请ID（必填）
    - **features**: 特征字典（必填）
    - **model_id**: 指定模型ID（可选，不指定则使用生产模型）
    - **ab_test_id**: A/B测试ID（可选）
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

        # 如果指定了A/B测试，获取分组
        if score_request.ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=score_request.ab_test_id,
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
                # A/B测试失败不影响主流程
                log_audit(
                    action=AuditAction.AB_TEST_ERROR.value,
                    user_id=current_user,
                    ip_address=client_ip,
                    details={
                        "error": str(e),
                        "ab_test_id": score_request.ab_test_id,
                        "application_id": score_request.application_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                debug_print("ScoringAPI", f"A/B测试错误: {e}")

        # 如果没有指定model_id且没有AB测试分配，使用生产模型
        if not model_id:
            # 从模型注册中心获取生产模型ID
            from datamind.core.ml.model import model_registry
            models = model_registry.list_models(
                task_type=TaskType.SCORING.value,
                is_production=True
            )
            if models:
                model_id = models[0]['model_id']
            else:
                log_audit(
                    action=AuditAction.MODEL_QUERY.value,
                    user_id=current_user,
                    ip_address=client_ip,
                    details={
                        "application_id": score_request.application_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=400,
                    detail="未配置生产模型，请指定model_id"
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

        # 构建响应
        response_data = {
            'total_score': result['total_score'],
            'default_probability': result['default_probability'],
            'feature_scores': result['feature_scores'],
            'model_id': result['model_id'],
            'model_version': result['model_version'],
            'application_id': score_request.application_id,
            'processing_time_ms': round(processing_time_ms, 2),
            'timestamp': result.get('timestamp', ''),
            'request_id': request_id,
            'trace_id': trace_id,
            'span_id': span_id,
            'ab_test_info': ab_test_info
        }

        # 记录成功审计日志
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "application_id": score_request.application_id,
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "total_score": result['total_score'],
                "default_probability": result['default_probability'],
                "processing_time_ms": round(processing_time_ms, 2),
                "ab_test_id": score_request.ab_test_id,
                "ab_test_group": ab_test_info.get('group_name') if ab_test_info else None,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        # 记录性能日志
        log_performance(
            operation=AuditAction.MODEL_INFERENCE.value,
            duration_ms=processing_time_ms,
            extra={
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "application_id": score_request.application_id,
                "trace_id": trace_id,
                "span_id": span_id
            }
        )

        # 如果是在A/B测试中，记录结果
        if ab_test_info:
            try:
                ab_test_manager.record_result(
                    test_id=ab_test_info['test_id'],
                    user_id=score_request.application_id,
                    metrics={
                        'score': result['total_score'],
                        'default_probability': result['default_probability'],
                        'processing_time_ms': processing_time_ms
                    }
                )
            except Exception as e:
                # 记录结果失败不影响主流程
                log_audit(
                    action=AuditAction.AB_TEST_ERROR.value,
                    user_id=current_user,
                    ip_address=client_ip,
                    details={
                        "error": str(e),
                        "test_id": ab_test_info['test_id'],
                        "application_id": score_request.application_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

        return response_data

    except ModelNotFoundException as e:
        processing_time_ms = (time.time() - start_time) * 1000
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "model_id": score_request.model_id,
                "application_id": score_request.application_id,
                "error": str(e),
                "processing_time_ms": round(processing_time_ms, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(status_code=404, detail=str(e))

    except ModelInferenceException as e:
        processing_time_ms = (time.time() - start_time) * 1000
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "model_id": score_request.model_id,
                "application_id": score_request.application_id,
                "error": str(e),
                "processing_time_ms": round(processing_time_ms, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(status_code=422, detail=str(e))

    except HTTPException:
        raise
    except Exception as e:
        processing_time_ms = (time.time() - start_time) * 1000
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "application_id": score_request.application_id,
                "error": str(e),
                "error_type": type(e).__name__,
                "processing_time_ms": round(processing_time_ms, 2),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")


@router.post("/batch")
async def batch_predict_scorecard(
        request: Request,
        requests: List[ScorecardRequest],
        api_key: str = Depends(get_api_key),
        current_user: str = Depends(get_current_user)
):
    """
    批量评分卡预测

    - **requests**: 评分卡请求列表

    返回批量处理结果，包含成功和失败的请求详情。
    """
    start_time = time.time()
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    results = []
    errors = []

    for idx, req in enumerate(requests):
        try:
            # 复用单次预测逻辑
            result = await predict_scorecard(request, req, api_key, current_user)
            results.append({
                "index": idx,
                "success": True,
                "data": result
            })
        except HTTPException as e:
            errors.append({
                "index": idx,
                "error": e.detail,
                "status_code": e.status_code
            })
        except Exception as e:
            errors.append({
                "index": idx,
                "error": str(e),
                "status_code": 500
            })

    processing_time_ms = (time.time() - start_time) * 1000

    log_audit(
        action=AuditAction.MODEL_BATCH_INFERENCE.value,
        user_id=current_user,
        ip_address=client_ip,
        details={
            "total_requests": len(requests),
            "success_count": len(results),
            "failed_count": len(errors),
            "processing_time_ms": round(processing_time_ms, 2),
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        },
        request_id=request_id
    )

    # 记录性能日志
    log_performance(
        operation=AuditAction.MODEL_BATCH_INFERENCE.value,
        duration_ms=processing_time_ms,
        extra={
            "batch_size": len(requests),
            "success_count": len(results),
            "failed_count": len(errors),
            "trace_id": trace_id,
            "span_id": span_id
        }
    )

    return {
        "total": len(requests),
        "success": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
        "request_id": request_id,
        "trace_id": trace_id,
        "processing_time_ms": round(processing_time_ms, 2)
    }