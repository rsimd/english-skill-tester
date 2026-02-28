"""Linguistic metrics computation for rule-based scoring."""

import re

import textstat

# spaCy lazy loader with graceful fallback (incompatible with Python 3.14)
_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy  # noqa: PLC0415
            _nlp = spacy.load("en_core_web_sm")
        except Exception:
            _nlp = None  # Model not installed or runtime incompatible, graceful fallback
    return _nlp


def _check_grammar_spacy(text: str) -> list[str]:
    """Check grammar errors using spaCy dependency parsing."""
    nlp = _get_nlp()
    if nlp is None:
        return []
    errors = []
    doc = nlp(text)
    for token in doc:
        # Subject-verb agreement: singular subject with plural verb
        if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
            subj = token
            verb = token.head
            # "he/she/it" + present tense non-3rd-person-singular
            if subj.text.lower() in ("he", "she", "it") and verb.tag_ == "VBP":
                errors.append(f"Subject-verb agreement: '{subj.text} {verb.text}'")
    return errors


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


def is_filler_word(token, doc) -> bool:
    """Context-aware filler word detection using spaCy."""
    word = token.text.lower()
    if word == "like":
        # "I like dogs" → not filler (verb usage)
        if token.pos_ == "VERB":
            return False
        # "would like" → not filler
        if any(t.text.lower() == "would" for t in token.head.children):
            return False
        # "like a dog" → simile/preposition, not filler
        if token.pos_ in ("ADP", "SCONJ") and token.dep_ in ("prep", "mark"):
            return False
        return True  # Otherwise treat as filler
    elif word == "well":
        # "very well" / "quite well" → not filler
        if token.dep_ == "advmod" and token.head.pos_ == "ADJ":
            return False
        # At sentence start → likely filler
        if token.i == 0 or (token.i > 0 and doc[token.i - 1].is_sent_start):
            return True
        return token.dep_ == "intj"
    elif word in ("actually", "basically", "literally"):
        return True  # These are almost always fillers in speech
    return False


def _count_fillers(text: str) -> int:
    """Count fillers using context-aware spaCy detection with regex fallback."""
    nlp = _get_nlp()
    if nlp is None:
        # Fallback: original set-based detection
        words = text.lower().split()
        return sum(1 for w in words if w in FILLERS)
    doc = nlp(text)
    return sum(1 for token in doc if is_filler_word(token, doc))


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

    # Filler ratio (context-aware detection)
    filler_count = _count_fillers(text)
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

    # Combine regex errors + spaCy errors
    spacy_errors = _check_grammar_spacy(text)
    error_count += len(spacy_errors)

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


# Tier 1: 最頻出1000語（基本語彙）— BNC/COCA準拠
BASIC_WORDS: frozenset[str] = frozenset({
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "so", "up", "out", "if", "about", "who", "get", "which", "go", "me",
    "when", "make", "can", "like", "time", "no", "just", "him", "know", "take",
    "people", "into", "year", "your", "good", "some", "could", "them", "see",
    "other", "than", "then", "now", "look", "only", "come", "its", "over", "think",
    "also", "back", "after", "use", "two", "how", "our", "work", "first", "well",
    "way", "even", "new", "want", "because", "any", "these", "give", "day", "most",
    "us", "house", "car", "school", "water", "food", "money", "life", "child",
    "world", "hand", "part", "place", "case", "week", "company", "system",
    "program", "question", "government", "number", "night", "point", "city",
    "play", "small", "large", "next", "early", "young", "important", "few",
    "public", "bad", "same", "able", "human", "local", "sure", "free", "real",
    "best", "black", "white", "already", "name", "need", "home", "face",
    "today", "here", "help", "every", "family", "body", "music", "color",
    "friend", "room", "story", "fact", "idea", "air", "month", "lot",
    "right", "study", "book", "eye", "job", "word", "business", "issue",
    "side", "kind", "head", "service", "area", "national", "pay",
    "become", "move", "live", "hold", "run", "bring", "happen", "write",
    "provide", "sit", "stand", "lose", "meet", "include", "continue",
    "set", "learn", "change", "lead", "understand", "watch", "follow",
    "stop", "create", "speak", "read", "spend", "grow", "open", "walk",
    "win", "offer", "remember", "love", "consider", "appear", "buy", "wait",
    "serve", "die", "send", "expect", "build", "stay", "fall", "cut", "reach",
    "kill", "remain", "suggest", "raise", "pass", "sell", "require", "report",
    "decide", "pull", "feel", "talk", "next", "keep", "let", "put", "mean",
    "call", "try", "ask", "need", "leave", "seem", "start", "show", "hear",
    "play", "turn", "place", "find", "tell", "given", "end", "long", "down",
    "own", "old", "right", "big", "high", "different", "little", "last",
    "few", "much", "many", "great", "other", "old", "right", "right",
    "still", "own", "same", "another", "each", "both", "between", "own",
    "through", "during", "before", "never", "always", "around", "something",
    "nothing", "everything", "everyone", "someone", "anyone", "nobody",
    "almost", "often", "together", "sometimes", "however", "though",
    "without", "again", "ago", "yet", "since", "while", "under", "along",
    "near", "below", "above", "across", "behind", "within", "against",
    "upon", "inside", "outside", "around", "until", "toward", "between",
    "front", "back", "left", "right", "top", "bottom", "far", "away",
    "maybe", "perhaps", "definitely", "probably", "already", "soon", "later",
    "once", "twice", "enough", "either", "neither", "both", "each",
    "whose", "where", "why", "whether", "whenever", "whatever", "whoever",
    "although", "because", "since", "unless", "until", "while", "after",
    "before", "if", "when", "than", "that", "as", "so", "but", "and",
    "door", "window", "floor", "wall", "table", "chair", "bed", "light",
    "road", "street", "town", "country", "land", "sea", "river", "field",
    "tree", "flower", "fire", "sun", "moon", "star", "sky", "rain", "snow",
    "dog", "cat", "bird", "fish", "horse", "cow", "pig", "sheep", "bear",
    "red", "blue", "green", "yellow", "brown", "grey", "orange", "purple",
    "hot", "cold", "warm", "cool", "dry", "wet", "hard", "soft", "heavy",
    "light", "fast", "slow", "quiet", "loud", "clean", "dirty", "open",
    "close", "full", "empty", "strong", "weak", "safe", "happy", "sad",
    "angry", "afraid", "ready", "true", "false", "possible", "likely",
    "easy", "difficult", "simple", "complex", "clear", "dark", "deep",
    "long", "short", "wide", "narrow", "round", "flat", "straight", "sharp",
})

# Tier 2: 頻出1001-3000語（中級語彙）— BNC/COCA準拠
INTERMEDIATE_WORDS: frozenset[str] = frozenset({
    "achieve", "analyze", "approach", "aspect", "assume", "authority",
    "available", "benefit", "concept", "consistent", "context", "contract",
    "contribute", "create", "culture", "define", "develop", "distribute",
    "economy", "environment", "establish", "evaluate", "evidence", "factor",
    "financial", "focus", "function", "identify", "impact", "indicate",
    "individual", "initial", "involved", "major", "method", "occur",
    "percent", "period", "policy", "positive", "potential", "previous",
    "primary", "process", "professional", "project", "research",
    "resource", "response", "result", "role", "section", "significant",
    "similar", "specific", "structure", "technology", "theory", "tradition",
    "unique", "various", "increase", "reduce", "require",
    "suggest", "affect", "support", "maintain", "demonstrate", "obtain",
    "participate", "alternative", "comprehensive", "efficient",
    "fundamental", "generation", "global", "implement", "integration",
    "mechanism", "objective", "perspective", "phenomenon", "principle",
    "procedure", "represent", "sector", "strategy", "sufficient", "survey",
    "acquire", "adapt", "adequate", "adjacent", "adjust", "administration",
    "adult", "advocate", "allocate", "ambiguous", "analyze", "anticipate",
    "appropriate", "approximate", "assist", "associate", "attribute",
    "capacity", "category", "challenge", "circumstance", "clarify",
    "colleague", "communicate", "community", "compare", "component",
    "conduct", "conflict", "consequence", "consistent", "constitute",
    "constraint", "construct", "consume", "contemporary", "contrast",
    "controversy", "coordinate", "correspond", "criteria", "critical",
    "debate", "decline", "deduce", "demonstrate", "derive", "despite",
    "determine", "dimension", "diverse", "document", "domain",
    "emerge", "enable", "enhance", "ensure", "equivalent", "examine",
    "expose", "feature", "flexible", "generate", "hypothesis",
    "illustrate", "imply", "incorporate", "inevitable", "innovation",
    "investigate", "justify", "maintain", "minimum", "modify",
    "monitor", "motivation", "network", "neutral", "notion", "obtain",
    "outcome", "output", "overall", "parameter", "participant",
    "perception", "potential", "priority", "proportion", "pursue",
    "qualify", "quantity", "range", "ratio", "refer", "region",
    "regulate", "relationship", "relevant", "resolve", "retain",
    "significant", "simulate", "source", "specific", "stability",
    "status", "substitute", "summarize", "target", "task", "technique",
    "transformation", "transition", "trend", "underlying", "utilize",
    "valid", "variable", "verify", "vision", "volume",
    "access", "accurate", "acknowledge", "acquire", "acute",
    "aggregate", "align", "allocate", "ambiguous", "analyze",
    "annual", "anticipate", "apparent", "appropriate", "arbitrary",
    "assess", "assignment", "assume", "assure", "attached",
    "attitude", "background", "balanced", "barrier", "behavior",
    "capital", "challenge", "channel", "characteristic", "classify",
    "coefficient", "coherent", "collaborate", "commence", "commit",
    "comparable", "compatible", "compel", "competent", "compile",
    "complement", "complex", "compliant", "comprehensive", "concentrate",
    "conclusion", "configure", "confine", "confirm", "confront",
    "controversy", "convince", "correlate", "crucial", "currency",
    "data", "debate", "dedicate", "define", "degrade", "demand",
    "describe", "designate", "detect", "devote", "digital",
    "dimension", "direct", "discrete", "draft", "dynamic",
    "elaborate", "eliminate", "emphasize", "empirical", "engage",
    "entity", "estimate", "eventually", "exhibit", "expertise",
    "explicit", "explore", "external", "facilitate", "feedback",
    "format", "formula", "framework", "frequency", "genuine",
    "guarantee", "guideline", "hierarchy", "highlight", "identify",
    "immense", "implement", "implicit", "impose", "inherent",
    "input", "insight", "instance", "interact", "internal",
    "interpret", "introduce", "involve", "isolate", "issue",
    "justify", "label", "layer", "logic", "maximize",
    "minimize", "mutual", "negative", "objective", "optimal",
    "organize", "parallel", "pattern", "phase", "physical",
    "position", "precise", "predict", "prefer", "preliminary",
    "prescribe", "preserve", "process", "promote", "propose",
    "protocol", "ratio", "recognize", "recommend", "recover",
    "refine", "reinforce", "release", "rely", "remove",
    "report", "require", "restrict", "review", "revise",
    "schedule", "scope", "select", "sequence", "simulate",
    "specify", "standard", "stimulate", "submit", "terminate",
    "theory", "transfer", "transform", "uniform", "update",
    "validate", "version", "achieve", "allocate", "analyze",
})

# Backward compatibility alias
HIGH_FREQ_WORDS = BASIC_WORDS


def calculate_vocabulary_score(words: list[str]) -> float:
    """Score vocabulary using 3-tier word frequency.

    Args:
        words: List of words (already tokenized).

    Returns:
        Score 0-100.
    """
    if not words:
        return 0.0
    lower_words = [w.lower() for w in words if w.isalpha()]
    if not lower_words:
        return 0.0
    basic = sum(1 for w in lower_words if w in BASIC_WORDS)
    intermediate = sum(1 for w in lower_words if w in INTERMEDIATE_WORDS)
    advanced = len(lower_words) - basic - intermediate
    # Score: basic=0.3, intermediate=0.6, advanced=1.0 (normalized)
    score = (basic * 0.3 + intermediate * 0.6 + advanced * 1.0) / len(lower_words)
    return min(score * 100, 100.0)


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

    return calculate_vocabulary_score(words)
