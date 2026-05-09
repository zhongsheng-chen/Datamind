from datamind.models.guard import ModelGuard
from datamind.models.enums import MetadataStatus, DeploymentStatus

ModelGuard.validate_metadata_transition(
    current=MetadataStatus.ACTIVE,
    target=MetadataStatus.DEPRECATED,
)

ModelGuard.validate_deployment_transition(
    current=DeploymentStatus.INACTIVE,
    target=DeploymentStatus.ACTIVE,
    metadata_status=MetadataStatus.ACTIVE,
)