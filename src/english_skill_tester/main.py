"""FastAPI application entry point."""

import logging
import os
import time
from collections import defaultdict

import structlog
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from english_skill_tester.api.routes import router
from english_skill_tester.api.websocket import handle_browser_websocket
from english_skill_tester.config import Settings

# Simple in-memory rate limiter for WebSocket (slowapi does not support WS natively)
_ws_connection_times: dict[str, list[float]] = defaultdict(list)
_WS_RATE_LIMIT = 10  # max WS connections per IP per window
_WS_RATE_WINDOW = 60  # seconds

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
_allowed_origins_env = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
)
allowed_origins = [o.strip() for o in _allowed_origins_env.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
    """Browser WebSocket endpoint with per-IP rate limiting."""
    client_ip = websocket.client.host if websocket.client else "unknown"
    now = time.time()
    times = _ws_connection_times[client_ip]
    times[:] = [t for t in times if now - t < _WS_RATE_WINDOW]
    if len(times) >= _WS_RATE_LIMIT:
        await websocket.close(code=1008, reason="Rate limit exceeded")
        return
    times.append(now)
    await handle_browser_websocket(websocket, settings)


# Mount recordings for audio playback (must be before frontend catch-all)
app.mount(
    "/data/recordings",
    StaticFiles(directory=str(settings.recordings_dir)),
    name="recordings",
)

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
