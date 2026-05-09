# datamind/cli/common.py

"""CLI上下文"""

import uuid

from datamind.context.scope import context_scope


def cli_context():
    """CLI上下文"""

    return context_scope(
        user="system",
        ip="127.0.0.1",
        trace_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        source="cli",
    )