# datamind/core/ml/runtime/request.py
"""请求模型"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class PredictRequest:
    """预测请求"""
    model_id: str
    features: Dict[str, Any]

    # 可选参数
    need_explain: bool = False
    need_reason: bool = False

    # 策略路由参数
    task_type: str = "scoring"           # scoring / fraud_detection
    environment: str = "production"      # development / testing / staging / production
    user_id: Optional[str] = None
    challenger_weight: float = 0.0       # 陪跑模型流量权重 (0-1)

    # 追踪信息
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    # 审计信息
    user_id_for_audit: Optional[str] = None
    ip_address: Optional[str] = None
    api_key: Optional[str] = None