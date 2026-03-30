# datamind/core/ml/runtime/response.py
"""响应模型"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class PredictResponse:
    """预测响应"""
    score: Optional[float]                # 信用评分
    probability: float                     # 违约概率
    feature_scores: Optional[Dict[str, float]]  # 特征分
    reason_codes: Optional[List[Dict[str, Any]]]  # 拒绝原因
    capabilities: List[Dict[str, str]]    # 模型能力描述

    # 元信息
    model_id: str
    model_type: str
    model_role: str                       # champion / challenger
    task_type: str
    environment: str
    processing_time_ms: float
    supports_feature_scores: bool

    # 追踪信息
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 API 响应）"""
        return {
            "score": self.score,
            "probability": self.probability,
            "feature_scores": self.feature_scores,
            "reason_codes": self.reason_codes,
            "capabilities": self.capabilities,
            "meta": {
                "model_id": self.model_id,
                "model_type": self.model_type,
                "model_role": self.model_role,
                "task_type": self.task_type,
                "environment": self.environment,
                "processing_time_ms": self.processing_time_ms,
                "supports_feature_scores": self.supports_feature_scores,
                "request_id": self.request_id,
                "trace_id": self.trace_id
            }
        }