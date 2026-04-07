# Datamind/datamind/core/db/models/monitoring/api_log.py

"""API调用日志表定义
"""

from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, String, Integer, DateTime, Text, BigInteger,
    Numeric, Index,
    Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.sql import func

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import TaskType


class ApiCallLog(Base):
    """API调用日志表"""
    __tablename__ = 'api_call_logs'
    __table_args__ = (
        Index('idx_api_time', 'created_at'),
        Index('idx_api_app_model', 'application_id', 'model_id'),
        Index('idx_api_request_id', 'request_id'),
        Index('idx_api_status', 'status_code'),
        Index('idx_api_task_type', 'task_type'),
        Index('idx_api_user_id', 'user_id'),
        Index('idx_api_partition_date', 'partition_date'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(50), unique=True, nullable=False, index=True)
    application_id = Column(String(50), nullable=False, index=True)
    model_id = Column(String(50), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    task_type = Column(
        SQLEnum(
            TaskType,
            name="task_type_enum",
            values_callable=enum_values
        ),
        nullable=False,
        default=TaskType.SCORING.value
    )

    endpoint = Column(String(100), nullable=False)

    request_data = Column(JSONB, nullable=True)
    response_data = Column(JSONB, nullable=True)
    request_headers = Column(JSONB, nullable=True)
    response_headers = Column(JSONB, nullable=True)

    processing_time_ms = Column(Integer, nullable=False)
    model_inference_time_ms = Column(Integer, nullable=True)
    total_time_ms = Column(Integer, nullable=True)

    status_code = Column(Integer, nullable=False)
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(200), nullable=True)
    api_key = Column(String(100), nullable=True)
    user_id = Column(String(50), nullable=True, index=True)

    cost_credits = Column(Numeric(10, 4), nullable=True)
    billing_info = Column(JSONB, nullable=True)

    business_metrics = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    partition_date = Column(DateTime, nullable=False,
                          server_default=func.date_trunc('day', func.now()))

    def __repr__(self):
        return f"<ApiCallLog(request_id='{self.request_id}', model='{self.model_id}', status={self.status_code})>"

    # ==================== 转换方法 ====================

    def to_dict(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """转换为字典

        参数:
            include_sensitive: 是否包含敏感信息（请求/响应数据、请求头等）

        返回:
            日志字典
        """
        data = {
            'request_id': self.request_id,
            'application_id': self.application_id,
            'model_id': self.model_id,
            'model_version': self.model_version,
            'task_type': self.task_type.value if self.task_type else None,
            'endpoint': self.endpoint,
            'processing_time_ms': self.processing_time_ms,
            'model_inference_time_ms': self.model_inference_time_ms,
            'total_time_ms': self.total_time_ms,
            'status_code': self.status_code,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'ip_address': str(self.ip_address) if self.ip_address else None,
            'user_agent': self.user_agent,
            'user_id': self.user_id,
            'cost_credits': float(self.cost_credits) if self.cost_credits else None,
            'business_metrics': self.business_metrics,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'partition_date': self.partition_date.isoformat() if self.partition_date else None,
        }

        if include_sensitive:
            data.update({
                'request_data': self.request_data,
                'response_data': self.response_data,
                'request_headers': self.request_headers,
                'response_headers': self.response_headers,
                'api_key': self.api_key,
                'billing_info': self.billing_info,
                'error_traceback': self.error_traceback,
            })

        return data

    def to_summary(self) -> Dict[str, Any]:
        """获取日志摘要（用于监控展示）"""
        return {
            'request_id': self.request_id,
            'model_id': self.model_id,
            'status_code': self.status_code,
            'processing_time_ms': self.processing_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    # ==================== 状态检查 ====================

    def is_success(self) -> bool:
        """检查请求是否成功"""
        return 200 <= self.status_code < 300

    def is_client_error(self) -> bool:
        """检查是否为客户端错误（4xx）"""
        return 400 <= self.status_code < 500

    def is_server_error(self) -> bool:
        """检查是否为服务器错误（5xx）"""
        return 500 <= self.status_code < 600

    def has_error(self) -> bool:
        """检查是否有错误"""
        return self.status_code >= 400

    def is_timeout(self) -> bool:
        """检查是否为超时错误"""
        return self.status_code == 408 or self.status_code == 504

    def is_rate_limited(self) -> bool:
        """检查是否为限流错误"""
        return self.status_code == 429

    def is_unauthorized(self) -> bool:
        """检查是否为未授权错误"""
        return self.status_code == 401

    def is_forbidden(self) -> bool:
        """检查是否为禁止访问错误"""
        return self.status_code == 403

    def is_not_found(self) -> bool:
        """检查是否为资源不存在错误"""
        return self.status_code == 404

    # ==================== 性能检查 ====================

    def is_slow_request(self, threshold_ms: int = 1000) -> bool:
        """检查是否为慢请求

        参数:
            threshold_ms: 慢请求阈值（毫秒），默认1000ms

        返回:
            True 表示慢请求，False 表示正常
        """
        return self.processing_time_ms > threshold_ms

    def is_very_slow_request(self, threshold_ms: int = 3000) -> bool:
        """检查是否为非常慢的请求

        参数:
            threshold_ms: 阈值（毫秒），默认3000ms

        返回:
            True 表示非常慢，False 表示正常
        """
        return self.processing_time_ms > threshold_ms

    def get_time_breakdown(self) -> Dict[str, Optional[int]]:
        """获取时间分解

        返回:
            包含各阶段耗时的字典
        """
        return {
            'total_ms': self.total_time_ms,
            'processing_ms': self.processing_time_ms,
            'inference_ms': self.model_inference_time_ms,
            'overhead_ms': self.total_time_ms - self.processing_time_ms if self.total_time_ms else None,
        }

    # ==================== 业务指标 ====================

    def get_business_metric(self, key: str, default: Any = None) -> Any:
        """获取业务指标值

        参数:
            key: 指标键名
            default: 默认值

        返回:
            指标值，不存在时返回默认值
        """
        if not self.business_metrics:
            return default
        return self.business_metrics.get(key, default)

    def get_score(self) -> Optional[float]:
        """获取评分（仅评分卡任务）"""
        if self.task_type != TaskType.SCORING:
            return None
        return self.get_business_metric('score')

    def get_risk_level(self) -> Optional[str]:
        """获取风险等级（仅反欺诈任务）"""
        if self.task_type != TaskType.FRAUD_DETECTION:
            return None
        return self.get_business_metric('risk_level')

    def get_risk_score(self) -> Optional[float]:
        """获取风险评分（仅反欺诈任务）"""
        if self.task_type != TaskType.FRAUD_DETECTION:
            return None
        return self.get_business_metric('risk_score')

    # ==================== 计费相关 ====================

    def has_cost(self) -> bool:
        """检查是否有计费信息"""
        return self.cost_credits is not None and self.cost_credits > 0

    def get_cost_credits_float(self) -> Optional[float]:
        """获取计费积分（浮点数）"""
        return float(self.cost_credits) if self.cost_credits else None

    # ==================== 工厂方法 ====================

    @classmethod
    def create(
        cls,
        request_id: str,
        application_id: str,
        model_id: str,
        model_version: str,
        endpoint: str,
        processing_time_ms: int,
        status_code: int,
        task_type: TaskType = TaskType.SCORING,
        model_inference_time_ms: Optional[int] = None,
        total_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        error_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        api_key: Optional[str] = None,
        user_id: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        business_metrics: Optional[Dict[str, Any]] = None,
        cost_credits: Optional[float] = None
    ) -> 'ApiCallLog':
        """创建API调用日志实例

        参数:
            request_id: 请求ID
            application_id: 应用ID
            model_id: 模型ID
            model_version: 模型版本
            endpoint: 端点
            processing_time_ms: 处理时间（毫秒）
            status_code: 状态码
            task_type: 任务类型，默认评分卡
            model_inference_time_ms: 模型推理时间（毫秒）
            total_time_ms: 总时间（毫秒）
            error_message: 错误消息
            error_code: 错误码
            ip_address: IP地址
            user_agent: User-Agent
            api_key: API密钥
            user_id: 用户ID
            request_data: 请求数据
            response_data: 响应数据
            business_metrics: 业务指标
            cost_credits: 计费积分

        返回:
            ApiCallLog 实例
        """
        return cls(
            request_id=request_id,
            application_id=application_id,
            model_id=model_id,
            model_version=model_version,
            task_type=task_type,
            endpoint=endpoint,
            processing_time_ms=processing_time_ms,
            model_inference_time_ms=model_inference_time_ms,
            total_time_ms=total_time_ms,
            status_code=status_code,
            error_message=error_message,
            error_code=error_code,
            ip_address=ip_address,
            user_agent=user_agent,
            api_key=api_key,
            user_id=user_id,
            request_data=request_data,
            response_data=response_data,
            business_metrics=business_metrics,
            cost_credits=cost_credits,
        )

    @classmethod
    def create_success(
        cls,
        request_id: str,
        application_id: str,
        model_id: str,
        model_version: str,
        endpoint: str,
        processing_time_ms: int,
        response_data: Optional[Dict[str, Any]] = None,
        business_metrics: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> 'ApiCallLog':
        """创建成功请求的日志实例

        参数:
            request_id: 请求ID
            application_id: 应用ID
            model_id: 模型ID
            model_version: 模型版本
            endpoint: 端点
            processing_time_ms: 处理时间（毫秒）
            response_data: 响应数据
            business_metrics: 业务指标
            **kwargs: 其他参数

        返回:
            ApiCallLog 实例
        """
        return cls.create(
            request_id=request_id,
            application_id=application_id,
            model_id=model_id,
            model_version=model_version,
            endpoint=endpoint,
            processing_time_ms=processing_time_ms,
            status_code=200,
            response_data=response_data,
            business_metrics=business_metrics,
            **kwargs
        )

    @classmethod
    def create_error(
        cls,
        request_id: str,
        application_id: str,
        model_id: str,
        model_version: str,
        endpoint: str,
        processing_time_ms: int,
        status_code: int,
        error_message: str,
        error_code: Optional[str] = None,
        **kwargs
    ) -> 'ApiCallLog':
        """创建错误请求的日志实例

        参数:
            request_id: 请求ID
            application_id: 应用ID
            model_id: 模型ID
            model_version: 模型版本
            endpoint: 端点
            processing_time_ms: 处理时间（毫秒）
            status_code: 状态码
            error_message: 错误消息
            error_code: 错误码
            **kwargs: 其他参数

        返回:
            ApiCallLog 实例
        """
        return cls.create(
            request_id=request_id,
            application_id=application_id,
            model_id=model_id,
            model_version=model_version,
            endpoint=endpoint,
            processing_time_ms=processing_time_ms,
            status_code=status_code,
            error_message=error_message,
            error_code=error_code,
            **kwargs
        )