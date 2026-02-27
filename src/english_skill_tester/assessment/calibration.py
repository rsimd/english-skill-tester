"""TOEIC/IELTS score calibration and mapping."""

from english_skill_tester.models.assessment import score_to_ielts, score_to_toeic


def calibrate_vocabulary_score(
    ttr: float,
    unique_words: int,
    avg_word_length: float,
    frequency_score: float,
) -> float:
    """Calibrate vocabulary metrics to 0-100 score.

    Args:
        ttr: Type-Token Ratio (0-1).
        unique_words: Count of unique words used.
        avg_word_length: Average word length.
        frequency_score: Word frequency sophistication score (0-100).

    Returns:
        Calibrated vocabulary score 0-100.
    """
    # TTR contribution (weight: 30%) — higher diversity is better
    # TTR naturally decreases with more text, so we boost it
    ttr_score = min(100, ttr * 150)

    # Unique words contribution (weight: 20%) — more unique words is better
    unique_score = min(100, unique_words * 1.5)

    # Word length contribution (weight: 10%) — longer words suggest sophistication
    length_score = min(100, max(0, (avg_word_length - 3) * 30))

    # Frequency score contribution (weight: 40%)
    freq_score = frequency_score

    return (ttr_score * 0.3 + unique_score * 0.2 + length_score * 0.1 + freq_score * 0.4)


def calibrate_grammar_score(
    error_ratio: float,
    readability: float,
) -> float:
    """Calibrate grammar metrics to 0-100 score.

    Args:
        error_ratio: Detected errors per word.
        readability: Flesch-Kincaid grade level.

    Returns:
        Calibrated grammar score 0-100.
    """
    # Error penalty (weight: 60%) — fewer errors is better
    error_score = max(0, 100 - error_ratio * 500)

    # Complexity bonus (weight: 40%) — higher grade level = more complex structures
    complexity_score = min(100, readability * 8)

    return error_score * 0.6 + complexity_score * 0.4


def calibrate_fluency_score(
    filler_ratio: float,
    words_per_minute: float,
    avg_sentence_length: float,
) -> float:
    """Calibrate fluency metrics to 0-100 score.

    Args:
        filler_ratio: Proportion of filler words.
        words_per_minute: Speaking rate.
        avg_sentence_length: Average sentence length in words.

    Returns:
        Calibrated fluency score 0-100.
    """
    # Filler penalty (weight: 40%) — fewer fillers is better
    filler_score = max(0, 100 - filler_ratio * 400)

    # WPM score (weight: 30%) — optimal range is 120-160 WPM for conversation
    if words_per_minute == 0:
        wpm_score = 50.0  # No duration data available
    elif words_per_minute < 60:
        wpm_score = words_per_minute  # Too slow
    elif words_per_minute <= 160:
        wpm_score = 60 + (words_per_minute - 60) * 0.4  # Good range
    else:
        wpm_score = max(50, 100 - (words_per_minute - 160) * 0.3)  # Too fast

    # Sentence length score (weight: 30%) — optimal range is 8-15 words
    if avg_sentence_length < 3:
        sent_score = avg_sentence_length * 15
    elif avg_sentence_length <= 15:
        sent_score = 45 + (avg_sentence_length - 3) * 4.5
    else:
        sent_score = max(50, 100 - (avg_sentence_length - 15) * 3)

    return filler_score * 0.4 + wpm_score * 0.3 + sent_score * 0.3


def get_level_label(score: float) -> str:
    """Get human-readable level label from score.

    Args:
        score: Overall score 0-100.

    Returns:
        Level label string.
    """
    if score < 20:
        return "Beginner"
    elif score < 40:
        return "Elementary"
    elif score < 60:
        return "Intermediate"
    elif score < 80:
        return "Upper Intermediate"
    else:
        return "Advanced"


def get_full_mapping(score: float) -> dict[str, str | int | float]:
    """Get complete score mapping with TOEIC/IELTS estimates.

    Args:
        score: Overall score 0-100.

    Returns:
        Dict with level, toeic, ielts estimates.
    """
    return {
        "level": get_level_label(score),
        "toeic": score_to_toeic(score),
        "ielts": score_to_ielts(score),
        "score": round(score, 1),
    }
