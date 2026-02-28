"""Score history persistence for tracking improvement over sessions."""

import json
from datetime import datetime
from pathlib import Path

HISTORY_FILENAME = "score_history.json"


def append_session_score(
    sessions_dir: Path,
    session_id: str,
    started_at: datetime,
    ended_at: datetime | None,
    overall_score: float,
    components: dict,
    toeic_estimate: int,
    ielts_estimate: float,
) -> None:
    """Append a session's final scores to score_history.json."""
    history_path = sessions_dir / HISTORY_FILENAME

    if history_path.exists():
        data = json.loads(history_path.read_text())
    else:
        data = {"sessions": []}

    entry: dict = {
        "session_id": session_id,
        "timestamp": started_at.isoformat(),
        "scores": components,
        "overall": round(overall_score, 1),
        "toeic_estimate": toeic_estimate,
        "ielts_estimate": ielts_estimate,
    }
    if ended_at is not None:
        entry["duration_seconds"] = round(
            (ended_at - started_at).total_seconds()
        )

    data["sessions"].append(entry)
    history_path.write_text(json.dumps(data, indent=2))


def read_score_history(sessions_dir: Path) -> dict:
    """Read score history from file. Returns empty history if not found."""
    history_path = sessions_dir / HISTORY_FILENAME
    if not history_path.exists():
        return {"sessions": []}
    return json.loads(history_path.read_text())
