# Datamind/datamind/core/db/models/monitoring/performance.py

"""模型性能监控表定义
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column, String, Integer, DateTime, Float, BigInteger,
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from datamind.core.db.base import Base, enum_values
from datamind.core.domain.enums import TaskType


class ModelPerformanceMetrics(Base):
    """模型性能监控表"""
    __tablename__ = 'model_performance_metrics'
    __table_args__ = (
        Index('idx_performance_model_date', 'model_id', 'date'),
        Index('idx_performance_task_type', 'task_type'),
        Index('idx_performance_date', 'date'),
        Index('idx_performance_model_version', 'model_id', 'model_version'),
        UniqueConstraint('model_id', 'model_version', 'date', name='uq_model_metric_date'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('public.model_metadata.model_id', ondelete='CASCADE'),
                     nullable=False, index=True)
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

    date = Column(DateTime, nullable=False)

    total_requests = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    timeout_count = Column(Integer, default=0)

    avg_response_time_ms = Column(Float)
    p50_response_time_ms = Column(Float)
    p95_response_time_ms = Column(Float)
    p99_response_time_ms = Column(Float)
    max_response_time_ms = Column(Integer)
    min_response_time_ms = Column(Integer)

    # 评分卡专用指标
    avg_score = Column(Float, nullable=True)
    score_distribution = Column(JSONB, nullable=True)
    score_bins = Column(JSONB, nullable=True)

    # 反欺诈专用指标
    fraud_rate = Column(Float, nullable=True)
    fraud_count = Column(Integer, nullable=True)
    risk_distribution = Column(JSONB, nullable=True)
    risk_levels = Column(JSONB, nullable=True)

    feature_importance_drift = Column(JSONB, nullable=True)

    avg_cpu_usage = Column(Float, nullable=True)
    avg_memory_usage = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    model = relationship("ModelMetadata", back_populates="performance_records")

    def __repr__(self):
        return f"<ModelPerformanceMetrics(model='{self.model_id}', date='{self.date}')>"

    # ==================== 转换方法 ====================

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'model_id': self.model_id,
            'model_version': self.model_version,
            'task_type': self.task_type.value if self.task_type else None,
            'date': self.date.isoformat() if self.date else None,
            'total_requests': self.total_requests,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'timeout_count': self.timeout_count,
            'success_rate': self.get_success_rate(),
            'error_rate': self.get_error_rate(),
            'avg_response_time_ms': self.avg_response_time_ms,
            'p50_response_time_ms': self.p50_response_time_ms,
            'p95_response_time_ms': self.p95_response_time_ms,
            'p99_response_time_ms': self.p99_response_time_ms,
            'max_response_time_ms': self.max_response_time_ms,
            'min_response_time_ms': self.min_response_time_ms,
            'avg_score': self.avg_score,
            'score_distribution': self.score_distribution,
            'fraud_rate': self.fraud_rate,
            'fraud_count': self.fraud_count,
            'risk_distribution': self.risk_distribution,
            'risk_levels': self.risk_levels,
            'feature_importance_drift': self.feature_importance_drift,
            'avg_cpu_usage': self.avg_cpu_usage,
            'avg_memory_usage': self.avg_memory_usage,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_summary(self) -> Dict[str, Any]:
        """获取性能摘要（用于监控展示）"""
        return {
            'model_id': self.model_id,
            'model_version': self.model_version,
            'date': self.date.isoformat() if self.date else None,
            'total_requests': self.total_requests,
            'success_rate': self.get_success_rate(),
            'avg_response_time_ms': self.avg_response_time_ms,
            'p95_response_time_ms': self.p95_response_time_ms,
            'error_rate': self.get_error_rate(),
        }

    # ==================== 统计方法 ====================

    def get_success_rate(self) -> Optional[float]:
        """获取成功率

        返回:
            成功率（0-100），没有请求时返回 None
        """
        if self.total_requests == 0:
            return None
        return round(self.success_count / self.total_requests * 100, 2)

    def get_error_rate(self) -> Optional[float]:
        """获取错误率

        返回:
            错误率（0-100），没有请求时返回 None
        """
        if self.total_requests == 0:
            return None
        return round(self.error_count / self.total_requests * 100, 2)

    def get_timeout_rate(self) -> Optional[float]:
        """获取超时率

        返回:
            超时率（0-100），没有请求时返回 None
        """
        if self.total_requests == 0:
            return None
        return round(self.timeout_count / self.total_requests * 100, 2)

    def get_availability(self) -> Optional[float]:
        """获取可用性（成功率）

        返回:
            可用性（0-100），没有请求时返回 None
        """
        return self.get_success_rate()

    def has_degradation(self, threshold_p95_ms: int = 1000) -> bool:
        """检查性能是否降级

        参数:
            threshold_p95_ms: P95响应时间阈值（毫秒），默认1000ms

        返回:
            True 表示性能降级，False 表示正常
        """
        if self.p95_response_time_ms is None:
            return False
        return self.p95_response_time_ms > threshold_p95_ms

    def has_high_error_rate(self, threshold: float = 5.0) -> bool:
        """检查错误率是否过高

        参数:
            threshold: 错误率阈值（百分比），默认5%

        返回:
            True 表示错误率过高，False 表示正常
        """
        error_rate = self.get_error_rate()
        if error_rate is None:
            return False
        return error_rate > threshold

    def is_healthy(self, error_threshold: float = 5.0, p95_threshold_ms: int = 1000) -> bool:
        """检查模型是否健康

        参数:
            error_threshold: 错误率阈值（百分比）
            p95_threshold_ms: P95响应时间阈值（毫秒）

        返回:
            True 表示健康，False 表示不健康
        """
        return not self.has_high_error_rate(error_threshold) and not self.has_degradation(p95_threshold_ms)

    # ==================== 评分卡专用方法 ====================

    def is_scoring_model(self) -> bool:
        """检查是否为评分卡模型"""
        return self.task_type == TaskType.SCORING

    def get_score_stats(self) -> Dict[str, Any]:
        """获取评分统计信息"""
        if not self.is_scoring_model():
            return {}

        return {
            'avg_score': self.avg_score,
            'score_distribution': self.score_distribution,
            'score_bins': self.score_bins,
        }

    def get_score_range(self) -> Optional[Dict[str, float]]:
        """获取评分范围

        返回:
            包含 min_score 和 max_score 的字典
        """
        if not self.score_distribution:
            return None

        scores = []
        for bin_name, count in self.score_distribution.items():
            try:
                if '-' in bin_name:
                    low, high = bin_name.split('-')
                    scores.append(float(low))
                    scores.append(float(high))
                else:
                    scores.append(float(bin_name))
            except (ValueError, TypeError):
                continue

        if not scores:
            return None

        return {
            'min_score': min(scores),
            'max_score': max(scores),
        }

    # ==================== 反欺诈专用方法 ====================

    def is_fraud_model(self) -> bool:
        """检查是否为反欺诈模型"""
        return self.task_type == TaskType.FRAUD_DETECTION

    def get_risk_stats(self) -> Dict[str, Any]:
        """获取风险统计信息"""
        if not self.is_fraud_model():
            return {}

        return {
            'fraud_rate': self.fraud_rate,
            'fraud_count': self.fraud_count,
            'risk_distribution': self.risk_distribution,
            'risk_levels': self.risk_levels,
        }

    def get_high_risk_count(self) -> int:
        """获取高风险数量"""
        if not self.risk_levels:
            return 0
        return self.risk_levels.get('high', 0)

    def get_medium_risk_count(self) -> int:
        """获取中风险数量"""
        if not self.risk_levels:
            return 0
        return self.risk_levels.get('medium', 0)

    def get_low_risk_count(self) -> int:
        """获取低风险数量"""
        if not self.risk_levels:
            return 0
        return self.risk_levels.get('low', 0)

    # ==================== 资源使用方法 ====================

    def get_resource_usage(self) -> Dict[str, Optional[float]]:
        """获取资源使用情况"""
        return {
            'avg_cpu_usage': self.avg_cpu_usage,
            'avg_memory_usage': self.avg_memory_usage,
        }

    def has_high_cpu_usage(self, threshold: float = 80.0) -> bool:
        """检查CPU使用率是否过高

        参数:
            threshold: 阈值（百分比），默认80%

        返回:
            True 表示过高，False 表示正常
        """
        if self.avg_cpu_usage is None:
            return False
        return self.avg_cpu_usage > threshold

    def has_high_memory_usage(self, threshold: float = 80.0) -> bool:
        """检查内存使用率是否过高

        参数:
            threshold: 阈值（百分比），默认80%

        返回:
            True 表示过高，False 表示正常
        """
        if self.avg_memory_usage is None:
            return False
        return self.avg_memory_usage > threshold

    # ==================== 特征漂移方法 ====================

    def has_feature_drift(self) -> bool:
        """检查是否有特征漂移"""
        return self.feature_importance_drift is not None and len(self.feature_importance_drift) > 0

    def get_drifted_features(self) -> List[str]:
        """获取发生漂移的特征列表"""
        if not self.feature_importance_drift:
            return []
        return list(self.feature_importance_drift.keys())

    def get_feature_drift_score(self, feature_name: str) -> Optional[float]:
        """获取特征漂移分数

        参数:
            feature_name: 特征名称

        返回:
            漂移分数（0-1），不存在时返回 None
        """
        if not self.feature_importance_drift:
            return None
        drift_info = self.feature_importance_drift.get(feature_name)
        if isinstance(drift_info, dict):
            return drift_info.get('drift_score')
        return drift_info

    # ==================== 更新方法 ====================

    def increment_requests(self, success: bool = True, is_timeout: bool = False) -> None:
        """增加请求计数

        参数:
            success: 是否成功
            is_timeout: 是否超时
        """
        self.total_requests += 1
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            if is_timeout:
                self.timeout_count += 1

    def update_response_time_stats(
        self,
        avg_time_ms: float,
        p50_ms: float,
        p95_ms: float,
        p99_ms: float,
        max_ms: int,
        min_ms: int
    ) -> None:
        """更新响应时间统计

        参数:
            avg_time_ms: 平均响应时间
            p50_ms: P50响应时间
            p95_ms: P95响应时间
            p99_ms: P99响应时间
            max_ms: 最大响应时间
            min_ms: 最小响应时间
        """
        self.avg_response_time_ms = avg_time_ms
        self.p50_response_time_ms = p50_ms
        self.p95_response_time_ms = p95_ms
        self.p99_response_time_ms = p99_ms
        self.max_response_time_ms = max_ms
        self.min_response_time_ms = min_ms

    def update_score_stats(
        self,
        avg_score: float,
        score_distribution: Dict[str, int],
        score_bins: Optional[List[float]] = None
    ) -> None:
        """更新评分统计（评分卡模型）

        参数:
            avg_score: 平均评分
            score_distribution: 评分分布
            score_bins: 评分分箱边界
        """
        if not self.is_scoring_model():
            return

        self.avg_score = avg_score
        self.score_distribution = score_distribution
        self.score_bins = score_bins

    def update_risk_stats(
        self,
        fraud_rate: float,
        fraud_count: int,
        risk_distribution: Dict[str, int],
        risk_levels: Dict[str, int]
    ) -> None:
        """更新风险统计（反欺诈模型）

        参数:
            fraud_rate: 欺诈率
            fraud_count: 欺诈数量
            risk_distribution: 风险分布
            risk_levels: 风险等级分布
        """
        if not self.is_fraud_model():
            return

        self.fraud_rate = fraud_rate
        self.fraud_count = fraud_count
        self.risk_distribution = risk_distribution
        self.risk_levels = risk_levels

    def update_resource_usage(self, cpu_usage: float, memory_usage: float) -> None:
        """更新资源使用情况

        参数:
            cpu_usage: CPU使用率（百分比）
            memory_usage: 内存使用率（百分比）
        """
        self.avg_cpu_usage = cpu_usage
        self.avg_memory_usage = memory_usage

    def update_feature_drift(self, feature_importance_drift: Dict[str, Any]) -> None:
        """更新特征漂移信息

        参数:
            feature_importance_drift: 特征漂移信息
        """
        self.feature_importance_drift = feature_importance_drift

    # ==================== 工厂方法 ====================

    @classmethod
    def create(
        cls,
        model_id: str,
        model_version: str,
        task_type: TaskType,
        date: Optional[datetime] = None
    ) -> 'ModelPerformanceMetrics':
        """创建性能指标实例

        参数:
            model_id: 模型ID
            model_version: 模型版本
            task_type: 任务类型
            date: 日期，默认为当天

        返回:
            ModelPerformanceMetrics 实例
        """
        if date is None:
            date = datetime.now()

        return cls(
            model_id=model_id,
            model_version=model_version,
            task_type=task_type,
            date=date,
            total_requests=0,
            success_count=0,
            error_count=0,
            timeout_count=0,
        )

    @classmethod
    def create_for_scoring(
        cls,
        model_id: str,
        model_version: str,
        date: Optional[datetime] = None
    ) -> 'ModelPerformanceMetrics':
        """创建评分卡模型性能指标实例"""
        return cls.create(model_id, model_version, TaskType.SCORING, date)

    @classmethod
    def create_for_fraud(
        cls,
        model_id: str,
        model_version: str,
        date: Optional[datetime] = None
    ) -> 'ModelPerformanceMetrics':
        """创建反欺诈模型性能指标实例"""
        return cls.create(model_id, model_version, TaskType.FRAUD_DETECTION, date)