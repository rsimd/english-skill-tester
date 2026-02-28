"""Score history persistence for tracking improvement over sessions."""

import fcntl
import json
import os
import tempfile
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

    lock_path = sessions_dir / (HISTORY_FILENAME + ".lock")
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)

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
        with tempfile.NamedTemporaryFile(
            "w", dir=sessions_dir, delete=False, suffix=".json"
        ) as tmp:
            json.dump(data, tmp, indent=2)
        os.replace(tmp.name, history_path)


def read_score_history(sessions_dir: Path) -> dict:
    """Read score history from file. Returns empty history if not found."""
    history_path = sessions_dir / HISTORY_FILENAME
    if not history_path.exists():
        return {"sessions": []}
    return json.loads(history_path.read_text())
