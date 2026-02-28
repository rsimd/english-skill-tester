"""Hybrid assessment coordinator combining rule-based and LLM evaluation."""

import asyncio
import time

import structlog

from english_skill_tester.assessment.llm_evaluator import LLMEvaluator
from english_skill_tester.assessment.rule_based import RuleBasedScorer
from english_skill_tester.models.assessment import AssessmentResult, ComponentScores
from english_skill_tester.models.session import Session

logger = structlog.get_logger()


class HybridScorer:
    """Combines rule-based continuous and LLM periodic evaluation.

    Rule-based scores update on every new utterance.
    LLM evaluation triggers periodically (by utterance count or time interval).

    Args:
        api_key: OpenAI API key.
        eval_model: Model for LLM evaluation.
        llm_interval_utterances: Trigger LLM eval every N user utterances.
        llm_interval_seconds: Trigger LLM eval every N seconds.
    """

    def __init__(
        self,
        api_key: str,
        eval_model: str = "gpt-4o-mini",
        llm_interval_utterances: int = 10,
        llm_interval_seconds: float = 120.0,
    ):
        self.rule_scorer = RuleBasedScorer()
        self.llm_evaluator = LLMEvaluator(api_key=api_key, model=eval_model)
        self.llm_interval_utterances = llm_interval_utterances
        self.llm_interval_seconds = llm_interval_seconds

        self._last_llm_eval_time: float = 0.0
        self._last_llm_eval_count: int = 0
        self._latest_rule_scores = ComponentScores()
        self._latest_llm_scores = ComponentScores()
        self._llm_scores_lock = asyncio.Lock()
        self._llm_task: asyncio.Task | None = None
        self._history: list[AssessmentResult] = []

    @property
    def latest_result(self) -> AssessmentResult:
        """Get the most recent assessment result."""
        if self._history:
            return self._history[-1]
        result = AssessmentResult()
        result.compute_overall()
        return result

    @property
    def history(self) -> list[AssessmentResult]:
        return self._history

    async def _background_llm_eval(
        self, transcript: list[dict[str, str]], user_count: int
    ) -> None:
        """Run LLM evaluation in background and update scores when complete.

        Args:
            transcript: Conversation transcript.
            user_count: Number of user utterances.
        """
        try:
            scores = await self.llm_evaluator.evaluate(transcript)
            async with self._llm_scores_lock:
                self._latest_llm_scores = scores
            logger.info("llm_evaluation_completed", utterance_count=user_count)
        except Exception as e:
            logger.error("llm_evaluation_failed", error=str(e))

    async def update(self, session: Session) -> AssessmentResult:
        """Update assessment with current session data.

        Args:
            session: Current conversation session.

        Returns:
            Latest hybrid assessment result.
        """
        user_text = session.user_text_joined
        duration = session.duration_seconds

        # Always run rule-based evaluation
        self._latest_rule_scores = self.rule_scorer.evaluate(user_text, duration)

        # Check if LLM evaluation should trigger
        user_count = len(session.user_utterances)
        now = time.time()
        should_eval_llm = (
            user_count >= 3  # Minimum utterances needed
            and (
                user_count - self._last_llm_eval_count >= self.llm_interval_utterances
                or now - self._last_llm_eval_time >= self.llm_interval_seconds
            )
        )

        if should_eval_llm:
            transcript = [
                {"role": u.role, "text": u.text}
                for u in session.utterances
                if u.text
            ]
            # Spawn LLM evaluation as background task (non-blocking)
            # Skip if previous task is still running to avoid double-scheduling
            if self._llm_task is None or self._llm_task.done():
                self._llm_task = asyncio.create_task(
                    self._background_llm_eval(transcript, user_count)
                )
                self._last_llm_eval_time = now
                self._last_llm_eval_count = user_count
                logger.info("llm_evaluation_triggered", utterance_count=user_count)
            else:
                logger.debug("llm_evaluation_skipped_busy")

        # Merge: rule-based for vocab/grammar/fluency, LLM for comprehension/coherence
        # Read LLM scores with lock protection
        async with self._llm_scores_lock:
            llm_scores = self._latest_llm_scores

        merged = ComponentScores(
            vocabulary=self._blend(
                self._latest_rule_scores.vocabulary,
                llm_scores.vocabulary,
                rule_weight=0.6,
            ),
            grammar=self._blend(
                self._latest_rule_scores.grammar,
                llm_scores.grammar,
                rule_weight=0.6,
            ),
            fluency=self._blend(
                self._latest_rule_scores.fluency,
                llm_scores.fluency,
                rule_weight=0.7,
            ),
            comprehension=llm_scores.comprehension,
            coherence=llm_scores.coherence,
            pronunciation_proxy=llm_scores.pronunciation_proxy,
        )

        result = AssessmentResult(components=merged, source="hybrid")
        result.compute_overall()
        self._history.append(result)

        return result

    @staticmethod
    def _blend(rule: float, llm: float, rule_weight: float = 0.6) -> float:
        """Blend rule-based and LLM scores.

        Args:
            rule: Rule-based score.
            llm: LLM score.
            rule_weight: Weight for rule-based score (0-1).

        Returns:
            Blended score.
        """
        return round(rule * rule_weight + llm * (1 - rule_weight), 1)
