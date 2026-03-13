# core/models.py
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, JSON, Text,
    Float, Index, BigInteger, ForeignKey, Numeric, UniqueConstraint,
    Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import relationship, validates

from .enums import (
    TaskType, ModelType, Framework, ModelStatus,
    AuditAction, DeploymentEnvironment, ABTestStatus
)

Base = declarative_base()


class ModelMetadata(Base):
    """模型元数据表"""
    __tablename__ = 'model_metadata'
    __table_args__ = (
        Index('idx_model_status', 'status', 'is_production'),
        Index('idx_model_abtest', 'ab_test_group', 'status'),
        Index('idx_model_name_version', 'model_name', 'model_version', unique=True),
        Index('idx_model_created_at', 'created_at'),
        Index('idx_model_task_type', 'task_type'),
        Index('idx_model_type_framework', 'model_type', 'framework'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)
    model_type = Column(SQLEnum(ModelType), nullable=False)
    framework = Column(SQLEnum(Framework), nullable=False)

    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(BigInteger, nullable=False)

    input_features = Column(JSONB, nullable=False)
    output_schema = Column(JSONB, nullable=False)

    model_params = Column(JSONB, nullable=True)
    feature_importance = Column(JSONB, nullable=True)
    performance_metrics = Column(JSONB, nullable=True)

    status = Column(SQLEnum(ModelStatus), default=ModelStatus.INACTIVE)
    is_production = Column(Boolean, default=False)
    ab_test_group = Column(String(50), nullable=True)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deprecated_at = Column(DateTime(timezone=True), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)

    tags = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    versions = relationship("ModelVersionHistory", back_populates="model", cascade="all, delete-orphan")
    deployments = relationship("ModelDeployment", back_populates="model", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="model")
    performance_records = relationship("ModelPerformanceMetrics", back_populates="model")
    ab_test_assignments = relationship("ABTestAssignment", back_populates="model")


class ModelVersionHistory(Base):
    """模型版本历史表"""
    __tablename__ = 'model_version_history'
    __table_args__ = (
        Index('idx_history_model_time', 'model_id', 'operation_time'),
        Index('idx_history_operator', 'operator'),
        Index('idx_history_operation', 'operation'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('model_metadata.model_id', ondelete='CASCADE'), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    operation = Column(SQLEnum(AuditAction), nullable=False)

    operator = Column(String(50), nullable=False)
    operator_ip = Column(INET, nullable=True)
    operation_time = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(Text, nullable=True)
    metadata_snapshot = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)

    model = relationship("ModelMetadata", back_populates="versions")


class ModelDeployment(Base):
    """模型部署表"""
    __tablename__ = 'model_deployments'
    __table_args__ = (
        Index('idx_deployment_active', 'is_active'),
        Index('idx_deployment_env', 'environment'),
        Index('idx_deployment_model_env', 'model_id', 'environment'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    deployment_id = Column(String(50), unique=True, nullable=False)
    model_id = Column(String(50), ForeignKey('model_metadata.model_id', ondelete='CASCADE'), nullable=False)
    model_version = Column(String(20), nullable=False)

    environment = Column(SQLEnum(DeploymentEnvironment), nullable=False)
    endpoint_url = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)

    deployment_config = Column(JSONB, nullable=True)
    resources = Column(JSONB, nullable=True)

    deployed_by = Column(String(50), nullable=False)
    deployed_at = Column(DateTime(timezone=True), server_default=func.now())
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_status = Column(String(20), nullable=True)
    health_check_details = Column(JSONB, nullable=True)

    traffic_weight = Column(Integer, default=100)
    canary_config = Column(JSONB, nullable=True)

    model = relationship("ModelMetadata", back_populates="deployments")


class ApiCallLog(Base):
    """API调用日志表"""
    __tablename__ = 'api_call_logs'
    __table_args__ = (
        Index('idx_api_time', 'created_at'),
        Index('idx_api_app_model', 'application_id', 'model_id'),
        Index('idx_api_request_id', 'request_id'),
        Index('idx_api_status', 'status_code'),
        Index('idx_api_task_type', 'task_type'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(50), unique=True, nullable=False)
    application_id = Column(String(50), nullable=False, index=True)
    model_id = Column(String(50), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)

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
    user_id = Column(String(50), nullable=True)

    cost_credits = Column(Numeric(10, 4), nullable=True)
    billing_info = Column(JSONB, nullable=True)

    business_metrics = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    partition_date = Column(DateTime, nullable=False, server_default=func.date_trunc('day', func.now()))


class ModelPerformanceMetrics(Base):
    """模型性能监控表"""
    __tablename__ = 'model_performance_metrics'
    __table_args__ = (
        Index('idx_performance_model_date', 'model_id', 'date'),
        Index('idx_performance_task_type', 'task_type'),
        UniqueConstraint('model_id', 'model_version', 'date', name='uq_model_metric_date'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), ForeignKey('model_metadata.model_id', ondelete='CASCADE'), nullable=False, index=True)
    model_version = Column(String(20), nullable=False)

    task_type = Column(SQLEnum(TaskType), nullable=False)

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

    model = relationship("ModelMetadata", back_populates="performance_records")


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = 'audit_logs'
    __table_args__ = (
        Index('idx_audit_time', 'created_at'),
        Index('idx_audit_operator', 'operator'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_event', 'event_type'),
        Index('idx_audit_action', 'action'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    audit_id = Column(String(50), unique=True, nullable=False)
    event_type = Column(String(50), nullable=False)

    action = Column(SQLEnum(AuditAction), nullable=False)

    operator = Column(String(50), nullable=False)
    operator_ip = Column(INET, nullable=True)
    operator_role = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True)

    resource_type = Column(String(50), nullable=False)
    resource_id = Column(String(50), nullable=True)
    resource_name = Column(String(100), nullable=True)

    before_state = Column(JSONB, nullable=True)
    after_state = Column(JSONB, nullable=True)
    changes = Column(JSONB, nullable=True)
    details = Column(JSONB, nullable=True)

    result = Column(String(20))
    reason = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)

    model_id = Column(String(50), ForeignKey('model_metadata.model_id', ondelete='SET NULL'), nullable=True)
    model = relationship("ModelMetadata", back_populates="audit_logs")

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ABTestConfig(Base):
    """A/B测试配置表"""
    __tablename__ = 'ab_test_configs'
    __table_args__ = (
        Index('idx_abtest_status', 'status'),
        Index('idx_abtest_dates', 'start_date', 'end_date'),
        Index('idx_abtest_task_type', 'task_type'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), unique=True, nullable=False)
    test_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    task_type = Column(SQLEnum(TaskType), nullable=False)

    groups = Column(JSONB, nullable=False)

    traffic_allocation = Column(Float, default=100.0)
    assignment_strategy = Column(String(20), default='random')

    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)

    status = Column(SQLEnum(ABTestStatus), default=ABTestStatus.DRAFT)

    created_by = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    metrics = Column(JSONB, nullable=True)
    winning_criteria = Column(JSONB, nullable=True)

    results = Column(JSONB, nullable=True)
    winning_group = Column(String(50), nullable=True)

    assignments = relationship("ABTestAssignment", back_populates="test")


class ABTestAssignment(Base):
    """A/B测试分配记录表"""
    __tablename__ = 'ab_test_assignments'
    __table_args__ = (
        Index('idx_ab_assign_test_user', 'test_id', 'user_id'),
        Index('idx_ab_assign_time', 'assigned_at'),
        Index('idx_ab_assign_model', 'model_id'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    test_id = Column(String(50), ForeignKey('ab_test_configs.test_id', ondelete='CASCADE'), nullable=False)
    user_id = Column(String(50), nullable=False)
    group_name = Column(String(50), nullable=False)
    model_id = Column(String(50), ForeignKey('model_metadata.model_id', ondelete='CASCADE'), nullable=False)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assignment_hash = Column(String(64), nullable=True)

    expires_at = Column(DateTime(timezone=True), nullable=True)

    test = relationship("ABTestConfig", back_populates="assignments")
    model = relationship("ModelMetadata", back_populates="ab_test_assignments")


class SystemConfig(Base):
    """系统配置表"""
    __tablename__ = 'system_configs'
    __table_args__ = (
        Index('idx_config_key', 'config_key', unique=True),
        Index('idx_config_category', 'category'),
        {'schema': 'public'}
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False)
    config_value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)

    category = Column(String(50), nullable=True)
    is_encrypted = Column(Boolean, default=False)

    version = Column(Integer, default=1)

    updated_by = Column(String(50), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())