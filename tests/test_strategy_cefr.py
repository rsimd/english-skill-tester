"""Tests for ConversationStrategy CEFR-enhanced features (I-003, A-001, A-002)."""

from unittest.mock import AsyncMock

from english_skill_tester.conversation.strategy import ConversationStrategy
from english_skill_tester.models.session import SkillLevel


def test_skill_level_cefr_property():
    """SkillLevel.cefr returns correct CEFR strings for all values."""
    assert SkillLevel.BEGINNER.cefr == "A1"
    assert SkillLevel.ELEMENTARY.cefr == "A2"
    assert SkillLevel.INTERMEDIATE.cefr == "B1"
    assert SkillLevel.UPPER_INTERMEDIATE.cefr == "B2"
    assert SkillLevel.ADVANCED.cefr == "C1"


async def test_hysteresis_requires_two_consecutive():
    """1回目の同レベル提案ではレベル変更されない。"""
    strategy = ConversationStrategy()
    callback = AsyncMock()
    strategy.on_level_change(callback)

    # ADVANCED score once (from INTERMEDIATE baseline) → should NOT change
    result = await strategy.update_score(85.0)

    assert result is False
    assert strategy.current_level == SkillLevel.INTERMEDIATE
    callback.assert_not_called()


async def test_hysteresis_applies_on_second():
    """2回連続で同レベル提案が来たらレベル変更が適用される。"""
    strategy = ConversationStrategy()
    callback = AsyncMock()
    strategy.on_level_change(callback)

    # First ADVANCED suggestion: no change
    await strategy.update_score(85.0)
    assert strategy.current_level == SkillLevel.INTERMEDIATE

    # Second ADVANCED suggestion: change applied
    result = await strategy.update_score(90.0)

    assert result is True
    assert strategy.current_level == SkillLevel.ADVANCED
    # callback called exactly once (for the level change)
    assert callback.call_count == 1
    called_level, _ = callback.call_args[0]
    assert called_level == SkillLevel.ADVANCED


async def test_cooldown_prevents_rapid_change(monkeypatch):
    """変更後60秒クールダウン中はレベルが変更されない。"""
    current_time = [0.0]
    monkeypatch.setattr(
        "english_skill_tester.conversation.strategy.time.monotonic",
        lambda: current_time[0],
    )

    strategy = ConversationStrategy()
    callback = AsyncMock()
    strategy.on_level_change(callback)

    # Apply first change: 2 consecutive ADVANCED suggestions
    await strategy.update_score(85.0)
    result = await strategy.update_score(90.0)
    assert result is True
    assert strategy.current_level == SkillLevel.ADVANCED
    callback.reset_mock()

    # Attempt to revert to INTERMEDIATE during cooldown (time still 0)
    await strategy.update_score(50.0)
    result = await strategy.update_score(45.0)

    assert result is False
    assert strategy.current_level == SkillLevel.ADVANCED  # unchanged
    callback.assert_not_called()
