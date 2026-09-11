"""arq worker: a batch job-okat egy KÜLÖN process dolgozza fel, Redis queue-n
keresztül (docs/phase1-terv.md 11. szakasz — ez a production alapértelmezés,
`queue.backend: redis`; a dev/teszt `inline` backend nem használja ezt a
modult, ld. api/deps.py ServiceContainer.submit_batch_job).

Indítás: `arq leiratozo.queue.worker.WorkerSettings`
(a CONFIG_PATH env ugyanúgy vezérli, mint az API-processzt)."""
from __future__ import annotations

import logging
from typing import Any

from arq.connections import RedisSettings

from leiratozo.api.deps import ServiceContainer, get_config
from leiratozo.logging_setup import configure_logging

logger = logging.getLogger(__name__)


async def on_startup(ctx: dict[str, Any]) -> None:
    """Egyszer fut workerenként — itt épül fel a ServiceContainer (modellek
    betöltése), nem minden job-nál újra."""
    config = get_config()
    configure_logging(config.logging.level, config.logging.format)
    ctx["services"] = ServiceContainer(config)
    logger.info("leiratozo worker elindult")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("leiratozo worker leáll")


async def run_batch_job(
    ctx: dict[str, Any], job_id: str, raw_audio: bytes, filename_hint: str | None
) -> None:
    services: ServiceContainer = ctx["services"]
    await services.batch_service.run(job_id, raw_audio, filename_hint=filename_hint)


class WorkerSettings:
    functions = [run_batch_job]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_config().queue.url)
