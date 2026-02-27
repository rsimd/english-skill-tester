"""Post-session feedback generation using LLM."""

import json

import structlog
from openai import AsyncOpenAI

from english_skill_tester.models.assessment import AssessmentResult, score_to_ielts, score_to_toeic

logger = structlog.get_logger()

FEEDBACK_PROMPT = """\
You are an expert English language tutor providing feedback after a conversation practice session.

Given the conversation transcript and assessment scores, provide detailed, constructive feedback.

Assessment scores (0-100):
- Vocabulary: {vocabulary}
- Grammar: {grammar}
- Fluency: {fluency}
- Comprehension: {comprehension}
- Coherence: {coherence}
- Overall: {overall}
- Estimated TOEIC: {toeic}
- Estimated IELTS: {ielts}

Respond with a JSON object:
{{
    "summary": "<2-3 sentence overall assessment>",
    "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "weaknesses": ["<area 1>", "<area 2>", "<area 3>"],
    "advice": [
        "<specific, actionable advice 1>",
        "<specific, actionable advice 2>",
        "<specific, actionable advice 3>"
    ],
    "example_corrections": [
        {{"original": "<sentence>", "corrected": "<improved>", "explanation": "<why>"}}
    ]
}}

Be encouraging but honest. Focus on the most impactful improvements.
"""


class FeedbackGenerator:
    """Generates comprehensive post-session feedback.

    Args:
        api_key: OpenAI API key.
        model: Model to use for feedback generation.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(
        self,
        transcript: list[dict[str, str]],
        assessment: AssessmentResult,
    ) -> dict:
        """Generate feedback for a completed session.

        Args:
            transcript: Full conversation transcript.
            assessment: Final assessment result.

        Returns:
            Feedback dict with summary, strengths, weaknesses, advice.
        """
        scores = assessment.components
        formatted_transcript = "\n".join(
            f"{'User' if t['role'] == 'user' else 'AI'}: {t['text']}"
            for t in transcript
        )

        prompt = FEEDBACK_PROMPT.format(
            vocabulary=scores.vocabulary,
            grammar=scores.grammar,
            fluency=scores.fluency,
            comprehension=scores.comprehension,
            coherence=scores.coherence,
            overall=assessment.overall_score,
            toeic=score_to_toeic(assessment.overall_score),
            ielts=score_to_ielts(assessment.overall_score),
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Transcript:\n{formatted_transcript}"},
                ],
                temperature=0.5,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            logger.info("feedback_generated")
            return result

        except Exception:
            logger.exception("feedback_generation_failed")
            return {
                "summary": "Unable to generate detailed feedback. Please try again.",
                "strengths": [],
                "weaknesses": [],
                "advice": ["Continue practicing regular English conversation."],
                "example_corrections": [],
            }
