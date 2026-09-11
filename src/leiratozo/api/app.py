"""FastAPI application factory. Ld. docs/phase1-terv.md 9. szakasz a végpont-
kontraktusért."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from leiratozo.api.deps import ServiceContainer, get_config
from leiratozo.api.routes import config as config_routes
from leiratozo.api.routes import health, jobs, live, speakers
from leiratozo.config.schema import AppConfig
from leiratozo.logging_setup import configure_logging


def create_app(config: AppConfig | None = None) -> FastAPI:
    cfg = config or get_config()
    configure_logging(cfg.logging.level, cfg.logging.format)

    services = ServiceContainer(cfg)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # queue.backend=="redis" esetén itt épül fel az arq/Redis pool; "inline"
        # esetén (config.fake.yaml, tesztek) nincs teendő — ld. deps.ServiceContainer.
        await services.start()
        try:
            yield
        finally:
            await services.stop()

    app = FastAPI(title="Leiratozó Worker", version="0.1.0", lifespan=lifespan)
    app.state.services = services

    app.include_router(health.router)
    app.include_router(jobs.router)
    app.include_router(speakers.router)
    app.include_router(live.router)
    app.include_router(config_routes.router)
    return app
