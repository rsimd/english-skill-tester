"""Smoke tests for HybridScorer."""

from unittest.mock import AsyncMock, patch

import pytest

from english_skill_tester.assessment.scorer import HybridScorer
from english_skill_tester.models.assessment import AssessmentResult, ComponentScores
from english_skill_tester.models.session import Session


class TestHybridScorerInit:
    def test_instantiation(self):
        scorer = HybridScorer(api_key="test-key")
        assert scorer.rule_scorer is not None
        assert scorer.llm_evaluator is not None
        assert scorer.llm_interval_utterances == 10
        assert scorer.llm_interval_seconds == 120.0

    def test_instantiation_custom_params(self):
        scorer = HybridScorer(
            api_key="test-key",
            eval_model="gpt-4o",
            llm_interval_utterances=5,
            llm_interval_seconds=60.0,
        )
        assert scorer.llm_interval_utterances == 5
        assert scorer.llm_interval_seconds == 60.0

    def test_blend_static_method(self):
        result = HybridScorer._blend(80.0, 60.0, rule_weight=0.6)
        assert result == pytest.approx(72.0, abs=0.1)

    def test_blend_equal_weights(self):
        result = HybridScorer._blend(100.0, 0.0, rule_weight=0.5)
        assert result == pytest.approx(50.0, abs=0.1)

    def test_latest_result_initial(self):
        scorer = HybridScorer(api_key="test-key")
        result = scorer.latest_result
        assert isinstance(result, AssessmentResult)
        assert 0.0 <= result.overall_score <= 100.0

    def test_history_initial_empty(self):
        scorer = HybridScorer(api_key="test-key")
        assert scorer.history == []


class TestHybridScorerUpdate:
    async def test_update_single_utterance(self):
        """With 1 utterance, LLM eval does not trigger (needs >= 3)."""
        scorer = HybridScorer(api_key="test-key")
        session = Session(session_id="test-session-001")
        session.add_utterance("user", "Hello, how are you today?")

        result = await scorer.update(session)

        assert isinstance(result, AssessmentResult)
        assert 0.0 <= result.overall_score <= 100.0
        assert len(scorer.history) == 1

    async def test_update_appends_history(self):
        scorer = HybridScorer(api_key="test-key")
        session = Session(session_id="test-session-002")
        session.add_utterance("user", "I went to the store yesterday.")
        session.add_utterance("assistant", "That sounds interesting!")
        session.add_utterance("user", "Yes, I bought some groceries.")

        await scorer.update(session)
        await scorer.update(session)

        assert len(scorer.history) == 2

    async def test_update_with_llm_mocked(self):
        """LLM eval triggers when user_count >= 3 and interval met."""
        scorer = HybridScorer(
            api_key="test-key",
            llm_interval_utterances=1,
            llm_interval_seconds=0.0,
        )
        session = Session(session_id="test-session-003")
        for i in range(3):
            session.add_utterance("user", f"Utterance number {i + 1} here.")

        mock_scores = ComponentScores(
            vocabulary=70.0,
            grammar=65.0,
            fluency=60.0,
            comprehension=75.0,
            coherence=70.0,
            pronunciation_proxy=65.0,
        )
        with patch.object(
            scorer.llm_evaluator,
            "evaluate",
            new=AsyncMock(return_value=mock_scores),
        ):
            result = await scorer.update(session)

        assert isinstance(result, AssessmentResult)
        assert 0.0 <= result.overall_score <= 100.0
