"""Session data models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """Session lifecycle states."""

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    ERROR = "error"


class SkillLevel(StrEnum):
    """English skill level categories."""

    BEGINNER = "beginner"
    ELEMENTARY = "elementary"
    INTERMEDIATE = "intermediate"
    UPPER_INTERMEDIATE = "upper_intermediate"
    ADVANCED = "advanced"

    @classmethod
    def from_score(cls, score: float) -> "SkillLevel":
        """Determine skill level from 0-100 score."""
        if score < 20:
            return cls.BEGINNER
        elif score < 40:
            return cls.ELEMENTARY
        elif score < 60:
            return cls.INTERMEDIATE
        elif score < 80:
            return cls.UPPER_INTERMEDIATE
        else:
            return cls.ADVANCED


class Utterance(BaseModel):
    """A single utterance in the conversation."""

    role: str  # "user" or "assistant"
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)
    duration_ms: float | None = None


class Session(BaseModel):
    """Conversation session data."""

    session_id: str
    status: SessionStatus = SessionStatus.CREATED
    started_at: datetime = Field(default_factory=datetime.now)
    ended_at: datetime | None = None
    utterances: list[Utterance] = Field(default_factory=list)
    current_level: SkillLevel = SkillLevel.INTERMEDIATE
    recording_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_utterance(self, role: str, text: str, duration_ms: float | None = None) -> Utterance:
        """Add an utterance to the session transcript."""
        utterance = Utterance(role=role, text=text, duration_ms=duration_ms)
        self.utterances.append(utterance)
        return utterance

    @property
    def user_utterances(self) -> list[Utterance]:
        """Get only user utterances."""
        return [u for u in self.utterances if u.role == "user"]

    @property
    def user_text_joined(self) -> str:
        """Get all user text joined for analysis."""
        return " ".join(u.text for u in self.user_utterances if u.text)

    @property
    def duration_seconds(self) -> float:
        """Session duration in seconds (uses current time if session is still active)."""
        if self.ended_at is None:
            return (datetime.now() - self.started_at).total_seconds()
        return (self.ended_at - self.started_at).total_seconds()
