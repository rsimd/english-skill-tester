"""Transcript formatting and highlighting for post-session review."""

import re

import spacy
from spacy.tokens import Doc

from english_skill_tester.assessment.metrics import FILLERS, GRAMMAR_PATTERNS

# Load spaCy model at module initialization
try:
    _nlp = spacy.load("en_core_web_sm")
except OSError:
    _nlp = None


def highlight_transcript(
    utterances: list[dict[str, str]],
) -> list[dict[str, object]]:
    """Add highlights to transcript utterances for review display.

    Args:
        utterances: List of {"role": str, "text": str}.

    Returns:
        Enriched utterances with highlights.
    """
    result = []
    for u in utterances:
        entry: dict[str, object] = {
            "role": u["role"],
            "text": u["text"],
            "highlights": [],
        }
        if u["role"] == "user":
            entry["highlights"] = _find_highlights(u["text"])
        result.append(entry)
    return result


def _check_subject_verb_agreement(doc: Doc) -> list[dict[str, str]]:
    """Detect subject-verb agreement errors using dependency parsing.

    Args:
        doc: spaCy parsed document.

    Returns:
        List of grammar highlights for agreement errors.
    """
    highlights: list[dict[str, str]] = []

    for token in doc:
        # Find nominal subjects
        if token.dep_ == "nsubj":
            # Get the verb this subject depends on
            verb = token.head
            if verb.pos_ == "VERB" or verb.pos_ == "AUX":
                # Check for common agreement errors
                # Third person singular subject (he/she/it) should use singular verb
                is_third_singular = token.tag_ in ["PRP", "NN", "NNP"] and token.text.lower() in ["he", "she", "it"]
                # Check if verb is plural form with singular subject
                if is_third_singular and verb.tag_ in ["VBP"] and verb.text.lower() in ["don't", "aren't", "weren't", "haven't"]:
                    highlights.append({
                        "type": "grammar",
                        "word": f"{token.text} {verb.text}",
                        "category": "subject-verb agreement (spaCy)",
                    })

    return highlights


def _check_missing_articles(doc: Doc) -> list[dict[str, str]]:
    """Detect potentially missing articles using determiner analysis.

    Args:
        doc: spaCy parsed document.

    Returns:
        List of grammar highlights for missing articles.
    """
    highlights: list[dict[str, str]] = []

    for i, token in enumerate(doc):
        # Check for countable singular nouns without determiners
        if token.pos_ == "NOUN" and token.tag_ == "NN":
            # Check if there's a determiner child
            has_det = any(child.dep_ == "det" for child in token.children)

            # Check if preceded by determiner
            has_preceding_det = i > 0 and doc[i-1].pos_ == "DET"

            # Skip if proper noun, mass noun, or already has determiner
            if not has_det and not has_preceding_det and not token.tag_ == "NNP":
                # Simple heuristic: flag if it's a subject or object
                if token.dep_ in ["nsubj", "nsubjpass", "dobj", "pobj"]:
                    highlights.append({
                        "type": "grammar",
                        "word": token.text,
                        "category": "possible missing article (spaCy)",
                    })

    return highlights


def _check_tense_consistency(doc: Doc) -> list[dict[str, str]]:
    """Detect tense inconsistency issues using verb form analysis.

    Args:
        doc: spaCy parsed document.

    Returns:
        List of grammar highlights for tense issues.
    """
    highlights: list[dict[str, str]] = []

    # Collect all main verbs in the sentence
    verbs = [token for token in doc if token.pos_ == "VERB" and token.dep_ in ["ROOT", "conj"]]

    if len(verbs) >= 2:
        # Check for mixed tenses (past + present in coordinated clauses)
        tenses = [token.tag_ for token in verbs]
        has_past = any(tag in ["VBD", "VBN"] for tag in tenses)
        has_present = any(tag in ["VBP", "VBZ", "VB"] for tag in tenses)

        if has_past and has_present:
            # This is a weak signal - only flag if verbs are coordinated
            highlights.append({
                "type": "grammar",
                "word": " and ".join(v.text for v in verbs),
                "category": "possible tense inconsistency (spaCy)",
            })

    return highlights


def _check_word_order(doc: Doc) -> list[dict[str, str]]:
    """Detect word order issues using dependency tree structure.

    Args:
        doc: spaCy parsed document.

    Returns:
        List of grammar highlights for word order problems.
    """
    highlights: list[dict[str, str]] = []

    # Check for adjectives appearing after nouns (non-English word order)
    # This is a weak check as some postpositive adjectives are valid in English
    for token in doc:
        if token.pos_ == "NOUN":
            # Look for adjectives that modify this noun
            for child in token.children:
                if child.pos_ == "ADJ" and child.dep_ == "amod":
                    # In English, adjectives typically precede nouns
                    # Flag if adjective comes after noun (simple heuristic)
                    if child.i > token.i:
                        highlights.append({
                            "type": "grammar",
                            "word": f"{token.text} {child.text}",
                            "category": "unusual word order (spaCy)",
                        })

    return highlights


def _find_highlights(text: str) -> list[dict[str, str]]:
    """Find notable patterns in user text.

    Args:
        text: User utterance text.

    Returns:
        List of highlight annotations.
    """
    highlights: list[dict[str, str]] = []

    # spaCy-based grammar checking (if model is available)
    if _nlp is not None:
        try:
            doc = _nlp(text)
            highlights.extend(_check_subject_verb_agreement(doc))
            highlights.extend(_check_missing_articles(doc))
            highlights.extend(_check_tense_consistency(doc))
            highlights.extend(_check_word_order(doc))
        except Exception:
            # Fallback to regex-only if spaCy parsing fails
            pass

    # Find filler words
    words = re.findall(r"[a-zA-Z']+", text.lower())
    for word in words:
        if word in FILLERS:
            highlights.append({
                "type": "filler",
                "word": word,
                "suggestion": "Try to reduce filler words for smoother speech.",
            })

    # Find grammar patterns
    for pattern, name in GRAMMAR_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for m in matches:
            highlights.append({
                "type": "grammar",
                "word": m.group(),
                "category": name,
            })

    # Find advanced vocabulary (long, uncommon words)
    for word in words:
        if len(word) >= 8:
            highlights.append({
                "type": "advanced_vocab",
                "word": word,
            })

    return highlights


def format_transcript_text(utterances: list[dict[str, str]]) -> str:
    """Format transcript as readable text.

    Args:
        utterances: List of {"role": str, "text": str}.

    Returns:
        Formatted transcript string.
    """
    lines = []
    for u in utterances:
        speaker = "You" if u["role"] == "user" else "AI"
        lines.append(f"{speaker}: {u['text']}")
    return "\n\n".join(lines)
