"""CYBERPULSE AI — FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, engine
from ml.inference.service import get_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("cyberpulse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # capture the main event loop so sync/background code can broadcast via WS
    from .realtime.hub import hub
    import asyncio
    hub.bind_loop(asyncio.get_running_loop())
    # create tables (idempotent). Alembic migrations are provided for managed
    # PostgreSQL deployments; for the SQLite demo we use create_all.
    Base.metadata.create_all(bind=engine)
    svc = get_service()
    if svc.loaded:
        logger.info("Model loaded: %s", svc.model_path)
    else:
        logger.warning("Model NOT loaded — run scripts/train_model.py. "
                       "Prediction endpoints will return 503.")
    yield
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="CYBERPULSE AI",
        description=(
            "Proactive Cybercrime Intelligence & Cash-Withdrawal Prediction Platform. "
            "Prototype validated using synthetic data. Architecture designed for "
            "integration with authorized data sources."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # secure headers
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    from .routers import (
        alerts,
        auth,
        dashboard,
        data,
        demo,
        graph,
        health,
        investigations,
        map as map_router,
        model,
        notifications,
        predictions,
        realtime,
        simulation,
    )
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(map_router.router, prefix="/api/v1")
    app.include_router(predictions.router, prefix="/api/v1")
    app.include_router(alerts.router, prefix="/api/v1")
    app.include_router(investigations.router, prefix="/api/v1")
    app.include_router(graph.router, prefix="/api/v1")
    app.include_router(model.router, prefix="/api/v1")
    app.include_router(simulation.router, prefix="/api/v1")
    app.include_router(data.router, prefix="/api/v1")
    app.include_router(notifications.router, prefix="/api/v1")
    app.include_router(notifications.arouter, prefix="/api/v1")
    app.include_router(demo.router, prefix="/api/v1")
    app.include_router(realtime.router)  # /ws/events at root

    @app.get("/")
    def root():
        return {
            "name": "CYBERPULSE AI",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "disclaimer": "Prototype validated using synthetic data.",
        }

    return app


app = create_app()