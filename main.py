import asyncio

from datamind.config import get_settings
from datamind.logging import setup_logging
from datamind.db.core.diagnostics import log_db_diagnostics
from datamind.db.health import health_check


async def startup():
    settings = get_settings()
    setup_logging(settings.logging)

    log_db_diagnostics()

    await health_check()

if __name__ == '__main__':
    asyncio.run(startup())