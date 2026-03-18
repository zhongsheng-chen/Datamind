# Datamind/datamind/api/routes/scoring_api.py
from fastapi import APIRouter, HTTPException, Depends, Request, Body
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from datamind.core.ml.inference import inference_engine
from datamind.core.ml.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core import log_manager, get_request_id
from datamind.api.dependencies import get_api_key, get_current_user
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import settings

router = APIRouter()


class ScorecardRequest(BaseModel):
    """评分卡请求模型"""
    application_id: str = Field(..., description="申请ID")
    features: Dict[str, Any] = Field(..., description="特征字典")
    model_id: Optional[str] = Field(None, description="指定模型ID（可选）")
    ab_test_id: Optional[str] = Field(None, description="A/B测试ID（可选）")


class ScorecardResponse(BaseModel):
    """评分卡响应模型"""
    total_score: float
    feature_scores: Dict[str, float]
    model_id: str
    model_version: str
    application_id: str
    processing_time_ms: float
    timestamp: str
    request_id: str
    ab_test_info: Optional[Dict[str, Any]] = None


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
    request_id = get_request_id()

    try:
        model_id = score_request.model_id
        ab_test_info = None

        # 如果指定了A/B测试，获取分组
        if score_request.ab_test_id and settings.AB_TEST_ENABLED:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=score_request.ab_test_id,
                    user_id=score_request.application_id,
                    ip_address=request.client.host if request.client else None
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
                log_manager.log_audit(
                    action="AB_TEST_ERROR",
                    user_id=current_user,
                    ip_address=request.client.host if request.client else None,
                    details={"error": str(e), "ab_test_id": score_request.ab_test_id},
                    request_id=request_id
                )

        # 如果没有指定model_id且没有AB测试分配，使用生产模型
        if not model_id:
            # TODO: 获取生产模型ID
            # model_id = get_production_model_id(TaskType.SCORING)
            raise HTTPException(status_code=400, detail="必须指定model_id或使用A/B测试")

        # 执行预测
        result = inference_engine.predict_scorecard(
            model_id=model_id,
            features=score_request.features,
            application_id=score_request.application_id,
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            api_key=api_key
        )

        # 添加AB测试信息
        result['request_id'] = request_id
        result['ab_test_info'] = ab_test_info

        # 如果是在A/B测试中，记录结果
        if ab_test_info:
            try:
                ab_test_manager.record_result(
                    test_id=ab_test_info['test_id'],
                    user_id=score_request.application_id,
                    metrics={
                        'score': result['total_score'],
                        'processing_time_ms': result['processing_time_ms']
                    }
                )
            except Exception as e:
                # 记录结果失败不影响主流程
                log_manager.log_audit(
                    action="AB_TEST_RECORD_ERROR",
                    user_id=current_user,
                    ip_address=request.client.host if request.client else None,
                    details={"error": str(e)},
                    request_id=request_id
                )

        return result

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelInferenceException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log_manager.log_audit(
            action="SCORING_API_ERROR",
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            details={"error": str(e), "application_id": score_request.application_id},
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
    """
    request_id = get_request_id()

    results = []
    errors = []

    for idx, req in enumerate(requests):
        try:
            result = await predict_scorecard(request, req, api_key, current_user)
            results.append({
                "index": idx,
                "success": True,
                "data": result
            })
        except Exception as e:
            errors.append({
                "index": idx,
                "error": str(e)
            })

    return {
        "total": len(requests),
        "success": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
        "request_id": request_id
    }