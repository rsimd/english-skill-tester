"""Smoke tests for storage/score_history module."""

from datetime import datetime

import pytest

from english_skill_tester.storage.score_history import (
    append_session_score,
    read_score_history,
)


class TestReadScoreHistory:
    def test_returns_empty_when_no_file(self, tmp_path):
        result = read_score_history(tmp_path)
        assert result == {"sessions": []}

    def test_returns_empty_sessions_list(self, tmp_path):
        result = read_score_history(tmp_path)
        assert isinstance(result["sessions"], list)
        assert len(result["sessions"]) == 0


class TestAppendSessionScore:
    def test_creates_history_file(self, tmp_path):
        append_session_score(
            sessions_dir=tmp_path,
            session_id="session-001",
            started_at=datetime(2026, 2, 28, 10, 0, 0),
            ended_at=datetime(2026, 2, 28, 10, 5, 0),
            overall_score=72.5,
            components={"vocabulary": 80.0, "grammar": 70.0},
            toeic_estimate=650,
            ielts_estimate=6.5,
        )
        history_file = tmp_path / "score_history.json"
        assert history_file.exists()

    def test_appended_entry_content(self, tmp_path):
        append_session_score(
            sessions_dir=tmp_path,
            session_id="session-002",
            started_at=datetime(2026, 2, 28, 10, 0, 0),
            ended_at=datetime(2026, 2, 28, 10, 10, 0),
            overall_score=55.0,
            components={"vocabulary": 60.0, "grammar": 50.0},
            toeic_estimate=500,
            ielts_estimate=5.0,
        )
        history = read_score_history(tmp_path)
        assert len(history["sessions"]) == 1
        entry = history["sessions"][0]
        assert entry["session_id"] == "session-002"
        assert entry["overall"] == 55.0
        assert entry["toeic_estimate"] == 500
        assert entry["ielts_estimate"] == 5.0
        assert entry["duration_seconds"] == 600

    def test_multiple_append(self, tmp_path):
        for i in range(3):
            append_session_score(
                sessions_dir=tmp_path,
                session_id=f"session-{i:03d}",
                started_at=datetime(2026, 2, 28, 10, i, 0),
                ended_at=None,
                overall_score=float(50 + i * 10),
                components={},
                toeic_estimate=400 + i * 50,
                ielts_estimate=4.5 + i * 0.5,
            )
        history = read_score_history(tmp_path)
        assert len(history["sessions"]) == 3

    def test_no_duration_when_ended_at_none(self, tmp_path):
        append_session_score(
            sessions_dir=tmp_path,
            session_id="session-no-end",
            started_at=datetime(2026, 2, 28, 10, 0, 0),
            ended_at=None,
            overall_score=60.0,
            components={},
            toeic_estimate=550,
            ielts_estimate=5.5,
        )
        history = read_score_history(tmp_path)
        entry = history["sessions"][0]
        assert "duration_seconds" not in entry

    def test_roundtrip_read_after_write(self, tmp_path):
        components = {
            "vocabulary": 75.0,
            "grammar": 80.0,
            "fluency": 65.0,
        }
        append_session_score(
            sessions_dir=tmp_path,
            session_id="roundtrip-session",
            started_at=datetime(2026, 2, 28, 12, 0, 0),
            ended_at=datetime(2026, 2, 28, 12, 3, 0),
            overall_score=73.3,
            components=components,
            toeic_estimate=680,
            ielts_estimate=6.5,
        )
        history = read_score_history(tmp_path)
        entry = history["sessions"][0]
        assert entry["scores"] == components
        assert entry["overall"] == pytest.approx(73.3, abs=0.05)
