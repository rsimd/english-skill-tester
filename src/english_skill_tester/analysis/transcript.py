"""Transcript formatting and highlighting for post-session review."""

import json
import re

from english_skill_tester.assessment.metrics import FILLERS, GRAMMAR_PATTERNS


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


def _analyze_grammar_llm(text: str) -> list[dict[str, str]]:
    """Detect grammar issues using LLM. Returns highlight entries.

    Returns empty list on failure (regex-based checks still run).
    """
    try:
        import openai  # noqa: PLC0415

        client = openai.OpenAI(timeout=5.0)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Analyze English speech text for grammar errors. "
                        "Detect: subject-verb agreement errors, missing articles, "
                        "tense inconsistency, unusual word order. "
                        'Respond with JSON: {"highlights": [{"type": "grammar", '
                        '"word": "...", "category": "..."}, ...]}. '
                        "Only include clear, definite errors. Keep the list short."
                    ),
                },
                {"role": "user", "content": text[:2000]},
            ],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content)
        highlights = data.get("highlights", [])
        # Validate structure
        return [h for h in highlights if isinstance(h, dict) and "type" in h and "word" in h]
    except Exception:
        return []


def _find_highlights(text: str) -> list[dict[str, str]]:
    """Find notable patterns in user text.

    Args:
        text: User utterance text.

    Returns:
        List of highlight annotations.
    """
    highlights: list[dict[str, str]] = []

    # LLM-based grammar checking (with fallback on failure)
    highlights.extend(_analyze_grammar_llm(text))

    # Find filler words (regex-based, always runs)
    words = re.findall(r"[a-zA-Z']+", text.lower())
    for word in words:
        if word in FILLERS:
            highlights.append({
                "type": "filler",
                "word": word,
                "suggestion": "Try to reduce filler words for smoother speech.",
            })

    # Find grammar patterns (regex-based, always runs)
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
