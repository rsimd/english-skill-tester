"""Assessment score models."""

from datetime import datetime

from pydantic import BaseModel, Field


class ComponentScores(BaseModel):
    """Individual component scores (0-100 each)."""

    vocabulary: float = 50.0
    grammar: float = 50.0
    fluency: float = 50.0
    comprehension: float = 50.0
    coherence: float = 50.0
    pronunciation_proxy: float = 50.0


# Weights for each component
COMPONENT_WEIGHTS: dict[str, float] = {
    "vocabulary": 0.20,
    "grammar": 0.25,
    "fluency": 0.20,
    "comprehension": 0.15,
    "coherence": 0.15,
    "pronunciation_proxy": 0.05,
}


class AssessmentResult(BaseModel):
    """A single assessment snapshot."""

    timestamp: datetime = Field(default_factory=datetime.now)
    components: ComponentScores = Field(default_factory=ComponentScores)
    overall_score: float = 50.0
    source: str = "hybrid"  # "rule_based", "llm", "hybrid"

    def compute_overall(self) -> float:
        """Compute weighted overall score from components."""
        scores = self.components.model_dump()
        self.overall_score = sum(
            scores[key] * weight for key, weight in COMPONENT_WEIGHTS.items()
        )
        return self.overall_score


class ScoreMapping(BaseModel):
    """TOEIC/IELTS score mapping."""

    score: float
    level: str
    toeic_range: str
    ielts_range: str


SCORE_MAPPINGS: list[ScoreMapping] = [
    ScoreMapping(score=10, level="Beginner", toeic_range="10-250", ielts_range="1-3"),
    ScoreMapping(score=30, level="Elementary", toeic_range="250-400", ielts_range="3-4"),
    ScoreMapping(score=50, level="Intermediate", toeic_range="400-600", ielts_range="4.5-5.5"),
    ScoreMapping(score=70, level="Upper Intermediate", toeic_range="600-800", ielts_range="6-7"),
    ScoreMapping(score=90, level="Advanced", toeic_range="800-990", ielts_range="7.5-9"),
]


def score_to_toeic(score: float) -> int:
    """Convert 0-100 score to estimated TOEIC score."""
    return int(10 + (score / 100) * 980)


def score_to_ielts(score: float) -> float:
    """Convert 0-100 score to estimated IELTS band."""
    return round(1.0 + (score / 100) * 8.0, 1)
