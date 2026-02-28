"""Adaptive conversation strategy based on real-time skill assessment."""

import time

import structlog

from english_skill_tester.conversation.prompt_engine import get_prompt_engine
from english_skill_tester.conversation.prompts import build_system_prompt
from english_skill_tester.models.session import SkillLevel

logger = structlog.get_logger()


class ConversationStrategy:
    """Manages adaptive conversation difficulty.

    Tracks score changes and triggers prompt updates when the user's
    estimated level changes. Includes hysteresis (2 consecutive same-level
    suggestions required) and cooldown (60 s between changes) to avoid
    rapid oscillation.
    """

    def __init__(self) -> None:
        self._current_level: SkillLevel = SkillLevel.INTERMEDIATE
        self._context: str = ""
        self._level_change_callbacks: list = []
        self._prompt_engine = get_prompt_engine()
        self._consecutive_same_level: int = 0
        self._pending_level: SkillLevel | None = None
        self._last_level_change_time: float | None = None
        self._hysteresis_count: int = 2
        self._level_cooldown_sec: float = 60.0
        self._initial_assessment_done: bool = False
        self._utterance_count: int = 0

    @property
    def current_level(self) -> SkillLevel:
        return self._current_level

    @property
    def current_prompt(self) -> str:
        return build_system_prompt(self._current_level.value, self._context)

    def on_level_change(self, callback) -> None:
        """Register a callback for level changes.

        Args:
            callback: Async callable(new_level, new_prompt).
        """
        self._level_change_callbacks.append(callback)

    async def update_score(self, score: float) -> bool:
        """Update strategy based on new score.

        Applies hysteresis (2 consecutive same-level suggestions) and a
        60-second cooldown between level changes.  Also fires an initial
        prompt update after the first 5 utterances.

        Args:
            score: Overall score 0-100.

        Returns:
            True if level changed.
        """
        self._utterance_count += 1

        # Initial assessment: after 5 utterances fire prompt update once
        if self._utterance_count == 5 and not self._initial_assessment_done:
            self._initial_assessment_done = True
            init_prompt = self._prompt_engine.build_prompt(cefr=self._current_level.cefr)
            for callback in self._level_change_callbacks:
                await callback(self._current_level, init_prompt)

        new_level = SkillLevel.from_score(score)

        # No change needed – reset pending tracking
        if new_level == self._current_level:
            self._pending_level = None
            self._consecutive_same_level = 0
            return False

        # Cooldown: skip if a change was applied recently
        if self._last_level_change_time is not None:
            now = time.monotonic()
            if now - self._last_level_change_time < self._level_cooldown_sec:
                return False

        # Hysteresis: accumulate consecutive same-level suggestions
        if new_level == self._pending_level:
            self._consecutive_same_level += 1
        else:
            self._pending_level = new_level
            self._consecutive_same_level = 1

        if self._consecutive_same_level >= self._hysteresis_count:
            old_level = self._current_level
            self._current_level = new_level
            self._last_level_change_time = time.monotonic()
            self._consecutive_same_level = 0
            self._pending_level = None
            logger.info(
                "level_changed",
                old_level=old_level.value,
                new_level=new_level.value,
                score=score,
            )
            new_prompt = self._prompt_engine.build_prompt(cefr=new_level.cefr)
            for callback in self._level_change_callbacks:
                await callback(new_level, new_prompt)
            return True

        return False

    def set_context(self, context: str) -> None:
        """Update conversation context.

        Args:
            context: New context description.
        """
        self._context = context
