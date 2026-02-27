"""LLM-based periodic evaluation for comprehension and coherence."""

import json

import structlog
from openai import AsyncOpenAI

from english_skill_tester.models.assessment import ComponentScores

logger = structlog.get_logger()

EVAL_SYSTEM_PROMPT = """\
You are an expert English language assessor. Analyze the following conversation \
transcript between a user (language learner) and an AI conversation partner.

Evaluate the USER's English ability on these dimensions (score each 0-100):

1. **comprehension**: How well does the user understand what's being said? \
   Do they respond appropriately? Do they miss meanings or misinterpret questions?

2. **coherence**: How logically structured are the user's responses? \
   Do they stay on topic? Are their ideas well-organized and connected?

3. **pronunciation_proxy**: Based on transcript artifacts (unusual spellings, \
   misheard words), estimate pronunciation quality. If transcript seems clean, \
   score higher.

4. **vocabulary**: Assess vocabulary range and appropriateness. \
   Does the user use varied and contextually appropriate words?

5. **grammar**: Assess grammatical accuracy and complexity. \
   Does the user form correct sentences? Do they use complex structures?

Respond ONLY with a JSON object:
{
    "comprehension": <0-100>,
    "coherence": <0-100>,
    "pronunciation_proxy": <0-100>,
    "vocabulary": <0-100>,
    "grammar": <0-100>,
    "reasoning": "<brief explanation>"
}
"""


class LLMEvaluator:
    """Uses LLM to evaluate comprehension, coherence, and pronunciation.

    Args:
        api_key: OpenAI API key.
        model: Model to use for evaluation.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def evaluate(
        self,
        transcript: list[dict[str, str]],
    ) -> ComponentScores:
        """Evaluate conversation transcript using LLM.

        Args:
            transcript: List of {"role": "user"|"assistant", "text": "..."}.

        Returns:
            ComponentScores with all fields filled from LLM assessment.
        """
        if not transcript:
            return ComponentScores()

        # Format transcript for the prompt
        formatted = "\n".join(
            f"{'User' if t['role'] == 'user' else 'AI'}: {t['text']}"
            for t in transcript
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EVAL_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Transcript:\n{formatted}"},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.info("llm_evaluation_complete", result=result)

            return ComponentScores(
                comprehension=float(result.get("comprehension", 50)),
                coherence=float(result.get("coherence", 50)),
                pronunciation_proxy=float(result.get("pronunciation_proxy", 50)),
                vocabulary=float(result.get("vocabulary", 50)),
                grammar=float(result.get("grammar", 50)),
            )

        except Exception:
            logger.exception("llm_evaluation_failed")
            return ComponentScores()
