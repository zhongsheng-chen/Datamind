# datamind/serving/base.py (最终版)

import atexit
import time
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from datamind.core.ml.model_loader import get_model_loader
from datamind.core.ml.model_registry import get_model_registry
from datamind.core.ml.inference import get_inference_engine
from datamind.core.db.database import get_db, db_manager
from datamind.core.db.models import ModelDeployment
from datamind.core.domain.enums import AuditAction, TaskType, ModelStatus, DeploymentEnvironment
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
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

    def __init__(self, service_type: str, service_name: str):
        """
        初始化服务

        参数:
            service_type: 服务类型 (scoring/fraud_detection)
            service_name: 服务名称
        """
        self.service_type = service_type
        self.service_name = service_name
        self._task_type = TaskType.SCORING if service_type == 'scoring' else TaskType.FRAUD_DETECTION

        # 模型缓存
        self._active_models: Dict[str, Dict[str, Any]] = {}
        self._model_versions: Dict[str, str] = {}

        # 热加载线程控制
        self._hot_reload_thread: Optional[threading.Thread] = None
        self._stop_reload = threading.Event()
        self._reload_interval = 30

        # 初始化状态
        self._initialized = False

        # 获取组件实例（延迟初始化）
        self._model_loader = None
        self._model_registry = None
        self._inference_engine = None

        # 初始化数据库连接
        self._init_database()

        # 加载生产模型（异步，不阻塞启动）
        self._load_production_model_async()

        # 启动热加载监控
        self._start_hot_reload_monitor()

        # 注册退出清理
        atexit.register(self._cleanup)

        debug_print(self.service_name, f"初始化完成, task_type={self._task_type.value}")

    def _cleanup(self):
        """
        清理资源（由 atexit 调用）

        注意：清理过程中记录异常但不抛出，避免影响程序退出。
        """
        debug_print(self.service_name, "开始清理资源...")

        # 停止热加载监控
        self._stop_reload.set()

        # 等待热加载线程退出
        if self._hot_reload_thread and self._hot_reload_thread.is_alive():
            try:
                self._hot_reload_thread.join(timeout=2)
                if self._hot_reload_thread.is_alive():
                    debug_print(self.service_name, "热加载线程未能在2秒内退出")
                else:
                    debug_print(self.service_name, "热加载线程已退出")
            except Exception as e:
                debug_print(self.service_name, f"等待热加载线程退出时出错: {e}")

        # 清理已加载的模型
        for model_id in list(self._active_models.keys()):
            try:
                self._unload_model(model_id)
            except Exception as e:
                debug_print(self.service_name, f"清理模型 {model_id} 时出错: {e}")

        debug_print(self.service_name, "资源清理完成")

    # ==================== 延迟加载组件 ====================

    def _get_model_loader(self):
        """延迟获取模型加载器"""
        if self._model_loader is None:
            self._model_loader = get_model_loader()
        return self._model_loader

    def _get_model_registry(self):
        """延迟获取模型注册中心"""
        if self._model_registry is None:
            self._model_registry = get_model_registry()
        return self._model_registry

    def _get_inference_engine(self):
        """延迟获取推理引擎"""
        if self._inference_engine is None:
            self._inference_engine = get_inference_engine()
        return self._inference_engine

    # ==================== 环境配置 ====================

    @staticmethod
    def _get_environment() -> str:
        """
        获取环境值

        返回:
            环境字符串 (development/testing/staging/production)
        """
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
                    debug_print(self.service_name, "初始化数据库连接...")
                    db_manager.initialize()
                    self._db_initialized = True
                    debug_print(self.service_name, "数据库连接初始化成功")
                except Exception as e:
                    debug_print(self.service_name, f"数据库连接初始化失败: {e}")

    # ==================== 模型加载/卸载 ====================

    def _load_production_model_async(self):
        """异步加载生产模型（不阻塞服务启动）"""

        def load():
            time.sleep(2)
            try:
                self._load_production_model()
            except Exception as e:
                debug_print(self.service_name, f"加载生产模型失败: {e}")

        thread = threading.Thread(target=load, daemon=True, name=f"{self.service_name}_loader")
        thread.start()

    def _load_production_model(self):
        """加载生产环境模型"""
        if not self._db_initialized:
            debug_print(self.service_name, "数据库未就绪，跳过生产模型加载")
            return

        try:
            env_value = self._get_environment()
            debug_print(self.service_name, f"环境: {env_value}")

            with get_db() as session:
                deployment = session.query(ModelDeployment).filter(
                    ModelDeployment.environment == env_value,
                    ModelDeployment.is_active == True
                ).first()

                if deployment:
                    model_id = deployment.model_id
                    debug_print(self.service_name, f"找到部署配置: {model_id}")

                    model_info = self._get_model_registry().get_model_info(model_id)

                    if model_info and model_info.get('status') == ModelStatus.ACTIVE.value:
                        self._load_model(model_id)
                        self._initialized = True
                        debug_print(self.service_name, f"加载生产模型成功: {model_id}")
                    else:
                        debug_print(self.service_name, f"生产模型未激活: {model_id}")
                else:
                    debug_print(self.service_name, "未找到生产模型部署配置")

        except Exception as e:
            debug_print(self.service_name, f"加载生产模型失败: {e}")

    def _load_model(self, model_id: str) -> bool:
        """
        加载指定模型

        参数:
            model_id: 模型ID

        返回:
            是否加载成功
        """
        try:
            # 检查是否已加载
            if model_id in self._active_models:
                debug_print(self.service_name, f"模型已加载: {model_id}")
                return True

            # 获取模型元数据
            model_info = self._get_model_registry().get_model_info(model_id)
            if not model_info:
                debug_print(self.service_name, f"模型不存在: {model_id}")
                return False

            # 验证任务类型
            if model_info.get('task_type') != self._task_type.value:
                debug_print(self.service_name,
                            f"模型类型不匹配: {model_info.get('task_type')} != {self._task_type.value}")
                return False

            # 加载模型到内存
            model_loader = self._get_model_loader()
            success = model_loader.load_model(
                model_id=model_id,
                operator="bentoml",
                ip_address=None
            )

            if success:
                model = model_loader.get_model(model_id)
                if model:
                    self._active_models[model_id] = {
                        'model': model,
                        'version': model_info.get('model_version'),
                        'loaded_at': datetime.now(),
                        'metadata': model_info
                    }
                    self._model_versions[model_id] = model_info.get('model_version')
                    debug_print(self.service_name,
                                f"模型加载成功: {model_id} (version={model_info.get('model_version')})")
                    return True
                else:
                    debug_print(self.service_name, f"模型加载后获取失败: {model_id}")
                    return False
            else:
                debug_print(self.service_name, f"模型加载失败: {model_id}")
                return False

        except Exception as e:
            debug_print(self.service_name, f"加载模型异常: {model_id}, {e}")
            return False

    def _unload_model(self, model_id: str):
        """
        卸载模型

        参数:
            model_id: 模型ID
        """
        if model_id in self._active_models:
            model_loader = self._get_model_loader()
            model_loader.unload_model(
                model_id=model_id,
                operator="bentoml",
                ip_address=None
            )
            del self._active_models[model_id]
            if model_id in self._model_versions:
                del self._model_versions[model_id]
            debug_print(self.service_name, f"模型卸载成功: {model_id}")

    # ==================== 热加载监控 ====================

    def _start_hot_reload_monitor(self):
        """启动热加载监控线程"""

        def monitor():
            debug_print(self.service_name, "热加载监控线程启动")
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
                            model_info = self._get_model_registry().get_model_info(model_id)
                            if not model_info:
                                continue

                            current_version = self._model_versions.get(model_id)
                            latest_version = model_info.get('model_version')

                            if latest_version and latest_version != current_version:
                                debug_print(
                                    self.service_name,
                                    f"检测到模型版本更新: {model_id} {current_version} -> {latest_version}"
                                )
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
                    debug_print(self.service_name, f"热加载监控异常: {e}")

                self._stop_reload.wait(self._reload_interval)

        self._hot_reload_thread = threading.Thread(
            target=monitor,
            daemon=True,
            name=f"{self.service_name}_reloader"
        )
        self._hot_reload_thread.start()

    # ==================== 公开接口 - 模型获取 ====================

    def get_production_model(self) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        获取生产模型

        返回:
            (model_id, model_instance, model_version) 元组，未找到返回 (None, None, None)
        """
        if not self._active_models:
            self._load_production_model()
            if not self._active_models:
                return None, None, None

        # 返回第一个激活的模型（生产环境通常只有一个）
        for mid, info in self._active_models.items():
            return mid, info['model'], info['version']

        return None, None, None

    def get_model(self, model_id: str, auto_load: bool = True) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        根据模型ID获取模型

        参数:
            model_id: 模型ID
            auto_load: 如果模型未加载，是否自动加载

        返回:
            (model_id, model_instance, model_version) 元组，未找到返回 (None, None, None)
        """
        # 检查是否已加载
        if model_id in self._active_models:
            info = self._active_models[model_id]
            return model_id, info['model'], info['version']

        # 自动加载
        if auto_load:
            if self._load_model(model_id):
                info = self._active_models.get(model_id)
                if info:
                    return model_id, info['model'], info['version']

        return None, None, None

    def get_loaded_model_ids(self) -> List[str]:
        """
        获取所有已加载的模型ID列表

        返回:
            模型ID列表
        """
        return list(self._active_models.keys())

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """
        获取已加载的模型列表

        返回:
            已加载模型信息列表
        """
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
        """
        手动重新加载模型

        参数:
            model_id: 模型ID

        返回:
            操作结果字典，包含 success, message, model_id, version 字段
        """
        try:
            debug_print(self.service_name, f"手动重新加载模型: {model_id}")
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
            return {
                'success': False,
                'message': str(e)
            }

    def unload_model(self, model_id: str) -> Dict[str, Any]:
        """
        卸载模型

        参数:
            model_id: 模型ID

        返回:
            操作结果字典
        """
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
            return {
                'success': False,
                'message': str(e)
            }

    # ==================== 健康检查 ====================

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        返回:
            健康状态信息字典
        """
        status = 'healthy'
        issues = []

        if not self._db_initialized:
            status = 'degraded'
            issues.append('database_not_initialized')

        if not self._active_models:
            status = 'degraded'
            issues.append('no_models_loaded')

        for mid, info in self._active_models.items():
            if not info.get('model'):
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
        debug_print(self.service_name, "停止服务")
        self._stop_reload.set()

    def __del__(self):
        """
        析构函数

        注意：__del__ 在垃圾回收时调用，应保持简单。
        """
        if hasattr(self, '_stop_reload'):
            self._stop_reload.set()