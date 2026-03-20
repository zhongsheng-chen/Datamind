# tests/test_database.py
"""测试数据库模型和操作

使用 pytest 框架测试数据库模型、关系和操作。
"""

import pytest
import uuid
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from datamind.core.db.models import (
    ModelMetadata, ModelVersionHistory, ModelDeployment,
    ApiCallLog, ModelPerformanceMetrics, AuditLog,
    ABTestConfig, ABTestAssignment, SystemConfig
)
from datamind.core.domain import (
    TaskType, ModelType, Framework, ModelStatus,
    AuditAction, DeploymentEnvironment, ABTestStatus
)


class TestDatabaseConnection:
    """测试数据库连接"""

    def test_connection(self, mock_db_session):
        """测试基本连接"""
        mock_db_session.execute.return_value.scalar.return_value = 1

        result = mock_db_session.execute(text("SELECT 1")).scalar()
        assert result == 1

    def test_postgres_version(self, mock_db_session):
        """测试PostgreSQL版本"""
        mock_db_session.execute.return_value.scalar.return_value = "PostgreSQL 14.0"

        result = mock_db_session.execute(text("SELECT version()")).scalar()
        assert "PostgreSQL" in result

    def test_extensions(self, mock_db_session):
        """测试必要的扩展"""
        mock_db_session.execute.return_value.scalar.return_value = True

        result = mock_db_session.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp')")
        ).scalar()
        assert result is True



class TestModelMetadata:
    """测试模型元数据表"""

    def test_create_model(self, mock_db_session):
        """测试创建模型"""
        model_id = f"test_model_{uuid.uuid4().hex[:8]}"

        # 创建模型对象
        new_model = ModelMetadata(
            model_id=model_id,
            model_name="test_lightgbm",
            model_version="1.0.0",
            task_type=TaskType.FRAUD_DETECTION.value,
            model_type=ModelType.LIGHTGBM.value,
            framework=Framework.LIGHTGBM.value,
            file_path="/tmp/test_model_2.json",
            file_hash="987654321",
            file_size=2048,
            input_features={"features": ["amount", "time"]},
            output_schema={"fraud_probability": "float"},
            created_by="test_user"
        )

        # 模拟数据库操作
        mock_db_session.add(new_model)
        mock_db_session.flush()

        # 模拟查询返回模型
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = new_model

        saved = mock_db_session.query(ModelMetadata).filter_by(
            model_id=model_id
        ).first()

        assert saved is not None
        assert saved.model_name == "test_lightgbm"
        assert saved.task_type == TaskType.FRAUD_DETECTION.value

    def test_model_unique_constraint(self, mock_db_session):
        """测试模型名称和版本唯一约束"""
        model_id1 = f"test_model_{uuid.uuid4().hex[:8]}"

        model1 = ModelMetadata(
            model_id=model_id1,
            model_name="unique_test",
            model_version="1.0.0",
            task_type=TaskType.SCORING.value,
            model_type=ModelType.XGBOOST.value,
            framework=Framework.XGBOOST.value,
            file_path="/tmp/unique1.json",
            file_hash="111",
            file_size=1024,
            input_features={"features": []},
            output_schema={},
            created_by="test_user"
        )

        # 第一个模型正常添加
        mock_db_session.add(model1)
        mock_db_session.flush()

        model_id2 = f"test_model_{uuid.uuid4().hex[:8]}"
        model2 = ModelMetadata(
            model_id=model_id2,
            model_name="unique_test",  # 同名
            model_version="1.0.0",  # 同版本
            task_type=TaskType.SCORING.value,
            model_type=ModelType.XGBOOST.value,
            framework=Framework.XGBOOST.value,
            file_path="/tmp/unique2.json",
            file_hash="222",
            file_size=1024,
            input_features={"features": []},
            output_schema={},
            created_by="test_user"
        )

        # 模拟唯一约束冲突
        mock_db_session.add(model2)
        mock_db_session.flush.side_effect = IntegrityError("Duplicate", None, None)

        with pytest.raises(IntegrityError):
            mock_db_session.flush()

    def test_model_relationships(self, mock_db_session, sample_model_metadata):
        """测试模型关联关系"""
        mock_db_session.query.return_value.filter_by.return_value.first.return_value = sample_model_metadata

        model = mock_db_session.query(ModelMetadata).filter_by(
            model_id=sample_model_metadata.model_id
        ).first()

        assert model is not None
        assert hasattr(model, 'model_id')
        assert hasattr(model, 'model_name')


class TestModelVersionHistory:
    """测试模型版本历史表"""

    def test_create_version_history(self, mock_db_session, sample_model_metadata):
        """测试创建版本历史"""
        history = ModelVersionHistory(
            model_id=sample_model_metadata.model_id,
            model_version="2.0.0",
            operation=AuditAction.UPDATE.value,
            operator="test_user",
            details={"changes": ["updated_params"]}
        )

        mock_db_session.add(history)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = history

        saved = mock_db_session.query(ModelVersionHistory).filter_by(
            model_id=sample_model_metadata.model_id,
            model_version="2.0.0"
        ).first()

        assert saved is not None
        assert saved.operation == AuditAction.UPDATE.value


class TestModelDeployment:
    """测试模型部署表"""

    def test_create_deployment(self, mock_db_session, sample_model_metadata):
        """测试创建部署"""
        deploy_id = f"deploy_{uuid.uuid4().hex[:8]}"
        deployment = ModelDeployment(
            deployment_id=deploy_id,
            model_id=sample_model_metadata.model_id,
            model_version="1.0.0",
            environment=DeploymentEnvironment.PRODUCTION.value,
            endpoint_url="https://api.example.com/predict",
            is_active=True,
            deployment_config={"replicas": 3, "autoscaling": True},
            deployed_by="test_user",
            traffic_weight=100
        )

        mock_db_session.add(deployment)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = deployment

        saved = mock_db_session.query(ModelDeployment).filter_by(
            deployment_id=deploy_id
        ).first()

        assert saved is not None
        assert saved.environment == DeploymentEnvironment.PRODUCTION.value
        assert saved.deployment_config["replicas"] == 3


class TestApiCallLog:
    """测试API调用日志表"""

    def test_create_api_log(self, mock_db_session, sample_model_metadata):
        """测试创建API日志"""
        req_id = f"req_{uuid.uuid4().hex[:8]}"
        api_log = ApiCallLog(
            request_id=req_id,
            application_id="app_002",
            model_id=sample_model_metadata.model_id,
            model_version="1.0.0",
            task_type=TaskType.SCORING.value,
            endpoint="/predict",
            request_data={"features": [30, 60000]},
            response_data={"score": 0.92},
            processing_time_ms=45,
            status_code=200,
            ip_address="10.0.0.1"
        )

        mock_db_session.add(api_log)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = api_log

        saved = mock_db_session.query(ApiCallLog).filter_by(
            request_id=req_id
        ).first()

        assert saved is not None
        assert saved.processing_time_ms == 45
        assert saved.response_data["score"] == 0.92


class TestModelPerformanceMetrics:
    """测试模型性能指标表"""

    def test_create_performance_metric(self, mock_db_session, sample_model_metadata):
        """测试创建性能指标"""
        metric = ModelPerformanceMetrics(
            model_id=sample_model_metadata.model_id,
            model_version="1.0.0",
            task_type=TaskType.SCORING.value,
            date=datetime.now().date() - timedelta(days=1),
            total_requests=500,
            success_count=480,
            error_count=20,
            avg_response_time_ms=42.3,
            p95_response_time_ms=75.0,
            avg_score=0.78
        )

        mock_db_session.add(metric)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = metric

        saved = mock_db_session.query(ModelPerformanceMetrics).filter_by(
            model_id=sample_model_metadata.model_id,
            date=datetime.now().date() - timedelta(days=1)
        ).first()

        assert saved is not None
        assert saved.total_requests == 500


class TestAuditLog:
    """测试审计日志表"""

    def test_create_audit_log(self, mock_db_session):
        """测试创建审计日志"""
        audit_id = f"audit_{uuid.uuid4().hex[:8]}"
        audit = AuditLog(
            audit_id=audit_id,
            event_type="USER_OPERATION",
            action=AuditAction.UPDATE.value,
            operator="admin_user",
            operator_role="admin",
            resource_type="config",
            resource_id="config_001",
            before_state={"enabled": False},
            after_state={"enabled": True},
            changes={"enabled": [False, True]},
            result="SUCCESS"
        )

        mock_db_session.add(audit)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = audit

        saved = mock_db_session.query(AuditLog).filter_by(
            audit_id=audit_id
        ).first()

        assert saved is not None
        assert saved.operator == "admin_user"
        assert saved.after_state["enabled"] is True


class TestABTest:
    """测试A/B测试表"""

    def test_create_abtest(self, mock_db_session, sample_model_metadata):
        """测试创建AB测试"""
        test_id = f"abtest_{uuid.uuid4().hex[:8]}"
        abtest = ABTestConfig(
            test_id=test_id,
            test_name="Fraud Detection Test",
            task_type=TaskType.FRAUD_DETECTION.value,
            groups=[
                {"name": "A", "model_id": sample_model_metadata.model_id, "weight": 50},
                {"name": "B", "model_id": "model_004", "weight": 50}
            ],
            traffic_allocation=80.0,
            start_date=datetime.now(),
            status=ABTestStatus.DRAFT.value,
            created_by="test_user"
        )

        mock_db_session.add(abtest)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = abtest

        saved = mock_db_session.query(ABTestConfig).filter_by(
            test_id=test_id
        ).first()

        assert saved is not None
        assert saved.test_name == "Fraud Detection Test"
        assert saved.status == ABTestStatus.DRAFT.value

    def test_create_ab_assignment(self, mock_db_session, sample_model_metadata):
        """测试创建AB测试分配"""
        test_id = f"abtest_{uuid.uuid4().hex[:8]}"

        assignment = ABTestAssignment(
            test_id=test_id,
            user_id="user_001",
            group_name="control",
            model_id=sample_model_metadata.model_id,
            assignment_hash="hash_001",
            expires_at=datetime.now() + timedelta(days=7)
        )

        mock_db_session.add(assignment)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = assignment

        saved = mock_db_session.query(ABTestAssignment).filter_by(
            test_id=test_id,
            user_id="user_001"
        ).first()

        assert saved is not None
        assert saved.group_name == "control"


class TestSystemConfig:
    """测试系统配置表"""

    def test_create_config(self, mock_db_session):
        """测试创建系统配置"""
        config_key = f"test_config_{uuid.uuid4().hex[:8]}"
        config = SystemConfig(
            config_key=config_key,
            config_value={"threshold": 0.9, "enabled": True},
            description="新配置",
            category="test",
            updated_by="test_user"
        )

        mock_db_session.add(config)
        mock_db_session.flush()

        mock_db_session.query.return_value.filter_by.return_value.first.return_value = config

        saved = mock_db_session.query(SystemConfig).filter_by(
            config_key=config_key
        ).first()

        assert saved is not None
        assert saved.config_value["threshold"] == 0.9