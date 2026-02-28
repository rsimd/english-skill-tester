"""User profile persistence (JSON + fcntl.flock + atomic write)."""

import fcntl
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from ..models.user_profile import UserProfile


def get_profile_path(user_id: str) -> Path:
    profiles_dir = Path(__file__).parent.parent.parent.parent.parent / "data" / "user_profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    return profiles_dir / f"{user_id}.json"


def load_profile(user_id: str) -> UserProfile:
    path = get_profile_path(user_id)
    if not path.exists():
        return UserProfile(user_id=user_id)
    with open(path) as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)
    return UserProfile(**data)


def save_profile(profile: UserProfile) -> None:
    path = get_profile_path(profile.user_id)
    profile.updated_at = datetime.now()
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".json") as tmp:
        json.dump(profile.model_dump(), tmp, default=str)
    os.replace(tmp.name, path)


def update_profile(user_id: str, **kwargs) -> UserProfile:
    profile = load_profile(user_id)
    for key, value in kwargs.items():
        setattr(profile, key, value)
    save_profile(profile)
    return profile


def append_session_score(user_id: str, session_id: str, overall_score: float, cefr: str) -> None:
    profile = load_profile(user_id)
    profile.score_history.append({
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "overall_score": overall_score,
        "cefr": cefr,
    })
    profile.session_count += 1
    profile.estimated_cefr = cefr
    save_profile(profile)
