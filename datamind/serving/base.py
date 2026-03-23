# datamind/serving/base.py
"""BentoML 服务基类

提供 BentoML 服务的基础抽象，集成现有模块：
- 数据库会话管理
- 模型加载器
- 审计日志
- A/B测试
- 链路追踪
"""

import time
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.model_registry import model_registry
from datamind.core.ml.inference import inference_engine
from datamind.core.db.database import get_db, db_manager
from datamind.core.db.models.model.deployment import ModelDeployment
from datamind.core.domain.enums import AuditAction, TaskType, ModelStatus
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseBentoService:
    """BentoML 服务基类

    提供模型加载、热更新、审计日志等基础功能。
    """

    # 类级别锁，确保数据库只初始化一次
    _db_lock = threading.Lock()
    _db_initialized = False

    def __init__(self, service_type: str, service_name: str):
        """
        初始化服务

        Args:
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
        self._stop_reload = False

        # 初始化状态
        self._initialized = False

        # 初始化数据库连接
        self._init_database()

        # 加载生产模型
        self._load_production_model_gracefully()

        # 启动热加载监控
        self._start_hot_reload_monitor()

        debug_print(self.service_name, f"初始化完成, task_type={self._task_type.value}")

    def _get_environment(self) -> str:
        """获取环境值（小写，匹配数据库枚举）"""
        return settings.app.env.lower()

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

    def _load_production_model_gracefully(self):
        """优雅地加载生产模型（失败不影响服务启动）"""
        try:
            self._load_production_model()
        except Exception as e:
            debug_print(self.service_name, f"加载生产模型失败: {e}")
            self._initialized = False

    def _load_production_model(self):
        """加载生产环境模型"""
        if not self._db_initialized:
            debug_print(self.service_name, "数据库未就绪，跳过生产模型加载")
            return

        try:
            env_value = self._get_environment()

            with get_db() as session:
                deployment = session.query(ModelDeployment).filter(
                    ModelDeployment.environment == env_value,
                    ModelDeployment.is_active == True
                ).first()

                if deployment:
                    model_id = deployment.model_id
                    model_info = model_registry.get_model_info(model_id)

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
            self._initialized = False

    def _load_model(self, model_id: str) -> bool:
        """
        加载指定模型

        Args:
            model_id: 模型ID

        Returns:
            是否加载成功
        """
        try:
            # 检查是否已加载
            if model_id in self._active_models:
                debug_print(self.service_name, f"模型已加载: {model_id}")
                return True

            # 获取模型元数据
            model_info = model_registry.get_model_info(model_id)
            if not model_info:
                debug_print(self.service_name, f"模型不存在: {model_id}")
                return False

            # 验证任务类型
            if model_info.get('task_type') != self._task_type.value:
                debug_print(self.service_name,
                            f"模型类型不匹配: {model_info.get('task_type')} != {self._task_type.value}")
                return False

            # 加载模型到内存
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
                    debug_print(self.service_name, f"模型加载成功: {model_id}")
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
        """卸载模型"""
        if model_id in self._active_models:
            model_loader.unload_model(
                model_id=model_id,
                operator="bentoml",
                ip_address=None
            )
            del self._active_models[model_id]
            if model_id in self._model_versions:
                del self._model_versions[model_id]
            debug_print(self.service_name, f"模型卸载成功: {model_id}")

    def _start_hot_reload_monitor(self):
        """启动热加载监控线程"""

        def monitor():
            debug_print(self.service_name, "热加载监控线程启动")
            env_value = self._get_environment()

            while not self._stop_reload:
                try:
                    if not self._db_initialized:
                        time.sleep(30)
                        continue

                    with get_db() as session:
                        deployments = session.query(ModelDeployment).filter(
                            ModelDeployment.environment == env_value,
                            ModelDeployment.is_active == True,
                            ModelDeployment.deployment_config.contains({'hot_reload': True})
                        ).all()

                        for deployment in deployments:
                            model_id = deployment.model_id
                            model_info = model_registry.get_model_info(model_id)
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
                                        "service": self.service_name
                                    }
                                )

                except Exception as e:
                    debug_print(self.service_name, f"热加载监控异常: {e}")

                time.sleep(30)

        self._hot_reload_thread = threading.Thread(target=monitor, daemon=True)
        self._hot_reload_thread.start()

    def get_model(self, model_id: Optional[str] = None) -> Tuple[Optional[str], Optional[Any], Optional[str]]:
        """
        获取模型实例

        Args:
            model_id: 指定模型ID，不指定则使用生产模型

        Returns:
            (model_id, model_instance, model_version)
        """
        if model_id:
            if model_id not in self._active_models:
                if not self._load_model(model_id):
                    return None, None, None
            info = self._active_models[model_id]
            return model_id, info['model'], info['version']

        if not self._active_models:
            self._load_production_model_gracefully()
            if not self._active_models:
                return None, None, None

        for mid, info in self._active_models.items():
            return mid, info['model'], info['version']

        return None, None, None

    def reload_model(self, model_id: str) -> Dict[str, Any]:
        """手动重新加载模型"""
        try:
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

    def register_model(
            self,
            model_id: str,
            model_path: str,
            metadata: Dict[str, Any],
            operator: str = "bentoml"
    ) -> Dict[str, Any]:
        """注册新模型"""
        try:
            if metadata.get('task_type') != self._task_type.value:
                return {
                    'success': False,
                    'message': f'模型类型不匹配: {metadata.get("task_type")} != {self._task_type.value}'
                }

            result = model_registry.register_model(
                model_name=metadata.get('model_name', model_id),
                model_version=metadata.get('model_version', '1.0.0'),
                task_type=metadata.get('task_type'),
                model_type=metadata.get('model_type'),
                framework=metadata.get('framework'),
                input_features=metadata.get('input_features', []),
                output_schema=metadata.get('output_schema', {}),
                created_by=operator,
                model_file=open(model_path, 'rb'),
                description=metadata.get('description'),
                model_params=metadata.get('model_params'),
                tags=metadata.get('tags'),
                ip_address=None,
                scorecard_params=metadata.get('scorecard_params'),
                risk_config=metadata.get('risk_config')
            )

            if result and metadata.get('load_immediately'):
                self._load_model(model_id)

            return {
                'success': True,
                'message': f'模型 {model_id} 注册成功',
                'model_id': result
            }

        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }

    def unregister_model(self, model_id: str, operator: str = "bentoml") -> Dict[str, Any]:
        """注销模型"""
        try:
            self._unload_model(model_id)

            if hasattr(model_registry, 'archive_model'):
                model_registry.archive_model(
                    model_id=model_id,
                    operator=operator,
                    reason="注销",
                    ip_address=None
                )
                return {
                    'success': True,
                    'message': f'模型 {model_id} 注销成功'
                }
            else:
                return {
                    'success': False,
                    'message': '注销功能未实现'
                }

        except Exception as e:
            return {
                'success': False,
                'message': str(e)
            }

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """获取已加载的模型列表"""
        return [
            {
                'model_id': mid,
                'version': info['version'],
                'loaded_at': info['loaded_at'].isoformat(),
                'model_type': info['metadata'].get('model_type'),
                'framework': info['metadata'].get('framework')
            }
            for mid, info in self._active_models.items()
        ]

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            'status': 'healthy' if self._initialized or self._active_models else 'degraded',
            'service': self.service_name,
            'task_type': self._task_type.value,
            'loaded_models': len(self._active_models),
            'models': list(self._active_models.keys())
        }

    def __del__(self):
        """析构函数，停止热加载监控"""
        self._stop_reload = True
        if self._hot_reload_thread and self._hot_reload_thread.is_alive():
            self._hot_reload_thread.join(timeout=5)