import structlog

logger = structlog.get_logger(__name__)


class ModelDeployer:
    """模型部署器（负责：绑定版本 + 创建 deployment 记录）"""

    def __init__(self, backend):
        self.backend = backend

    async def deploy(
        self,
        *,
        model,
        version,
        deployment_repo,
        deployed_by: str | None = None,
    ):
        logger.info(
            "开始部署模型",
            model_id=model.model_id,
            version_id=version.version_id,
        )

        # 1. 确认 Bento 模型存在
        try:
            self.backend.load(
                framework=version.framework,
                tag=version.bento_tag,
            )
        except Exception as e:
            raise RuntimeError(
                f"模型未注册到 Bento Store: {version.bento_tag}"
            ) from e

        # 2. 生成 deployment_id
        import uuid
        deployment_id = f"dep_{uuid.uuid4().hex[:8]}"

        # 3. 创建 deployment record（核心）
        deployment = deployment_repo.create_deployment(
            deployment_id=deployment_id,
            model_id=model.model_id,
            version_id=version.version_id,
            framework=version.framework,
            deployed_by=deployed_by,
        )

        # 4. 默认 endpoint（逻辑层）
        endpoint = f"/api/v1/models/{model.name}/{version.version}/predict"

        logger.info(
            "部署成功",
            deployment_id=deployment_id,
            endpoint=endpoint,
        )

        return {
            "deployment_id": deployment_id,
            "model_id": model.model_id,
            "version_id": version.version_id,
            "endpoint": endpoint,
            "bento_tag": version.bento_tag,
            "status": "active",
        }