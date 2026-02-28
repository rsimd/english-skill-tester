"""Smoke tests for Pydantic models."""

from datetime import datetime

import pytest

from english_skill_tester.models.assessment import (
    AssessmentResult,
    ComponentScores,
    score_to_ielts,
    score_to_toeic,
)
from english_skill_tester.models.session import (
    Session,
    SessionStatus,
    SkillLevel,
    Utterance,
)


class TestComponentScores:
    def test_default_values(self):
        scores = ComponentScores()
        assert scores.vocabulary == 50.0
        assert scores.grammar == 50.0
        assert scores.fluency == 50.0
        assert scores.comprehension == 50.0
        assert scores.coherence == 50.0
        assert scores.pronunciation_proxy == 50.0

    def test_custom_values(self):
        scores = ComponentScores(vocabulary=80.0, grammar=70.0)
        assert scores.vocabulary == 80.0
        assert scores.grammar == 70.0

    def test_model_dump(self):
        scores = ComponentScores()
        data = scores.model_dump()
        assert "vocabulary" in data
        assert "grammar" in data
        assert len(data) == 6


class TestAssessmentResult:
    def test_default_instantiation(self):
        result = AssessmentResult()
        assert isinstance(result.timestamp, datetime)
        assert isinstance(result.components, ComponentScores)
        assert result.overall_score == 50.0
        assert result.source == "hybrid"

    def test_compute_overall(self):
        result = AssessmentResult(
            components=ComponentScores(
                vocabulary=100.0,
                grammar=100.0,
                fluency=100.0,
                comprehension=100.0,
                coherence=100.0,
                pronunciation_proxy=100.0,
            )
        )
        overall = result.compute_overall()
        assert overall == pytest.approx(100.0, abs=0.1)

    def test_compute_overall_zero(self):
        result = AssessmentResult(
            components=ComponentScores(
                vocabulary=0.0,
                grammar=0.0,
                fluency=0.0,
                comprehension=0.0,
                coherence=0.0,
                pronunciation_proxy=0.0,
            )
        )
        overall = result.compute_overall()
        assert overall == pytest.approx(0.0, abs=0.1)

    def test_score_to_toeic_range(self):
        assert score_to_toeic(0) >= 10
        assert score_to_toeic(100) <= 990
        assert score_to_toeic(50) > score_to_toeic(20)

    def test_score_to_ielts_range(self):
        assert score_to_ielts(0) >= 1.0
        assert score_to_ielts(100) <= 9.0
        assert score_to_ielts(70) > score_to_ielts(40)


class TestSessionStatus:
    def test_enum_values(self):
        assert SessionStatus.CREATED == "created"
        assert SessionStatus.ACTIVE == "active"
        assert SessionStatus.COMPLETED == "completed"
        assert SessionStatus.ERROR == "error"


class TestSkillLevel:
    def test_from_score_beginner(self):
        assert SkillLevel.from_score(10) == SkillLevel.BEGINNER

    def test_from_score_intermediate(self):
        assert SkillLevel.from_score(50) == SkillLevel.INTERMEDIATE

    def test_from_score_advanced(self):
        assert SkillLevel.from_score(90) == SkillLevel.ADVANCED

    def test_enum_values(self):
        assert SkillLevel.BEGINNER == "beginner"
        assert SkillLevel.ADVANCED == "advanced"


class TestUtterance:
    def test_instantiation(self):
        utt = Utterance(role="user", text="Hello world")
        assert utt.role == "user"
        assert utt.text == "Hello world"
        assert isinstance(utt.timestamp, datetime)
        assert utt.duration_ms is None

    def test_with_duration(self):
        utt = Utterance(role="assistant", text="Hi there", duration_ms=1500.0)
        assert utt.duration_ms == 1500.0


class TestSession:
    def test_instantiation(self):
        session = Session(session_id="abc-123")
        assert session.session_id == "abc-123"
        assert session.status == SessionStatus.CREATED
        assert session.utterances == []
        assert session.current_level == SkillLevel.INTERMEDIATE

    def test_add_utterance(self):
        session = Session(session_id="test-001")
        utt = session.add_utterance("user", "I love learning English.")
        assert utt.role == "user"
        assert len(session.utterances) == 1

    def test_user_utterances_filtered(self):
        session = Session(session_id="test-002")
        session.add_utterance("user", "Hello")
        session.add_utterance("assistant", "Hi")
        session.add_utterance("user", "How are you?")

        user_utts = session.user_utterances
        assert len(user_utts) == 2
        assert all(u.role == "user" for u in user_utts)

    def test_user_text_joined(self):
        session = Session(session_id="test-003")
        session.add_utterance("user", "Hello")
        session.add_utterance("assistant", "Hi there")
        session.add_utterance("user", "World")

        text = session.user_text_joined
        assert "Hello" in text
        assert "World" in text
        assert "Hi there" not in text

    def test_duration_none_without_end(self):
        session = Session(session_id="test-004")
        # L-005: active sessions return elapsed time (not None)
        assert isinstance(session.duration_seconds, float)
        assert session.duration_seconds >= 0

    def test_duration_with_end(self):
        from datetime import timedelta
        session = Session(session_id="test-005")
        session.ended_at = session.started_at + timedelta(seconds=120)
        assert session.duration_seconds == pytest.approx(120.0, abs=1.0)

    def test_required_field_session_id(self):
        with pytest.raises(Exception):
            Session()
