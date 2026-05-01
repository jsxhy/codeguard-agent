from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.webhook import router as webhook_router
from app.api.reviews import router as reviews_router
from app.api.debt import router as debt_router
from app.config import get_settings
from app.models.database import close_db, init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"Starting {settings.system.name} v{settings.system.version}")

    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")

    yield

    await close_db()
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.system.name,
        version=settings.system.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(webhook_router)
    app.include_router(reviews_router)
    app.include_router(debt_router)

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": settings.system.version}

    @app.get("/")
    async def root():
        return {
            "name": settings.system.name,
            "version": settings.system.version,
            "docs": "/docs",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.system.host,
        port=settings.system.port,
        reload=True,
    )
