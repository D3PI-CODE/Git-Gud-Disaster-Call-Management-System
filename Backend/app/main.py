"""ResQNet FastAPI backend — VALSEA + Gemini + Postgres."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.db.pool import close_pool, init_pool, open_pool
from app.routes.incidents import router as incidents_router

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    init_pool(settings.database_url)
    await open_pool()
    logger.info("Database pool ready")
    yield
    await close_pool()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = load_settings()

    application = FastAPI(
        title="ResQNet API",
        description="Disaster call pipeline: VALSEA → Gemini → Postgres",
        version="1.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(incidents_router)

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    return application


app = create_app()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings
