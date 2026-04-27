"""
FastAPI application factory for DevSynapse.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.dependencies import auth_service, get_monitoring_system, get_plugin_manager, settings
from api.routes.admin import router as admin_router
from api.routes.auth import router as auth_router
from api.routes.chat import router as chat_router
from api.routes.monitoring import router as monitoring_router
from api.routes.settings import router as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
LOOPBACK_API_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _cors_allow_credentials(allowed_origins: list[str]) -> bool:
    return "*" not in allowed_origins


def _api_host_is_loopback(api_host: str) -> bool:
    return api_host.strip().lower() in LOOPBACK_API_HOSTS


def _warn_if_api_host_is_exposed(api_host: str) -> None:
    if _api_host_is_loopback(api_host):
        return
    logger.warning(
        "DevSynapse API host '%s' is not loopback. This local-first app can execute "
        "commands on the user's machine; expose it to a network only if you understand "
        "and control that risk.",
        api_host,
    )


def _log_api_request_safely(monitoring_system, **kwargs) -> None:
    try:
        monitoring_system.log_api_request(**kwargs)
    except Exception:
        logger.exception("Failed to persist API request telemetry")


async def _log_api_request_background(monitoring_system, **kwargs) -> None:
    _log_api_request_safely(monitoring_system, **kwargs)


def _attach_api_request_log(response, monitoring_system, **kwargs):
    background_tasks = BackgroundTasks()
    if response.background is not None:
        background_tasks.add_task(response.background)
    background_tasks.add_task(_log_api_request_background, monitoring_system, **kwargs)
    response.background = background_tasks
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    plugin_manager = get_plugin_manager()

    auth_service.ensure_default_users()
    _warn_if_api_host_is_exposed(settings.api_host)
    logger.info("Inicializando DevSynapse...")
    await plugin_manager.load_all()
    await plugin_manager.emit_event("server:startup", {})
    logger.info("DevSynapse iniciado com %s plugins", len(plugin_manager.loaded_plugins))

    try:
        yield
    finally:
        logger.info("Desligando DevSynapse...")
        await plugin_manager.emit_event("server:shutdown", {})
        await plugin_manager.unload_all()
        logger.info("DevSynapse desligado")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DevSynapse AI API",
        description="API do assistente de desenvolvimento inteligente",
        version=settings.app_version,
        lifespan=lifespan,
    )
    cors_allowed_origins = settings.get_cors_allowed_origins()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins,
        allow_credentials=_cors_allow_credentials(cors_allowed_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    monitoring_system = get_monitoring_system()

    @app.middleware("http")
    async def monitor_requests(request: Request, call_next):
        start_time = time.time()
        try:
            response = await call_next(request)
            response_time = time.time() - start_time
            _attach_api_request_log(
                response,
                monitoring_system,
                endpoint=request.url.path,
                method=request.method,
                status_code=response.status_code,
                response_time=response_time,
                user_id=None,
                ip_address=request.client.host if request.client else None,
            )
            response.headers["X-Response-Time"] = f"{response_time:.3f}s"
            return response
        except Exception:
            response_time = time.time() - start_time
            _log_api_request_safely(
                monitoring_system,
                endpoint=request.url.path,
                method=request.method,
                status_code=500,
                response_time=response_time,
                user_id=None,
                ip_address=request.client.host if request.client else None,
            )
            raise

    @app.get("/api")
    async def api_info():
        return {
            "service": "DevSynapse AI API",
            "version": settings.app_version,
            "status": "operational",
            "endpoints": {
                "chat": "/chat",
                "execute": "/execute",
                "feedback": "/feedback",
                "health": "/health",
                "dashboard": "/monitoring/stats",
                "docs": "/docs",
            },
        }

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(chat_router)
    app.include_router(monitoring_router)
    app.include_router(settings_router)

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dir.exists():
        assets_dir = frontend_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
        async def serve_frontend(full_path: str):
            file_path = frontend_dir / full_path
            if file_path.exists() and file_path.is_file() and full_path != "index.html":
                return FileResponse(str(file_path))
            return FileResponse(str(frontend_dir / "index.html"))

    return app


app = create_app()
