"""Adaptive conversation strategy based on real-time skill assessment."""

import structlog

from english_skill_tester.conversation.prompts import build_system_prompt
from english_skill_tester.models.session import SkillLevel

logger = structlog.get_logger()


class ConversationStrategy:
    """Manages adaptive conversation difficulty.

    Tracks score changes and triggers prompt updates when the user's
    estimated level changes.
    """

    def __init__(self) -> None:
        self._current_level: SkillLevel = SkillLevel.INTERMEDIATE
        self._context: str = ""
        self._level_change_callbacks: list = []

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

        Args:
            score: Overall score 0-100.

        Returns:
            True if level changed.
        """
        new_level = SkillLevel.from_score(score)
        if new_level != self._current_level:
            old_level = self._current_level
            self._current_level = new_level
            logger.info(
                "level_changed",
                old_level=old_level.value,
                new_level=new_level.value,
                score=score,
            )
            new_prompt = self.current_prompt
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
