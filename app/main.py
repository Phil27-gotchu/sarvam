"""FastAPI application entrypoint for Malwani Mitra."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import bridge, coach, dish, menu, order
from app.config import WEB_DIR, ensure_runtime_dirs, get_settings
from app.data.repo import get_repo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("malwani_mitra")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_runtime_dirs()
    repo = get_repo()
    settings = get_settings()
    logger.info(
        "startup_complete",
        extra={
            "dishes": len(repo.list_dishes()),
            "origins": len(repo.list_origins()),
            "mock_sarvam": settings.mock_sarvam,
        },
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Malwani Mitra",
        description="Voice-first Malwani dining companion for tourists",
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
    application.include_router(menu.router)
    application.include_router(dish.router)
    application.include_router(order.router)
    application.include_router(coach.router)
    application.include_router(bridge.router)

    @application.get("/health")
    def health() -> dict[str, object]:
        s = get_settings()
        repo = get_repo()
        return {
            "status": "ok",
            "mock_sarvam": s.mock_sarvam,
            "dishes": len(repo.list_dishes()),
            "origins": [o.country for o in repo.list_origins()],
        }

    if WEB_DIR.exists():
        application.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

        @application.get("/")
        def index() -> FileResponse:
            return FileResponse(WEB_DIR / "index.html")

    return application


app = create_app()
