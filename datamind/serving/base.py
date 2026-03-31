# datamind/serving/base.py

"""BentoML 服务基类

提供模型加载、热更新、审计日志等基础功能。
"""

import atexit
import time
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from datamind.core.scoring.adapters import get_adapter
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.transform import WOETransformer
from datamind.core.scoring.predictor import Predictor
from datamind.core.scoring.capability import ScorecardCapability, has_capability
from datamind.core.db.database import get_db, db_manager
from datamind.core.db.models import ModelDeployment, ModelMetadata
from datamind.core.domain.enums import AuditAction, TaskType, ModelStatus, DeploymentEnvironment
from datamind.core.logging import log_audit, context
from datamind.core.logging.manager import LogManager
from datamind.config import get_settings

settings = get_settings()


class BaseBentoService:
    """
    BentoML 服务基类

    提供模型加载、热更新、审计日志等基础功能。
    """

    # 类级别锁，确保数据库只初始化一次
    _db_lock = threading.RLock()
    _db_initialized = False

    def __init__(self, service_type: str, service_name: str, debug: bool = False):
        """
        初始化服务

        参数:
            service_type: 服务类型 (scoring/fraud_detection)
            service_name: 服务名称
            debug: 是否启用调试日志
        """
        self.service_type = service_type
        self.service_name = service_name
        self._debug_enabled = debug
        self._task_type = TaskType.SCORING if service_type == 'scoring' else TaskType.FRAUD_DETECTION

        # 模型缓存
        self._active_models: Dict[str, Dict[str, Any]] = {}
        self._model_versions: Dict[str, str] = {}

        # 引擎缓存
        self._engines: Dict[str, ScoringEngine] = {}

        # 热加载线程控制
        self._hot_reload_thread: Optional[threading.Thread] = None
        self._stop_reload = threading.Event()
        self._reload_interval = 30

        # 初始化状态
        self._initialized = False

        # 获取日志器
        self._log_manager = LogManager()
        self.logger = self._log_manager.app_logger

        # 初始化数据库连接
        self._init_database()

        # 加载生产模型（异步，不阻塞启动）
        self._load_production_model_async()

        # 启动热加载监控
        self._start_hot_reload_monitor()

        # 注册退出清理
        atexit.register(self._cleanup)

        self._info("初始化完成, task_type=%s", self._task_type.value)

    def _debug(self, msg: str, *args) -> None:
        """调试输出"""
        if self._debug_enabled and self.logger:
            self.logger.debug(msg, *args)

    def _info(self, msg: str, *args) -> None:
        """信息输出"""
        if self.logger:
            self.logger.info(msg, *args)

    def _warning(self, msg: str, *args) -> None:
        """警告输出"""
        if self.logger:
            self.logger.warning(msg, *args)

    def _error(self, msg: str, *args) -> None:
        """错误输出"""
        if self.logger:
            self.logger.error(msg, *args)

    def _cleanup(self):
        """清理资源（由 atexit 调用）"""
        self._info("开始清理资源...")

        self._stop_reload.set()

        if self._hot_reload_thread and self._hot_reload_thread.is_alive():
            try:
                self._hot_reload_thread.join(timeout=2)
                if self._hot_reload_thread.is_alive():
                    self._warning("热加载线程未能在2秒内退出")
                else:
                    self._debug("热加载线程已退出")
            except Exception as e:
                self._error("等待热加载线程退出时出错: %s", e)

        for model_id in list(self._active_models.keys()):
            try:
                self._unload_model(model_id)
            except Exception as e:
                self._error("清理模型 %s 时出错: %s", model_id, e)

        self._info("资源清理完成")

    # ==================== 环境配置 ====================

    @staticmethod
    def _get_environment() -> str:
        """获取环境值"""
        env = settings.app.env
        if env == "production":
            return DeploymentEnvironment.PRODUCTION.value
        elif env == "staging":
            return DeploymentEnvironment.STAGING.value
        elif env == "testing":
            return DeploymentEnvironment.TESTING.value
        return DeploymentEnvironment.DEVELOPMENT.value

    # ==================== 数据库初始化 ====================

    def _init_database(self):
        """初始化数据库连接（线程安全）"""
        with self._db_lock:
            if not self._db_initialized:
                try:
                    self._debug("初始化数据库连接...")
                    db_manager.initialize()
                    self._db_initialized = True
                    self._info("数据库连接初始化成功")
                except Exception as e:
                    self._error("数据库连接初始化失败: %s", e)

    # ==================== 模型加载/卸载 ====================

    def _load_production_model_async(self):
        """异步加载生产模型（不阻塞服务启动）"""
        def load():
            time.sleep(2)
            try:
                self._load_production_model()
            except Exception as e:
                self._error("加载生产模型失败: %s", e)

        thread = threading.Thread(target=load, daemon=True, name=f"{self.service_name}_loader")
        thread.start()

    def _load_production_model(self):
        """加载生产环境模型"""
        if not self._db_initialized:
            self._debug("数据库未就绪，跳过生产模型加载")
            return

        try:
            env_value = self._get_environment()
            self._debug("环境: %s", env_value)

            with get_db() as session:
                deployment = session.query(ModelDeployment).filter(
                    ModelDeployment.environment == env_value,
                    ModelDeployment.is_active == True
                ).first()

                if deployment:
                    model_id = deployment.model_id
                    self._debug("找到部署配置: %s", model_id)

                    model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()

                    if model_info and model_info.status == ModelStatus.ACTIVE.value:
                        self._load_model(model_id)
                        self._initialized = True
                        self._info("加载生产模型成功: %s", model_id)
                    else:
                        self._warning("生产模型未激活: %s", model_id)
                else:
                    self._debug("未找到生产模型部署配置")

        except Exception as e:
            self._error("加载生产模型失败: %s", e)

    def _load_model(self, model_id: str) -> bool:
        """
        加载指定模型

        参数:
            model_id: 模型ID

        返回:
            是否加载成功
        """
        try:
            if model_id in self._active_models:
                self._debug("模型已加载: %s", model_id)
                return True

            with get_db() as session:
                model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model_info:
                    self._error("模型不存在: %s", model_id)
                    return False

                if model_info.task_type != self._task_type.value:
                    self._warning("模型类型不匹配: %s != %s",
                                  model_info.task_type, self._task_type.value)
                    return False

                # 加载模型文件
                import joblib
                import os

                model_path = model_info.file_path
                if not os.path.exists(model_path):
                    self._error("模型文件不存在: %s", model_path)
                    return False

                self._debug("加载模型文件: %s", model_path)
                model = joblib.load(model_path)

                # 获取特征名
                feature_names = model_info.input_features if hasattr(model_info, 'input_features') else None

                # 创建适配器
                adapter = get_adapter(model, feature_names=feature_names, debug=self._debug_enabled)

                # 创建评分引擎
                engine = ScoringEngine(
                    model_adapter=adapter,
                    transformer=None,
                    debug=self._debug_enabled
                )

                self._active_models[model_id] = {
                    'engine': engine,
                    'adapter': adapter,
                    'version': model_info.model_version,
                    'loaded_at': datetime.now(),
                    'metadata': {
                        'model_name': model_info.model_name,
                        'model_type': model_info.model_type,
                        'framework': model_info.framework,
                        'task_type': model_info.task_type
                    }
                }
                self._model_versions[model_id] = model_info.model_version
                self._engines[model_id] = engine

                self._info("模型加载成功: %s (version=%s)", model_id, model_info.model_version)
                return True

        except Exception as e:
            self._error("加载模型异常: %s, %s", model_id, e)
            return False

    def _unload_model(self, model_id: str):
        """卸载模型"""
        if model_id in self._active_models:
            del self._active_models[model_id]
            if model_id in self._engines:
                del self._engines[model_id]
            if model_id in self._model_versions:
                del self._model_versions[model_id]
            self._debug("模型卸载成功: %s", model_id)

    # ==================== 热加载监控 ====================

    def _start_hot_reload_monitor(self):
        """启动热加载监控线程"""
        def monitor():
            self._debug("热加载监控线程启动")
            env_value = self._get_environment()

            while not self._stop_reload.is_set():
                try:
                    if not self._db_initialized:
                        self._stop_reload.wait(self._reload_interval)
                        continue

                    with get_db() as session:
                        deployments = session.query(ModelDeployment).filter(
                            ModelDeployment.environment == env_value,
                            ModelDeployment.is_active == True
                        ).all()

                        for deployment in deployments:
                            model_id = deployment.model_id
                            model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                            if not model_info:
                                continue

                            current_version = self._model_versions.get(model_id)
                            latest_version = model_info.model_version

                            if latest_version and latest_version != current_version:
                                self._info("检测到模型版本更新: %s %s -> %s",
                                           model_id, current_version, latest_version)
                                self._unload_model(model_id)
                                self._load_model(model_id)

                                log_audit(
                                    action=AuditAction.MODEL_UPDATE.value,
                                    user_id="bentoml",
                                    details={
                                        "model_id": model_id,
                                        "old_version": current_version,
                                        "new_version": latest_version,
                                        "service": self.service_name,
                                        "action": "hot_reload"
                                    },
                                    request_id=context.get_request_id()
                                )

                except Exception as e:
                    self._error("热加载监控异常: %s", e)

                self._stop_reload.wait(self._reload_interval)

        self._hot_reload_thread = threading.Thread(
            target=monitor,
            daemon=True,
            name=f"{self.service_name}_reloader"
        )
        self._hot_reload_thread.start()

    # ==================== 公开接口 - 模型获取 ====================

    def get_production_model(self) -> Tuple[Optional[str], Optional[ScoringEngine], Optional[str]]:
        """
        获取生产模型

        返回:
            (model_id, engine, model_version) 元组，未找到返回 (None, None, None)
        """
        if not self._active_models:
            self._load_production_model()
            if not self._active_models:
                return None, None, None

        for mid, info in self._active_models.items():
            return mid, info['engine'], info['version']

        return None, None, None

    def get_model(self, model_id: str, auto_load: bool = True) -> Tuple[Optional[str], Optional[ScoringEngine], Optional[str]]:
        """
        根据模型ID获取模型

        参数:
            model_id: 模型ID
            auto_load: 如果模型未加载，是否自动加载

        返回:
            (model_id, engine, model_version) 元组，未找到返回 (None, None, None)
        """
        if model_id in self._active_models:
            info = self._active_models[model_id]
            return model_id, info['engine'], info['version']

        if auto_load:
            if self._load_model(model_id):
                info = self._active_models.get(model_id)
                if info:
                    return model_id, info['engine'], info['version']

        return None, None, None

    def get_loaded_model_ids(self) -> List[str]:
        """获取所有已加载的模型ID列表"""
        return list(self._active_models.keys())

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """获取已加载的模型列表"""
        return [
            {
                'model_id': mid,
                'model_name': info['metadata'].get('model_name'),
                'version': info['version'],
                'loaded_at': info['loaded_at'].isoformat(),
                'model_type': info['metadata'].get('model_type'),
                'framework': info['metadata'].get('framework'),
                'task_type': info['metadata'].get('task_type')
            }
            for mid, info in self._active_models.items()
        ]

    # ==================== 模型操作 ====================

    def reload_model(self, model_id: str) -> Dict[str, Any]:
        """手动重新加载模型"""
        try:
            self._info("手动重新加载模型: %s", model_id)
            self._unload_model(model_id)
            success = self._load_model(model_id)

            if success:
                return {
                    'success': True,
                    'message': f'模型 {model_id} 重新加载成功',
                    'model_id': model_id,
                    'version': self._model_versions.get(model_id)
                }
            else:
                return {
                    'success': False,
                    'message': f'模型 {model_id} 重新加载失败'
                }
        except Exception as e:
            self._error("重新加载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    def unload_model(self, model_id: str) -> Dict[str, Any]:
        """卸载模型"""
        try:
            if model_id not in self._active_models:
                return {
                    'success': False,
                    'message': f'模型 {model_id} 未加载'
                }
            self._unload_model(model_id)
            return {
                'success': True,
                'message': f'模型 {model_id} 卸载成功'
            }
        except Exception as e:
            self._error("卸载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    # ==================== 健康检查 ====================

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = 'healthy'
        issues = []

        if not self._db_initialized:
            status = 'degraded'
            issues.append('database_not_initialized')

        if not self._active_models:
            status = 'degraded'
            issues.append('no_models_loaded')

        for mid, info in self._active_models.items():
            if not info.get('engine'):
                status = 'unhealthy'
                issues.append(f'model_{mid}_invalid')

        return {
            'status': status,
            'service': self.service_name,
            'task_type': self._task_type.value,
            'loaded_models': len(self._active_models),
            'models': list(self._active_models.keys()),
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }

    def stop(self):
        """停止服务"""
        self._info("停止服务")
        self._stop_reload.set()

    def __del__(self):
        if hasattr(self, '_stop_reload'):
            self._stop_reload.set()