"""Tests for user profile storage and model."""

import pytest

from english_skill_tester.models.user_profile import UserProfile
from english_skill_tester.storage import user_profile as up_storage


@pytest.fixture(autouse=True)
def patch_profile_path(tmp_path, monkeypatch):
    def _get_profile_path(user_id: str):
        tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path / f"{user_id}.json"

    monkeypatch.setattr(up_storage, "get_profile_path", _get_profile_path)


def test_load_profile_new_user():
    profile = up_storage.load_profile("user_new")
    assert isinstance(profile, UserProfile)
    assert profile.user_id == "user_new"
    assert profile.session_count == 0
    assert profile.estimated_cefr == "B1"


def test_save_and_load():
    profile = up_storage.load_profile("user_save")
    profile.estimated_cefr = "C1"
    profile.interests = ["technology", "science"]
    up_storage.save_profile(profile)

    loaded = up_storage.load_profile("user_save")
    assert loaded.estimated_cefr == "C1"
    assert loaded.interests == ["technology", "science"]
    assert loaded.user_id == "user_save"


def test_append_session_score():
    up_storage.append_session_score("user_score", "session-001", 75.0, "B2")
    profile = up_storage.load_profile("user_score")
    assert profile.session_count == 1
    assert profile.estimated_cefr == "B2"
    assert len(profile.score_history) == 1
    entry = profile.score_history[0]
    assert entry["session_id"] == "session-001"
    assert entry["overall_score"] == 75.0
    assert entry["cefr"] == "B2"
