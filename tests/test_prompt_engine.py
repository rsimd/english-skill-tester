"""Tests for PromptEngine - CEFR-based prompt generation."""

from english_skill_tester.conversation.prompt_engine import PromptEngine, get_prompt_engine


def test_build_prompt_default():
    """デフォルトでプロンプト文字列が返る"""
    engine = PromptEngine()
    result = engine.build_prompt()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_prompt_per_cefr():
    """A1〜C2各レベルでプロンプトが異なる"""
    engine = PromptEngine()
    prompts = {level: engine.build_prompt(cefr=level) for level in PromptEngine.CEFR_LEVELS}
    # Each level should produce a non-empty string
    for level, prompt in prompts.items():
        assert isinstance(prompt, str), f"Level {level} returned non-string"
        assert len(prompt) > 0, f"Level {level} returned empty prompt"
    # Prompts should differ across levels
    unique_prompts = set(prompts.values())
    assert len(unique_prompts) > 1, "All CEFR levels produced identical prompts"


def test_invalid_cefr_fallback():
    """不正なCEFR値でB1にフォールバック"""
    engine = PromptEngine()
    b1_prompt = engine.build_prompt(cefr="B1")
    invalid_prompt = engine.build_prompt(cefr="Z9")
    assert invalid_prompt == b1_prompt, "Invalid CEFR should fall back to B1"


def test_get_prompt_engine_singleton():
    """get_prompt_engine() returns consistent instance"""
    engine1 = get_prompt_engine()
    engine2 = get_prompt_engine()
    assert engine1 is engine2
