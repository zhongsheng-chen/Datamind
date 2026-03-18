# tests/test_database.py

import os
import unittest
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from datamind.core.db import db_manager, Base
from datamind.core.db.models import (
    ModelMetadata, ModelVersionHistory, ModelDeployment,
    ApiCallLog, ModelPerformanceMetrics, AuditLog,
    ABTestConfig, ABTestAssignment, SystemConfig
)

from datamind.core.domain import (
    TaskType, ModelType, Framework, ModelStatus,
    AuditAction, DeploymentEnvironment, ABTestStatus
)

from datamind.core.logging import log_manager
from datamind.config import get_settings


class TestDatabaseBase(unittest.TestCase):
    """PostgreSQL数据库测试基类"""

    # 调试开关：控制是否打印信息，默认为 False（不打印调试）
    PRINT_DEBUG = os.getenv("DB_TEST_DEBUG", "false").lower() == "true"

    @classmethod
    def setUpClass(cls):
        """测试类初始化，创建测试数据库"""
        # 从配置获取数据库URL，但修改为测试数据库
        settings = get_settings()
        base_url = settings.database.url

        # 解析URL并创建测试数据库URL
        if 'postgresql' in base_url:
            # 假设原始URL: postgresql://user:pass@host:port/datamind
            # 测试数据库: postgresql://user:pass@host:port/datamind_test
            if base_url.endswith('/'):
                cls.test_db_url = base_url + "datamind_test"
            else:
                # 替换最后的数据库名
                parts = base_url.rsplit('/', 1)
                if len(parts) == 2:
                    cls.test_db_url = parts[0] + "/datamind_test"
                else:
                    cls.test_db_url = base_url + "_test"
        else:
            # 默认测试数据库
            cls.test_db_url = "postgresql://postgres:postgres@localhost:5432/datamind_test"

        if cls.PRINT_DEBUG:
            print(f"\n测试数据库URL: {cls.test_db_url}")

        # 创建测试数据库（如果不存在）
        cls._create_test_database()

        # 创建引擎和会话
        cls.engine = create_engine(
            cls.test_db_url,
            poolclass=NullPool,  # 测试时使用NullPool避免连接池问题
            echo=False  # 设置为True可以查看SQL语句
        )

        # 创建所有表
        Base.metadata.create_all(cls.engine)

        # 创建会话工厂
        cls.Session = sessionmaker(bind=cls.engine)

        # 初始化日志管理器
        if not hasattr(log_manager, '_initialized') or not log_manager._initialized:
            from datamind.config import LoggingConfig, LogLevel
            config = LoggingConfig(level=LogLevel.ERROR)
            log_manager.initialize(config)

        if cls.PRINT_DEBUG:
            print("测试数据库初始化完成")

    @classmethod
    def _create_test_database(cls):
        """创建测试数据库"""
        # 连接到默认数据库（postgres）
        default_url = cls.test_db_url.replace('/datamind_test', '/postgres')
        try:
            engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
            with engine.connect() as conn:
                # 检查数据库是否已存在
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = 'datamind_test'")
                ).first()

                if not result:
                    conn.execute(text("CREATE DATABASE datamind_test"))
                    if cls.PRINT_DEBUG:
                        print("创建测试数据库: datamind_test")
                else:
                    if cls.PRINT_DEBUG:
                        print("测试数据库已存在: datamind_test")

            engine.dispose()

        except Exception as e:
            if cls.PRINT_DEBUG:
                print(f"创建测试数据库失败: {e}")
                print("将使用现有数据库继续测试...")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        # 关闭所有连接
        cls.engine.dispose()

        # 删除开关：控制是否删除测试数据库，默认为 True（删除）
        DROP_DATABASE = os.getenv("DROP_TEST_DATABASE", "true").lower() == "true"

        if DROP_DATABASE:
            cls._drop_test_database()
            if cls.PRINT_DEBUG:
                print("测试数据库已删除")
        else:
            if cls.PRINT_DEBUG:
                print("测试数据库连接已关闭（数据库已保留）")

    @classmethod
    def _drop_test_database(cls):
        """删除测试数据库"""
        # 连接到默认数据库
        default_url = cls.test_db_url.replace('/datamind_test', '/postgres')
        try:
            engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
            with engine.connect() as conn:
                # 终止所有连接到测试数据库的连接
                conn.execute(text("""
                                  SELECT pg_terminate_backend(pid)
                                  FROM pg_stat_activity
                                  WHERE datname = 'datamind_test'
                                  """))

                # 删除数据库
                conn.execute(text("DROP DATABASE IF EXISTS datamind_test"))
                if cls.PRINT_DEBUG:
                    print("删除测试数据库: datamind_test")

            engine.dispose()

        except Exception as e:
            if cls.PRINT_DEBUG:
                print(f"删除测试数据库失败: {e}")

    def setUp(self):
        """每个测试前的准备工作"""
        # 直接创建会话，让 SQLAlchemy 自己管理事务
        self.session = self.Session()

        # 插入基础测试数据
        self._insert_test_data()

    def tearDown(self):
        """每个测试后的清理工作"""
        # 回滚事务（确保测试隔离）
        self.session.rollback()
        self.session.close()

    def _insert_test_data(self):
        """插入基础测试数据"""
        # 生成唯一ID
        model_uuid = str(uuid.uuid4())[:8]

        # 创建测试模型
        self.test_model = ModelMetadata(
            model_id=f"test_model_{model_uuid}",
            model_name="test_xgboost",
            model_version="1.0.0",
            task_type=TaskType.SCORING,
            model_type=ModelType.XGBOOST,
            framework=Framework.XGBOOST,
            file_path="/tmp/test_model.json",
            file_hash="abcdef1234567890",
            file_size=1024,
            input_features={"features": ["age", "income"]},
            output_schema={"score": "float"},
            model_params={"learning_rate": 0.1},
            feature_importance={"age": 0.3, "income": 0.7},
            performance_metrics={"accuracy": 0.95},
            status=ModelStatus.ACTIVE,
            is_production=True,
            created_by="test_user",
            description="测试模型",
            tags={"department": "risk"}
        )
        self.session.add(self.test_model)
        self.session.flush()  # 确保 model_id 生成

        # 创建版本历史
        self.test_history = ModelVersionHistory(
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            operation=AuditAction.CREATE,
            operator="test_user",
            operator_ip="127.0.0.1",
            reason="初始创建",
            details={"action": "model_creation"}
        )
        self.session.add(self.test_history)

        # 创建部署记录
        deploy_uuid = str(uuid.uuid4())[:8]
        self.test_deployment = ModelDeployment(
            deployment_id=f"deploy_{deploy_uuid}",
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            environment=DeploymentEnvironment.TESTING,
            endpoint_url="http://localhost:8000/predict",
            is_active=True,
            deployment_config={"replicas": 1},
            resources={"cpu": "1", "memory": "1Gi"},
            deployed_by="test_user",
            traffic_weight=100
        )
        self.session.add(self.test_deployment)

        # 创建审计日志
        audit_uuid = str(uuid.uuid4())[:8]
        self.test_audit = AuditLog(
            audit_id=f"audit_{audit_uuid}",
            event_type="MODEL_OPERATION",
            action=AuditAction.CREATE,
            operator="test_user",
            operator_ip="127.0.0.1",
            operator_role="admin",
            resource_type="model",
            resource_id=self.test_model.model_id,
            resource_name=self.test_model.model_name,
            details={"version": "1.0.0"},
            result="SUCCESS",
            model_id=self.test_model.model_id
        )
        self.session.add(self.test_audit)

        # 创建性能指标
        self.test_performance = ModelPerformanceMetrics(
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            task_type=TaskType.SCORING,
            date=datetime.now().date(),
            total_requests=1000,
            success_count=950,
            error_count=50,
            avg_response_time_ms=45.5,
            p50_response_time_ms=40.0,
            p95_response_time_ms=80.0,
            p99_response_time_ms=120.0,
            avg_score=0.75,
            score_distribution={"0-0.5": 100, "0.5-1.0": 900}
        )
        self.session.add(self.test_performance)

        # 创建AB测试配置
        ab_uuid = str(uuid.uuid4())[:8]
        self.test_abtest = ABTestConfig(
            test_id=f"abtest_{ab_uuid}",
            test_name="Score Model Test",
            description="测试新评分模型",
            task_type=TaskType.SCORING,
            groups=[
                {"name": "control", "model_id": self.test_model.model_id, "weight": 50},
                {"name": "treatment", "model_id": "model_002", "weight": 50}
            ],
            traffic_allocation=100.0,
            assignment_strategy="random",
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=30),
            status=ABTestStatus.RUNNING,
            created_by="test_user",
            metrics=["accuracy", "latency"],
            winning_criteria={"accuracy": ">0.95"}
        )
        self.session.add(self.test_abtest)
        self.session.flush()  # 确保 test_id 生成

        # 创建AB测试分配
        self.test_ab_assignment = ABTestAssignment(
            test_id=self.test_abtest.test_id,
            user_id="user_001",
            group_name="control",
            model_id=self.test_model.model_id,
            assignment_hash="hash_001",
            expires_at=datetime.now() + timedelta(days=7)
        )
        self.session.add(self.test_ab_assignment)

        # 创建系统配置
        config_uuid = str(uuid.uuid4())[:8]
        self.test_config = SystemConfig(
            config_key=f"test_config_{config_uuid}",
            config_value={"enabled": True, "threshold": 0.8},
            description="测试配置",
            category="test",
            is_encrypted=False,
            version=1,
            updated_by="test_user"
        )
        self.session.add(self.test_config)

        self.session.flush()


class TestDatabaseConnection(TestDatabaseBase):
    """测试数据库连接"""

    def test_connection(self):
        """测试基本连接"""
        result = self.session.execute(text("SELECT 1")).scalar()
        self.assertEqual(result, 1)

    def test_postgres_version(self):
        """测试PostgreSQL版本"""
        result = self.session.execute(text("SELECT version()")).scalar()
        self.assertIn("PostgreSQL", result)
        if self.PRINT_DEBUG:
            print(f"\nPostgreSQL版本: {result[:50]}...")

    def test_extensions(self):
        """测试必要的扩展"""
        # 检查 uuid-ossp 扩展
        result = self.session.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp')")
        ).scalar()
        status = "存在" if result else "不存在"
        if self.PRINT_DEBUG:
            print(f"uuid-ossp扩展: {status}")


class TestModelMetadata(TestDatabaseBase):
    """测试模型元数据表"""

    def test_create_model(self):
        """测试创建模型"""
        model_id = f"test_model_{uuid.uuid4()}"
        new_model = ModelMetadata(
            model_id=model_id,
            model_name="test_lightgbm",
            model_version="1.0.0",
            task_type=TaskType.FRAUD_DETECTION,
            model_type=ModelType.LIGHTGBM,
            framework=Framework.LIGHTGBM,
            file_path="/tmp/test_model_2.json",
            file_hash="987654321",
            file_size=2048,
            input_features={"features": ["amount", "time"]},
            output_schema={"fraud_probability": "float"},
            created_by="test_user"
        )
        self.session.add(new_model)
        self.session.flush()

        # 验证
        saved_model = self.session.query(ModelMetadata).filter_by(
            model_id=model_id
        ).first()
        self.assertIsNotNone(saved_model)
        self.assertEqual(saved_model.model_name, "test_lightgbm")
        self.assertEqual(saved_model.task_type, TaskType.FRAUD_DETECTION)

    def test_model_unique_constraint(self):
        """测试模型名称和版本唯一约束"""
        # 创建两个同名的模型
        model1 = ModelMetadata(
            model_id=f"test_model_{uuid.uuid4()}",
            model_name="unique_test",
            model_version="1.0.0",
            task_type=TaskType.SCORING,
            model_type=ModelType.XGBOOST,
            framework=Framework.XGBOOST,
            file_path="/tmp/unique1.json",
            file_hash="111",
            file_size=1024,
            input_features={"features": []},
            output_schema={},
            created_by="test_user"
        )
        self.session.add(model1)
        self.session.flush()

        # 创建第二个同名同版本的模型
        model2 = ModelMetadata(
            model_id=f"test_model_{uuid.uuid4()}",
            model_name="unique_test",  # 同名
            model_version="1.0.0",  # 同版本
            task_type=TaskType.SCORING,
            model_type=ModelType.XGBOOST,
            framework=Framework.XGBOOST,
            file_path="/tmp/unique2.json",
            file_hash="222",
            file_size=1024,
            input_features={"features": []},
            output_schema={},
            created_by="test_user"
        )
        self.session.add(model2)

        # 应该抛出唯一约束异常
        with self.assertRaises(IntegrityError):
            self.session.flush()


    def test_model_relationships(self):
        """测试模型关联关系"""
        model = self.session.query(ModelMetadata).filter_by(
            model_id=self.test_model.model_id
        ).first()

        # 验证版本历史
        self.assertGreaterEqual(len(model.versions), 1)

        # 验证部署记录
        self.assertGreaterEqual(len(model.deployments), 1)

        # 验证审计日志
        self.assertGreaterEqual(len(model.audit_logs), 1)

        # 验证性能记录
        self.assertGreaterEqual(len(model.performance_records), 1)


class TestModelVersionHistory(TestDatabaseBase):
    """测试模型版本历史表"""

    def test_create_version_history(self):
        """测试创建版本历史"""
        history = ModelVersionHistory(
            model_id=self.test_model.model_id,
            model_version="2.0.0",
            operation=AuditAction.UPDATE,
            operator="test_user",
            details={"changes": ["updated_params"]}
        )
        self.session.add(history)
        self.session.flush()

        saved = self.session.query(ModelVersionHistory).filter_by(
            model_id=self.test_model.model_id,
            model_version="2.0.0"
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.operation, AuditAction.UPDATE)


class TestModelDeployment(TestDatabaseBase):
    """测试模型部署表"""

    def test_create_deployment(self):
        """测试创建部署"""
        deploy_id = f"deploy_{uuid.uuid4()}"
        deployment = ModelDeployment(
            deployment_id=deploy_id,
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            environment=DeploymentEnvironment.PRODUCTION,
            endpoint_url="https://api.example.com/predict",
            is_active=True,
            deployment_config={"replicas": 3, "autoscaling": True},
            deployed_by="test_user",
            traffic_weight=100
        )
        self.session.add(deployment)
        self.session.flush()

        saved = self.session.query(ModelDeployment).filter_by(
            deployment_id=deploy_id
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.environment, DeploymentEnvironment.PRODUCTION)
        self.assertEqual(saved.deployment_config["replicas"], 3)


class TestApiCallLog(TestDatabaseBase):
    """测试API调用日志表"""

    def test_create_api_log(self):
        """测试创建API日志"""
        req_id = f"req_{uuid.uuid4()}"
        api_log = ApiCallLog(
            request_id=req_id,
            application_id="app_002",
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            task_type=TaskType.SCORING,
            endpoint="/predict",
            request_data={"features": [30, 60000]},
            response_data={"score": 0.92},
            processing_time_ms=45,
            status_code=200,
            ip_address="10.0.0.1"
        )
        self.session.add(api_log)
        self.session.flush()

        saved = self.session.query(ApiCallLog).filter_by(
            request_id=req_id
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.processing_time_ms, 45)
        self.assertEqual(saved.response_data["score"], 0.92)

    def test_jsonb_query(self):
        """测试JSONB字段查询"""
        # 添加一些测试数据
        for i in range(3):
            log = ApiCallLog(
                request_id=f"json_test_{i}",
                application_id="json_test_app",
                model_id=self.test_model.model_id,
                model_version="1.0.0",
                task_type=TaskType.SCORING,
                endpoint="/predict",
                request_data={"test_id": i, "value": i * 10},
                response_data={"result": i * 2},
                processing_time_ms=10,
                status_code=200
            )
            self.session.add(log)
        self.session.flush()

        # 使用PostgreSQL的JSONB查询
        logs = self.session.execute(
            text("""
                 SELECT *
                 FROM api_call_logs
                 WHERE request_data ->> 'test_id' = '1'
                 """)
        ).fetchall()

        self.assertGreaterEqual(len(logs), 1)


class TestModelPerformanceMetrics(TestDatabaseBase):
    """测试模型性能指标表"""

    def test_create_performance_metric(self):
        """测试创建性能指标"""
        metric = ModelPerformanceMetrics(
            model_id=self.test_model.model_id,
            model_version="1.0.0",
            task_type=TaskType.SCORING,
            date=datetime.now().date() - timedelta(days=1),
            total_requests=500,
            success_count=480,
            error_count=20,
            avg_response_time_ms=42.3,
            p95_response_time_ms=75.0,
            avg_score=0.78
        )
        self.session.add(metric)
        self.session.flush()

        saved = self.session.query(ModelPerformanceMetrics).filter_by(
            model_id=self.test_model.model_id,
            date=datetime.now().date() - timedelta(days=1)
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.total_requests, 500)


class TestAuditLog(TestDatabaseBase):
    """测试审计日志表"""

    def test_create_audit_log(self):
        """测试创建审计日志"""
        audit_id = f"audit_{uuid.uuid4()}"
        audit = AuditLog(
            audit_id=audit_id,
            event_type="USER_OPERATION",
            action=AuditAction.UPDATE,
            operator="admin_user",
            operator_role="admin",
            resource_type="config",
            resource_id="config_001",
            before_state={"enabled": False},
            after_state={"enabled": True},
            changes={"enabled": [False, True]},
            result="SUCCESS"
        )
        self.session.add(audit)
        self.session.flush()

        saved = self.session.query(AuditLog).filter_by(
            audit_id=audit_id
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.operator, "admin_user")
        self.assertEqual(saved.after_state["enabled"], True)


class TestABTest(TestDatabaseBase):
    """测试A/B测试表"""

    def test_create_abtest(self):
        """测试创建AB测试"""
        test_id = f"abtest_{uuid.uuid4()}"
        abtest = ABTestConfig(
            test_id=test_id,
            test_name="Fraud Detection Test",
            task_type=TaskType.FRAUD_DETECTION,
            groups=[
                {"name": "A", "model_id": self.test_model.model_id, "weight": 50},
                {"name": "B", "model_id": "model_004", "weight": 50}
            ],
            traffic_allocation=80.0,
            start_date=datetime.now(),
            status=ABTestStatus.DRAFT,
            created_by="test_user"
        )
        self.session.add(abtest)
        self.session.flush()

        saved = self.session.query(ABTestConfig).filter_by(
            test_id=test_id
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.test_name, "Fraud Detection Test")
        self.assertEqual(saved.status, ABTestStatus.DRAFT)


class TestSystemConfig(TestDatabaseBase):
    """测试系统配置表"""

    def test_create_config(self):
        """测试创建系统配置"""
        config_key = f"test_config_{uuid.uuid4()}"
        config = SystemConfig(
            config_key=config_key,
            config_value={"threshold": 0.9, "enabled": True},
            description="新配置",
            category="test",
            updated_by="test_user"
        )
        self.session.add(config)
        self.session.flush()

        saved = self.session.query(SystemConfig).filter_by(
            config_key=config_key
        ).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.config_value["threshold"], 0.9)


class TestDatabaseManager(TestDatabaseBase):
    """测试数据库管理器"""

    def setUp(self):
        """每个测试前的准备工作"""
        super().setUp()
        # 初始化 db_manager
        if not hasattr(db_manager, '_initialized') or not db_manager._initialized:
            db_manager.initialize(
                database_url=self.test_db_url,
                pool_size=5,
                max_overflow=10
            )

    def tearDown(self):
        """每个测试后的清理工作"""
        super().tearDown()
        # 清理 db_manager 状态
        if hasattr(db_manager, '_initialized') and db_manager._initialized:
            db_manager._initialized = False
            db_manager._engines = {}
            db_manager._session_factories = {}
            db_manager._scoped_sessions = {}

    def test_health_check(self):
        """测试健康检查"""
        with db_manager.session_scope() as session:
            result = session.execute(text("SELECT 1")).scalar()
            self.assertEqual(result, 1)

        # 测试健康检查方法
        health = db_manager.check_health()
        self.assertIn('status', health)
        self.assertIn('engines', health)


class TestEnums(TestDatabaseBase):
    """测试枚举类型"""

    def test_task_type_values(self):
        """测试任务类型枚举"""
        self.assertEqual(TaskType.SCORING.value, "scoring")
        self.assertEqual(TaskType.FRAUD_DETECTION.value, "fraud_detection")

    def test_model_type_values(self):
        """测试模型类型枚举"""
        self.assertEqual(ModelType.XGBOOST.value, "xgboost")
        self.assertEqual(ModelType.LIGHTGBM.value, "lightgbm")

    def test_framework_compatibility(self):
        """测试框架兼容性"""
        from datamind.core.domain import is_compatible, get_supported_models, get_supported_frameworks

        # XGBoost框架应该兼容XGBoost模型
        self.assertTrue(
            is_compatible(Framework.XGBOOST, ModelType.XGBOOST)
        )

        # XGBoost框架不应该兼容LightGBM模型
        self.assertFalse(
            is_compatible(Framework.XGBOOST, ModelType.LIGHTGBM)
        )

        # 测试获取支持的模型
        supported_models = get_supported_models(Framework.TORCH)
        self.assertIn(ModelType.NEURAL_NETWORK, supported_models)
        self.assertIn(ModelType.LOGISTIC_REGRESSION, supported_models)

        # 测试获取支持的框架
        supported_frameworks = get_supported_frameworks(ModelType.NEURAL_NETWORK)
        self.assertIn(Framework.TORCH, supported_frameworks)
        self.assertIn(Framework.TENSORFLOW, supported_frameworks)
        self.assertIn(Framework.ONNX, supported_frameworks)

    def test_validate_or_raise(self):
        """测试验证并抛出异常"""
        from datamind.core.domain import validate_or_raise

        # 兼容的情况，不应该抛出异常
        try:
            validate_or_raise(Framework.XGBOOST, ModelType.XGBOOST)
        except ValueError:
            self.fail("validate_or_raise() 对兼容的组合抛出了异常")

        # 不兼容的情况，应该抛出异常
        with self.assertRaises(ValueError) as context:
            validate_or_raise(Framework.XGBOOST, ModelType.LIGHTGBM)

        # 验证异常信息
        self.assertIn("不支持模型类型", str(context.exception))
        self.assertIn("xgboost", str(context.exception))
        self.assertIn("lightgbm", str(context.exception))

    def test_compatibility_mapping(self):
        """测试兼容性映射常量"""
        from datamind.core.domain import FRAMEWORK_MODEL_COMPATIBILITY

        # 验证映射不为空
        self.assertGreater(len(FRAMEWORK_MODEL_COMPATIBILITY), 0)

        # 验证 ONNX 支持多种模型
        onnx_models = FRAMEWORK_MODEL_COMPATIBILITY[Framework.ONNX]
        self.assertIn(ModelType.XGBOOST, onnx_models)
        self.assertIn(ModelType.NEURAL_NETWORK, onnx_models)
        self.assertIn(ModelType.DECISION_TREE, onnx_models)


if __name__ == "__main__":
    unittest.main(verbosity=2)