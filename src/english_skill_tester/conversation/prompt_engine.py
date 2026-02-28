"""CEFR-based prompt template engine for English conversation sessions."""

from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "config" / "prompts"


@lru_cache(maxsize=1)
def _load_yaml(filename: str) -> dict:
    path = PROMPTS_DIR / filename
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class PromptEngine:
    """CEFR × トピック × 訂正スタイルの組み合わせでプロンプト生成"""

    CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

    def build_prompt(
        self,
        cefr: str = "B1",
        topic: str | None = None,
        scenario: str | None = None,
        user_profile=None,
    ) -> str:
        cefr = cefr.upper() if cefr else "B1"
        if cefr not in self.CEFR_LEVELS:
            cefr = "B1"

        parts = []

        # 1. CEFR基本テンプレート (levels.yaml)
        levels = _load_yaml("levels.yaml")
        if cefr in levels:
            parts.append(levels[cefr].get("system_prompt", ""))

        # 2. 言語調整ルール (scaffolding.yaml)
        scaffolding = _load_yaml("scaffolding.yaml")
        if scaffolding:
            rules = scaffolding.get(cefr, scaffolding.get("default", {}))
            if rules.get("prompt_addition"):
                parts.append(rules["prompt_addition"])

        # 3. トピック/シナリオ (topics.yaml)
        topics = _load_yaml("topics.yaml")
        if topic and topics:
            topic_data = topics.get("topics", {}).get(cefr, [])
            if topic_data:
                parts.append(f"Today's topic pool: {', '.join(topic_data[:5])}")
        if scenario and topics:
            scenario_data = topics.get("scenarios", {}).get(scenario)
            if scenario_data:
                parts.append(f"Role-play scenario: {scenario_data}")

        # 4. 訂正戦略 (corrections.yaml)
        corrections = _load_yaml("corrections.yaml")
        if corrections:
            corr = corrections.get(cefr, corrections.get("default", {}))
            if corr.get("prompt_addition"):
                parts.append(corr["prompt_addition"])

        # 5. ユーザープロファイルパーソナライズ
        if user_profile:
            if user_profile.weak_grammar_points:
                parts.append(
                    f"Focus on these grammar points the user struggles with: "
                    f"{', '.join(user_profile.weak_grammar_points[:3])}"
                )
            if user_profile.interests:
                parts.append(
                    f"User interests: {', '.join(user_profile.interests[:3])}. "
                    "Incorporate these into conversation when natural."
                )

        return "\n\n".join(p for p in parts if p)


_engine = PromptEngine()


def get_prompt_engine() -> PromptEngine:
    return _engine
