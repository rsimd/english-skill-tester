"""FastAPI application entry point."""

import logging
import os

import structlog
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from english_skill_tester.api.routes import router
from english_skill_tester.api.websocket import handle_browser_websocket
from english_skill_tester.config import Settings

# Configure structlog based on environment
is_production = os.getenv("ENV", "development").lower() == "production"

if is_production:
    # Production: JSON format for machine parsing
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
else:
    # Development: console format for human readability
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

settings = Settings()

app = FastAPI(title="English Skill Tester", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Optional APP_SECRET authentication middleware (P-SEC-002)."""
    if not settings.app_secret:
        return await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        return await call_next(request)
    secret = request.headers.get("X-App-Secret", "")
    if request.url.path == "/ws":
        if secret != settings.app_secret:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)
    if secret != settings.app_secret:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Browser WebSocket endpoint."""
    await handle_browser_websocket(websocket, settings)


# Mount frontend static files (must be after API routes)
app.mount("/", StaticFiles(directory=str(settings.frontend_dir), html=True), name="frontend")


def main() -> None:
    """Run the application."""
    uvicorn.run(
        "english_skill_tester.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
