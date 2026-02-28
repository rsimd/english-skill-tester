"""User profile model for tracking learning progress across sessions."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    estimated_cefr: str = "B1"  # A1/A2/B1/B2/C1/C2
    self_reported_level: str | None = None
    session_count: int = 0
    total_practice_minutes: float = 0.0
    score_history: list[dict] = Field(default_factory=list)
    error_patterns: dict[str, int] = Field(default_factory=dict)
    vocabulary_stats: dict = Field(default_factory=dict)
    weak_grammar_points: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
