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
    """Convert 0-100 assessment score to approximate TOEIC score (10-990).

    Uses piecewise linear mapping to better approximate real TOEIC distribution.
    Calibrated against typical TOEIC score distributions.
    """
    score = max(0.0, min(100.0, score))
    # Piecewise linear segments: (score_threshold, toeic_value)
    segments = [
        (0, 10),
        (20, 150),   # Low performers: 0-20% → 10-150
        (40, 350),   # Below average: 20-40% → 150-350
        (55, 500),   # Average: 40-55% → 350-500
        (70, 650),   # Above average: 55-70% → 500-650
        (85, 800),   # Good: 70-85% → 650-800
        (95, 900),   # Very good: 85-95% → 800-900
        (100, 990),  # Excellent: 95-100% → 900-990
    ]
    for i in range(len(segments) - 1):
        s0, t0 = segments[i]
        s1, t1 = segments[i + 1]
        if s0 <= score <= s1:
            ratio = (score - s0) / (s1 - s0)
            return round(t0 + ratio * (t1 - t0))
    return 990


def score_to_ielts(score: float) -> float:
    """Convert 0-100 assessment score to approximate IELTS score (1.0-9.0).

    Uses piecewise linear mapping to better approximate IELTS band distribution.
    """
    score = max(0.0, min(100.0, score))
    segments = [
        (0, 1.0),
        (20, 2.5),   # Low: 0-20% → 1.0-2.5
        (40, 4.0),   # Below average: 20-40% → 2.5-4.0
        (55, 5.5),   # Average: 40-55% → 4.0-5.5 (most learners here)
        (70, 6.5),   # Above average: 55-70% → 5.5-6.5
        (85, 7.5),   # Good: 70-85% → 6.5-7.5
        (95, 8.5),   # Very good: 85-95% → 7.5-8.5
        (100, 9.0),  # Expert: 95-100% → 8.5-9.0
    ]
    for i in range(len(segments) - 1):
        s0, t0 = segments[i]
        s1, t1 = segments[i + 1]
        if s0 <= score <= s1:
            ratio = (score - s0) / (s1 - s0)
            return round(t0 + ratio * (t1 - t0), 1)
    return 9.0
