# datamind/runtime/manager.py

"""Runtime 管理器

负责模型运行时生命周期管理，包括：
  - 将模型发布为可服务的 BentoML service
  - 启动服务（local / process）
  - 停止服务
  - 获取服务 endpoint
  - 绑定 deployment 与 runtime 服务

核心功能：
  - build_service: 构建服务
  - start_service: 启动服务
  - stop_service: 停止服务
  - get_endpoint: 获取服务地址
  - deploy_model: 一键发布模型为可访问服务

注意：
  RuntimeManager 不管理“部署记录（deploy）”
  只管理“真实运行服务（runtime）”
"""

import subprocess
import socket
import time
import structlog
from typing import Any

from datamind.runtime.loader import ModelLoader
from datamind.runtime.backend import BentoBackend

logger = structlog.get_logger(__name__)


class RuntimeManager:
    """模型运行时管理器"""

    def __init__(self) -> None:
        self.loader = ModelLoader()
        self.backend = BentoBackend()

    # -------------------------
    # endpoint 生成（关键点）
    # -------------------------
    def _allocate_port(self) -> int:
        """分配可用端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("0.0.0.0", 0))
            return s.getsockname()[1]

    def _build_endpoint(self, host: str, port: int) -> str:
        """构建 endpoint"""
        return f"http://{host}:{port}"

    # -------------------------
    # 服务构建（核心）
    # -------------------------
    def build_service(
        self,
        *,
        framework: str,
        tag: str,
    ) -> Any:
        """加载模型服务实例"""
        model = self.loader.load(
            framework=framework,
            tag=tag,
        )

        logger.info(
            "模型加载成功",
            framework=framework,
            tag=tag,
        )

        return model

    # -------------------------
    # 启动服务（本地运行）
    # -------------------------
    def start_service(
        self,
        *,
        framework: str,
        tag: str,
        host: str = "127.0.0.1",
        port: int | None = None,
    ) -> dict[str, Any]:
        """启动服务"""

        if port is None:
            port = self._allocate_port()

        model = self.build_service(
            framework=framework,
            tag=tag,
        )

        # ⚠️ 这里是关键：你目前没有真正 server runner
        # 先用 subprocess 模拟 BentoML serve
        proc = subprocess.Popen(
            [
                "bentoml",
                "serve",
                "--port",
                str(port),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 给服务一点启动时间
        time.sleep(2)

        endpoint = self._build_endpoint(host, port)

        logger.info(
            "服务启动成功",
            endpoint=endpoint,
            framework=framework,
            tag=tag,
        )

        return {
            "endpoint": endpoint,
            "process_id": proc.pid,
            "framework": framework,
            "tag": tag,
        }

    # -------------------------
    # 停止服务
    # -------------------------
    def stop_service(self, *, process_id: int) -> None:
        """停止服务"""
        try:
            subprocess.Popen(["kill", "-9", str(process_id)])
            logger.info("服务已停止", process_id=process_id)
        except Exception as e:
            logger.error("停止服务失败", error=str(e))
            raise RuntimeError(f"停止服务失败: {e}") from e

    # -------------------------
    # 一键发布（核心 API）
    # -------------------------
    def deploy_model(
        self,
        *,
        framework: str,
        name: str,
        version: str,
        host: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """发布模型为 runtime 服务"""

        tag = f"{name}:{version}"

        result = self.start_service(
            framework=framework,
            tag=tag,
            host=host,
        )

        return {
            "endpoint": result["endpoint"],
            "process_id": result["process_id"],
            "tag": tag,
        }