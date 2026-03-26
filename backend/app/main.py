from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware import SecurityHeadersMiddleware
from app.routers.ai_configs import router as ai_configs_router
from app.routers.analyses import router as analyses_router
from app.routers.auth import router as auth_router
from app.routers.schedules import router as schedules_router
from app.routers.spotify import router as spotify_router
from app.routers.users import router as users_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Music History Analyser",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Security headers must be added before CORS so they are always present
    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(spotify_router)
    app.include_router(ai_configs_router)
    app.include_router(analyses_router)
    app.include_router(schedules_router)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
