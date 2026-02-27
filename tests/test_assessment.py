"""Tests for assessment scoring modules."""


from english_skill_tester.assessment.calibration import (
    calibrate_fluency_score,
    calibrate_grammar_score,
    calibrate_vocabulary_score,
    get_full_mapping,
    get_level_label,
)
from english_skill_tester.assessment.metrics import (
    compute_fluency_metrics,
    compute_grammar_metrics,
    compute_vocabulary_richness,
    compute_word_frequency_score,
)
from english_skill_tester.assessment.rule_based import RuleBasedScorer
from english_skill_tester.models.assessment import (
    AssessmentResult,
    ComponentScores,
    score_to_ielts,
    score_to_toeic,
)


class TestVocabularyMetrics:
    def test_empty_text(self):
        result = compute_vocabulary_richness("")
        assert result["ttr"] == 0.0
        assert result["total_words"] == 0

    def test_simple_text(self):
        result = compute_vocabulary_richness("I like to eat food and I like to cook food")
        assert result["total_words"] == 11
        assert result["unique_words"] <= result["total_words"]
        assert 0 < result["ttr"] <= 1.0

    def test_diverse_text(self):
        result = compute_vocabulary_richness(
            "The magnificent architecture demonstrated extraordinary craftsmanship"
        )
        assert result["ttr"] == 1.0  # All unique words
        assert result["avg_word_length"] > 5


class TestFluencyMetrics:
    def test_empty_text(self):
        result = compute_fluency_metrics("")
        assert result["filler_ratio"] == 0.0

    def test_no_fillers(self):
        result = compute_fluency_metrics(
            "I went to the store and bought some groceries yesterday."
        )
        assert result["filler_ratio"] == 0.0

    def test_with_fillers(self):
        result = compute_fluency_metrics(
            "Um like I basically um went to um the store you know"
        )
        assert result["filler_ratio"] > 0.3

    def test_wpm_calculation(self):
        result = compute_fluency_metrics("word " * 120, duration_seconds=60)
        assert 100 < result["words_per_minute"] < 140


class TestGrammarMetrics:
    def test_empty_text(self):
        result = compute_grammar_metrics("")
        assert result["error_count"] == 0

    def test_correct_grammar(self):
        result = compute_grammar_metrics(
            "She doesn't like to go there. He went to the park."
        )
        assert result["error_count"] == 0

    def test_grammar_errors(self):
        result = compute_grammar_metrics("He don't like it. She don't know.")
        assert result["error_count"] >= 2


class TestWordFrequency:
    def test_simple_words(self):
        score = compute_word_frequency_score("I am a good person who is very nice")
        assert score < 80  # Simple words should score lower than advanced

    def test_advanced_words(self):
        score = compute_word_frequency_score(
            "The epistemological implications necessitate comprehensive deliberation"
        )
        assert score > 50

    def test_too_few_words(self):
        score = compute_word_frequency_score("hi there")
        assert score == 50.0


class TestCalibration:
    def test_vocabulary_calibration(self):
        score = calibrate_vocabulary_score(
            ttr=0.7, unique_words=50, avg_word_length=5.5, frequency_score=60
        )
        assert 0 <= score <= 100

    def test_grammar_calibration(self):
        score = calibrate_grammar_score(error_ratio=0.0, readability=8.0)
        assert score > 50

    def test_fluency_calibration(self):
        score = calibrate_fluency_score(
            filler_ratio=0.05, words_per_minute=130, avg_sentence_length=10
        )
        assert score > 50

    def test_level_labels(self):
        assert get_level_label(10) == "Beginner"
        assert get_level_label(30) == "Elementary"
        assert get_level_label(50) == "Intermediate"
        assert get_level_label(70) == "Upper Intermediate"
        assert get_level_label(90) == "Advanced"

    def test_full_mapping(self):
        mapping = get_full_mapping(65)
        assert mapping["level"] == "Upper Intermediate"
        assert "toeic" in mapping
        assert "ielts" in mapping


class TestScoreConversions:
    def test_toeic_range(self):
        assert 10 <= score_to_toeic(0) <= 20
        assert 970 <= score_to_toeic(100) <= 990

    def test_ielts_range(self):
        assert score_to_ielts(0) >= 1.0
        assert score_to_ielts(100) <= 9.0


class TestComponentScores:
    def test_default_scores(self):
        scores = ComponentScores()
        assert scores.vocabulary == 50.0
        assert scores.grammar == 50.0

    def test_assessment_result_compute(self):
        result = AssessmentResult(
            components=ComponentScores(
                vocabulary=80,
                grammar=70,
                fluency=60,
                comprehension=50,
                coherence=40,
                pronunciation_proxy=30,
            )
        )
        overall = result.compute_overall()
        assert 0 < overall < 100
        # Weighted average check
        expected = 80 * 0.20 + 70 * 0.25 + 60 * 0.20 + 50 * 0.15 + 40 * 0.15 + 30 * 0.05
        assert abs(overall - expected) < 0.01


class TestRuleBasedScorer:
    def test_empty_text(self):
        scorer = RuleBasedScorer()
        result = scorer.evaluate("")
        assert result.vocabulary == 50.0  # defaults

    def test_real_text(self):
        scorer = RuleBasedScorer()
        result = scorer.evaluate(
            "I think the problem is that many people don't understand "
            "the importance of environmental conservation. We should "
            "take more responsibility for our actions and consider the "
            "long-term consequences of pollution and deforestation.",
            duration_seconds=30,
        )
        assert result.vocabulary > 0
        assert result.grammar > 0
        assert result.fluency > 0
