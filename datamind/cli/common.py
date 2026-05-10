# datamind/cli/common.py

import uuid

from datamind.config import get_settings
from datamind.logging import setup_logging
from datamind.context.scope import context_scope


def cli_context(
    verbose: bool = False,
):
    """CLI上下文"""

    settings = get_settings()

    if verbose:
        logging_config = settings.logging
    else:
        logging_config = settings.logging.model_copy(
            update={
                "level": "ERROR",
            }
        )

    setup_logging(logging_config)

    return context_scope(
        user="system",
        ip="127.0.0.1",
        trace_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        source="cli",
    )