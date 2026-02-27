"""Linguistic metrics computation for rule-based scoring."""

import re
from collections import Counter

import textstat


def compute_vocabulary_richness(text: str) -> dict[str, float]:
    """Compute vocabulary richness metrics.

    Args:
        text: User's combined text.

    Returns:
        Dict with ttr, unique_words, total_words, avg_word_length.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return {"ttr": 0.0, "unique_words": 0, "total_words": 0, "avg_word_length": 0.0}

    unique = set(words)
    ttr = len(unique) / len(words) if words else 0.0
    avg_length = sum(len(w) for w in words) / len(words)

    return {
        "ttr": min(ttr, 1.0),
        "unique_words": len(unique),
        "total_words": len(words),
        "avg_word_length": avg_length,
    }


# Common filler words/phrases
FILLERS = {
    "um", "uh", "er", "ah", "like", "you know", "i mean", "basically",
    "actually", "literally", "sort of", "kind of", "well",
}


def compute_fluency_metrics(
    text: str, duration_seconds: float | None = None
) -> dict[str, float]:
    """Compute fluency-related metrics.

    Args:
        text: User's combined text.
        duration_seconds: Total speaking duration.

    Returns:
        Dict with filler_ratio, words_per_minute, avg_sentence_length.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return {"filler_ratio": 0.0, "words_per_minute": 0.0, "avg_sentence_length": 0.0}

    # Filler ratio
    filler_count = sum(1 for w in words if w in FILLERS)
    filler_ratio = filler_count / len(words)

    # Words per minute
    wpm = 0.0
    if duration_seconds and duration_seconds > 0:
        wpm = (len(words) / duration_seconds) * 60

    # Average sentence length
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = len(words) / max(len(sentences), 1)

    return {
        "filler_ratio": filler_ratio,
        "words_per_minute": wpm,
        "avg_sentence_length": avg_sentence_length,
    }


# Simple grammar error patterns
GRAMMAR_PATTERNS: list[tuple[str, str]] = [
    (r"\bi\b(?!\s+')", "lowercase I"),  # "i" instead of "I" (transcript may do this)
    (r"\bhe don't\b", "subject-verb agreement"),
    (r"\bshe don't\b", "subject-verb agreement"),
    (r"\bit don't\b", "subject-verb agreement"),
    (r"\bmore better\b", "double comparative"),
    (r"\bmost best\b", "double superlative"),
    (r"\bgoed\b", "irregular past tense"),
    (r"\bchilds\b", "irregular plural"),
    (r"\bpeoples\b", "irregular plural"),
    (r"\bdid went\b", "double past"),
    (r"\bdoes goes\b", "double present"),
]


def compute_grammar_metrics(text: str) -> dict[str, float]:
    """Compute grammar-related metrics.

    Args:
        text: User's combined text.

    Returns:
        Dict with error_count, error_ratio, readability.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if not words:
        return {"error_count": 0, "error_ratio": 0.0, "readability": 50.0}

    # Count pattern-based errors
    error_count = 0
    for pattern, _name in GRAMMAR_PATTERNS:
        matches = re.findall(pattern, text.lower())
        error_count += len(matches)

    error_ratio = error_count / max(len(words), 1)

    # Readability as a proxy for grammatical complexity (higher = more complex = better)
    try:
        readability = textstat.flesch_kincaid_grade(text)
    except Exception:
        readability = 5.0

    return {
        "error_count": error_count,
        "error_ratio": error_ratio,
        "readability": max(0, min(readability, 20)),
    }


# Frequency tiers from common English word lists
HIGH_FREQ_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know", "take",
    "people", "into", "year", "your", "good", "some", "could", "them", "see",
    "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
}


def compute_word_frequency_score(text: str) -> float:
    """Score vocabulary sophistication based on word frequency distribution.

    Higher score = uses more low-frequency (advanced) words.

    Args:
        text: User's combined text.

    Returns:
        Score 0-100.
    """
    words = re.findall(r"[a-zA-Z']+", text.lower())
    if len(words) < 5:
        return 50.0

    counts = Counter(words)
    non_common = sum(c for w, c in counts.items() if w not in HIGH_FREQ_WORDS)
    ratio = non_common / len(words)

    # Map ratio to score: 0.3 ratio → ~50, 0.6 ratio → ~80
    return min(100, max(0, ratio * 130))
