
# datamind/api/routes/v2/fraud_api.py

"""反欺诈 API 路由 v2 版本

v2 版本改进：
  - 响应结构更加扁平化
  - 统一字段命名：probability, risk_score, risk_factors
  - 更好的错误信息格式
  - 增加更多元数据
"""

import time
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from datamind.core.ml.model import inference_engine
from datamind.core.common.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core.logging import log_audit, context
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.config import get_settings
from datamind.api.dependencies import get_api_key, get_current_user

router = APIRouter()
settings = get_settings()


class FraudRequestV2(BaseModel):
    """反欺诈请求模型 v2"""
    application_id: str = Field(..., description="申请ID")
    features: Dict[str, Any] = Field(..., description="特征字典")
    model_id: Optional[str] = Field(None, description="指定模型ID（可选）")
    experiment: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="实验配置，包含 ab_test_id 等"
    )
    options: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="可选参数"
    )


class RiskFactorV2(BaseModel):
    """风险因素"""
    factor: str = Field(..., description="风险因素名称")
    value: float = Field(..., description="风险值")
    weight: float = Field(..., description="权重")
    description: Optional[str] = Field(None, description="风险描述")


class FraudResponseV2(BaseModel):
    """反欺诈响应模型 v2"""
    probability: float = Field(..., description="欺诈概率 (0-1)")
    risk_score: float = Field(..., description="风险评分 (0-100)")
    risk_factors: List[RiskFactorV2] = Field(default_factory=list, description="风险因素列表")
    model: Dict[str, str] = Field(..., description="模型信息")
    request: Dict[str, str] = Field(..., description="请求追踪信息")
    performance: Dict[str, float] = Field(..., description="性能指标")
    experiment: Optional[Dict[str, Any]] = Field(None, description="A/B测试信息")
    version: str = Field(default="v2", description="API版本")


@router.post("/predict", response_model=FraudResponseV2)
async def predict_fraud(
        request: Request,
        fraud_request: FraudRequestV2,
        api_key: str = Depends(get_api_key),
        current_user: str = Depends(get_current_user)
):
    """
    反欺诈模型预测 v2

    返回欺诈概率、风险评分和风险因素列表。
    """
    start_time = time.time()
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        model_id = fraud_request.model_id
        ab_test_info = None

        # 从 experiment 字段获取 A/B 测试 ID
        ab_test_id = fraud_request.experiment.get("ab_test_id") if fraud_request.experiment else None

        # A/B 测试分流
        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    user_id=fraud_request.application_id,
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
                        "application_id": fraud_request.application_id,
                        "api_version": "v2",
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

        # 如果没有指定 model_id，使用生产模型
        if not model_id:
            from datamind.core.ml.model import model_registry
            models = model_registry.list_models(
                task_type=TaskType.FRAUD_DETECTION.value,
                is_production=True
            )
            if models:
                model_id = models[0]['model_id']
            else:
                raise HTTPException(
                    status_code=400,
                    detail="未配置生产模型，请指定model_id"
                )

        # 执行预测
        result = inference_engine.predict_fraud(
            model_id=model_id,
            features=fraud_request.features,
            application_id=fraud_request.application_id,
            user_id=current_user,
            ip_address=client_ip,
            api_key=api_key
        )

        processing_time_ms = (time.time() - start_time) * 1000

        # 获取模型元数据
        from datamind.core.ml.model import model_registry as registry
        model_meta = registry.get_model_info(model_id) or {}

        # 构建 v2 响应
        response_data = {
            "probability": result['fraud_probability'],
            "risk_score": result['risk_score'],
            "risk_factors": [
                {
                    "factor": rf.get('factor', 'unknown'),
                    "value": rf.get('value', 0),
                    "weight": rf.get('weight', 0)
                }
                for rf in result.get('risk_factors', [])
            ],
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
                "application_id": fraud_request.application_id
            },
            "performance": {
                "processing_time_ms": round(processing_time_ms, 2),
                "inference_time_ms": result.get('processing_time_ms', 0)
            },
            "version": "v2"
        }

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
                "application_id": fraud_request.application_id,
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "fraud_probability": result['fraud_probability'],
                "risk_score": result['risk_score'],
                "processing_time_ms": round(processing_time_ms, 2),
                "api_version": "v2",
                "ab_test_id": ab_test_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return response_data

    except ModelNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ModelInferenceException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log_audit(
            action=AuditAction.MODEL_INFERENCE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "application_id": fraud_request.application_id,
                "error": str(e),
                "api_version": "v2",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"预测失败: {str(e)}")