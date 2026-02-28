"""REST API routes for session management and history."""

import json
import uuid

import structlog
from fastapi import APIRouter, HTTPException

from english_skill_tester.config import get_settings
from english_skill_tester.storage.score_history import read_score_history

logger = structlog.get_logger()
router = APIRouter(prefix="/api")


def validate_session_id(session_id: str) -> str:
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    return session_id


@router.get("/sessions")
async def list_sessions() -> list[dict]:
    """List all saved sessions."""
    settings = get_settings()
    sessions = []
    sessions_dir = settings.sessions_dir
    if sessions_dir.exists():
        for path in sorted(sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text())
                sessions.append({
                    "session_id": data.get("session_id", path.stem),
                    "started_at": data.get("started_at", ""),
                    "status": data.get("status", ""),
                    "current_level": data.get("current_level", ""),
                    "utterance_count": len(data.get("utterances", [])),
                })
            except Exception:
                logger.warning("session_parse_error", path=str(path))
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """Get a specific session's full data."""
    session_id = validate_session_id(session_id)
    settings = get_settings()
    path = settings.sessions_dir / f"{session_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Session not found")
    return json.loads(path.read_text())


@router.get("/sessions/history")
async def get_score_history() -> dict:
    """Return historical session scores."""
    settings = get_settings()
    return read_score_history(settings.sessions_dir)


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}
