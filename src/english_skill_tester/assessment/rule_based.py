"""Rule-based continuous scoring engine."""

import structlog

from english_skill_tester.assessment.calibration import (
    calibrate_fluency_score,
    calibrate_grammar_score,
    calibrate_vocabulary_score,
)
from english_skill_tester.assessment.metrics import (
    compute_fluency_metrics,
    compute_grammar_metrics,
    compute_vocabulary_richness,
    compute_word_frequency_score,
)
from english_skill_tester.models.assessment import ComponentScores

logger = structlog.get_logger()


class RuleBasedScorer:
    """Computes scores from linguistic analysis of user text.

    Analyzes accumulated user utterances for vocabulary, grammar, and fluency.
    """

    async def evaluate(
        self,
        text: str,
        duration_seconds: float | None = None,
    ) -> ComponentScores:
        """Evaluate user text and return component scores.

        Args:
            text: All user utterances joined.
            duration_seconds: Total speaking duration.

        Returns:
            ComponentScores with vocabulary, grammar, fluency filled.
        """
        if not text.strip():
            return ComponentScores()

        # Vocabulary
        vocab_metrics = compute_vocabulary_richness(text)
        freq_score = compute_word_frequency_score(text)
        vocabulary = calibrate_vocabulary_score(
            ttr=vocab_metrics["ttr"],
            unique_words=int(vocab_metrics["unique_words"]),
            avg_word_length=vocab_metrics["avg_word_length"],
            frequency_score=freq_score,
        )

        # Grammar
        grammar_metrics = await compute_grammar_metrics(text)
        grammar = calibrate_grammar_score(
            error_ratio=grammar_metrics["error_ratio"],
            readability=grammar_metrics["readability"],
        )

        # Fluency
        fluency_metrics = await compute_fluency_metrics(text, duration_seconds)
        fluency = calibrate_fluency_score(
            filler_ratio=fluency_metrics["filler_ratio"],
            words_per_minute=fluency_metrics["words_per_minute"],
            avg_sentence_length=fluency_metrics["avg_sentence_length"],
        )

        scores = ComponentScores(
            vocabulary=round(vocabulary, 1),
            grammar=round(grammar, 1),
            fluency=round(fluency, 1),
        )

        logger.debug(
            "rule_based_evaluation",
            vocabulary=scores.vocabulary,
            grammar=scores.grammar,
            fluency=scores.fluency,
        )

        return scores
