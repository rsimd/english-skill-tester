"""Browser WebSocket handler - central hub connecting all components."""

import asyncio
import json
import random
import time
import uuid
from datetime import datetime

import numpy as np
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from english_skill_tester.analysis.feedback import FeedbackGenerator
from english_skill_tester.analysis.transcript import highlight_transcript
from english_skill_tester.assessment.calibration import get_full_mapping
from english_skill_tester.assessment.scorer import HybridScorer
from english_skill_tester.audio.capture import AudioCapture
from english_skill_tester.audio.encoder import base64_to_pcm16, pcm16_to_base64
from english_skill_tester.audio.playback import AudioPlayback
from english_skill_tester.audio.recorder import AudioRecorder
from english_skill_tester.config import Settings
from english_skill_tester.conversation.strategy import ConversationStrategy
from english_skill_tester.models.assessment import score_to_ielts, score_to_toeic
from english_skill_tester.models.session import Session, SessionStatus
from english_skill_tester.realtime.client import RealtimeClient

logger = structlog.get_logger()


class GestureController:
    """Rule-based gesture triggering based on conversation events."""

    def __init__(self, send_fn):
        self._send = send_fn  # _send_to_browser
        self._last_gesture_time = 0
        self._min_interval = 3.0  # 最小ジェスチャー間隔（秒）

    async def on_session_start(self):
        await self._trigger("wave")

    async def on_user_finished_speaking(self):
        await self._trigger("nod")

    async def on_ai_response_long(self):
        """AI応答が2文以上の時"""
        gesture = random.choice(["explain", "open_palms", "point"])
        await self._trigger(gesture)

    async def on_high_score(self):
        gesture = random.choice(["thumbs_up", "celebration"])
        await self._trigger(gesture)

    async def on_silence(self):
        """5秒以上沈黙"""
        await self._trigger("listen")

    async def on_question_asked(self):
        await self._trigger("thinking_pose")

    def analyze_context(self, text: str) -> str | None:
        """Analyze AI transcript and return appropriate gesture."""
        text_lower = text.lower()

        if any(word in text_lower for word in ["think", "well...", "let me"]):
            return "thinking_pose"
        if any(word in text_lower for word in ["great!", "excellent!", "good job"]):
            return random.choice(["thumbs_up", "celebration"])
        if any(word in text_lower for word in ["don't know", "not sure"]):
            return "shrug"
        if "?" in text:
            return "lean_forward"
        if len(text.split()) > 50:
            return random.choice(["explain", "open_palms"])
        if any(word in text_lower for word in ["hello", "hi", "goodbye"]):
            return "wave"
        return None

    async def _trigger(self, gesture):
        now = time.time()
        if now - self._last_gesture_time < self._min_interval:
            return
        self._last_gesture_time = now
        await self._send({
            "type": "character_action",
            "action_type": "gesture",
            "value": gesture,
        })


class SessionManager:
    """Manages a single conversation session with all components.

    Args:
        settings: Application settings.
        browser_ws: WebSocket connection to the browser.
    """

    def __init__(self, settings: Settings, browser_ws: WebSocket):
        self.settings = settings
        self.browser_ws = browser_ws
        self.session = Session(session_id=str(uuid.uuid4()))
        self.strategy = ConversationStrategy()
        self.scorer = HybridScorer(
            api_key=settings.openai_api_key,
            eval_model=settings.evaluation_model,
            llm_interval_utterances=settings.llm_eval_interval_utterances,
            llm_interval_seconds=settings.llm_eval_interval_seconds,
        )
        self.feedback_gen = FeedbackGenerator(
            api_key=settings.openai_api_key,
            model=settings.evaluation_model,
        )
        self.capture = AudioCapture(
            sample_rate=settings.audio_sample_rate,
            channels=settings.audio_channels,
            chunk_size=settings.audio_chunk_size,
            device=settings.audio_input_device,
        )
        self.playback = AudioPlayback(
            sample_rate=settings.audio_sample_rate,
            channels=settings.audio_channels,
            chunk_size=settings.audio_chunk_size,
            device=settings.audio_output_device,
        )
        self.recorder = AudioRecorder(
            output_dir=settings.recordings_dir,
            sample_rate=settings.audio_sample_rate,
        )
        self.realtime = RealtimeClient(
            api_key=settings.openai_api_key,
            model=settings.realtime_model,
        )
        self._tasks: list[asyncio.Task] = []
        self._ai_speaking = False
        self.gesture_ctrl = GestureController(self._send_to_browser)

    async def start(self) -> None:
        """Start the conversation session."""
        self.session.status = SessionStatus.ACTIVE
        logger.info("session_starting", session_id=self.session.session_id)

        self._setup_realtime_handlers()
        self.strategy.on_level_change(self._on_level_change)

        initial_prompt = self.strategy.current_prompt
        await self.realtime.connect(initial_prompt)

        self.capture.start()
        self.playback.start()
        self.recorder.start()

        self._tasks = [
            asyncio.create_task(self._audio_send_loop()),
            asyncio.create_task(self.realtime.receive_loop()),
            asyncio.create_task(self._score_update_loop()),
        ]

        await self.gesture_ctrl.on_session_start()

        await self._send_to_browser({
            "type": "session_state",
            "status": "active",
            "session_id": self.session.session_id,
        })

    async def stop(self) -> None:
        """Stop the conversation session and generate feedback."""
        logger.info("session_stopping", session_id=self.session.session_id)

        self.capture.stop()
        self.playback.stop()
        self.recorder.stop()
        await self.realtime.disconnect()

        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        self.session.status = SessionStatus.COMPLETED
        self.session.ended_at = datetime.now()

        recording_paths = self.recorder.save(self.session.session_id)
        if recording_paths:
            self.session.recording_path = str(
                recording_paths.get("mixed", "")
            )

        await self._generate_and_send_feedback()
        await self._save_session()

        await self._send_to_browser({
            "type": "session_state",
            "status": "completed",
            "session_id": self.session.session_id,
        })

    def _setup_realtime_handlers(self) -> None:
        """Register handlers for Realtime API events."""

        async def on_audio_delta(event: dict) -> None:
            audio_b64 = event.get("delta", "")
            if audio_b64:
                audio = base64_to_pcm16(audio_b64)
                await self.playback.play(audio)
                self.recorder.record_output(audio)
                # Send audio level for lip sync
                level = float(np.abs(audio).mean())
                await self._send_to_browser({
                    "type": "audio_level",
                    "level": min(level * 5.0, 1.0),
                })

        async def on_response_started(event: dict) -> None:
            self._ai_speaking = True
            await self._send_to_browser({"type": "ai_speaking", "speaking": True})

        async def on_response_done(event: dict) -> None:
            # Wait for playback buffer to drain before stopping lip sync
            await asyncio.sleep(0.3)
            if self._ai_speaking:  # Check if new response has started
                self._ai_speaking = False
                await self._send_to_browser({"type": "ai_speaking", "speaking": False})
                await self._send_to_browser({"type": "audio_level", "level": 0})

        async def on_speech_started(event: dict) -> None:
            """User started speaking — clear AI audio buffer."""
            if self._ai_speaking:
                self.playback.clear()
                self._ai_speaking = False
                logger.debug("ai_audio_interrupted_by_user")

        async def on_user_transcript(event: dict) -> None:
            transcript = event.get("transcript", "")
            if transcript and transcript.strip():
                self.session.add_utterance("user", transcript)
                await self._send_to_browser({
                    "type": "transcript",
                    "role": "user",
                    "text": transcript,
                })
                logger.info("user_said", text=transcript[:80])
                await self.gesture_ctrl.on_user_finished_speaking()

        async def on_ai_transcript(event: dict) -> None:
            transcript = event.get("transcript", "")
            if transcript and transcript.strip():
                self.session.add_utterance("assistant", transcript)
                await self._send_to_browser({
                    "type": "transcript",
                    "role": "assistant",
                    "text": transcript,
                })
                # Trigger context-based gesture
                gesture = self.gesture_ctrl.analyze_context(transcript)
                if gesture:
                    await self.gesture_ctrl._trigger(gesture)

        async def on_function_call(event: dict) -> None:
            name = event.get("name", "")
            args = json.loads(event.get("arguments", "{}"))
            if name == "set_expression":
                await self._send_to_browser({
                    "type": "character_action",
                    "action_type": "expression",
                    "value": args.get("expression", "neutral"),
                })
            elif name == "play_gesture":
                await self._send_to_browser({
                    "type": "character_action",
                    "action_type": "gesture",
                    "value": args.get("gesture", "nod"),
                })

        self.realtime.on("response.audio.delta", on_audio_delta)
        self.realtime.on("response.created", on_response_started)
        self.realtime.on("response.done", on_response_done)
        self.realtime.on(
            "input_audio_buffer.speech_started", on_speech_started
        )
        self.realtime.on(
            "conversation.item.input_audio_transcription.completed",
            on_user_transcript,
        )
        self.realtime.on(
            "response.audio_transcript.done", on_ai_transcript
        )
        self.realtime.on(
            "response.function_call_arguments.done", on_function_call
        )

        self.realtime.register_function(
            "set_expression",
            lambda expression: json.dumps(
                {"status": "ok", "expression": expression}
            ),
        )
        self.realtime.register_function(
            "play_gesture",
            lambda gesture: json.dumps(
                {"status": "ok", "gesture": gesture}
            ),
        )

    async def _audio_send_loop(self) -> None:
        """Send microphone audio to Realtime API."""
        try:
            async for chunk in self.capture.chunks():
                self.recorder.record_input(chunk)
                audio_b64 = pcm16_to_base64(chunk)
                await self.realtime.send_audio(audio_b64)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("audio_send_loop_error")

    async def _score_update_loop(self) -> None:
        """Periodically compute and send score updates."""
        try:
            while True:
                await asyncio.sleep(
                    self.settings.score_update_interval_seconds
                )
                if self.session.user_utterances:
                    result = await self.scorer.update(self.session)
                    mapping = get_full_mapping(result.overall_score)

                    await self.strategy.update_score(
                        result.overall_score
                    )
                    self.session.current_level = (
                        self.strategy.current_level
                    )

                    scores = result.components
                    await self._send_to_browser({
                        "type": "score_update",
                        "overall": round(result.overall_score, 1),
                        "vocabulary": scores.vocabulary,
                        "grammar": scores.grammar,
                        "fluency": scores.fluency,
                        "comprehension": scores.comprehension,
                        "coherence": scores.coherence,
                        "pronunciation_proxy": scores.pronunciation_proxy,
                        "level": mapping["level"],
                        "toeic_estimate": mapping["toeic"],
                        "ielts_estimate": mapping["ielts"],
                    })
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("score_update_loop_error")

    async def _on_level_change(self, new_level, new_prompt: str) -> None:
        """Handle level change by updating Realtime API session."""
        await self.realtime.update_session(new_prompt)
        await self._send_to_browser({
            "type": "level_change",
            "level": new_level.value,
        })

    async def _generate_and_send_feedback(self) -> None:
        """Generate and send post-session feedback."""
        if not self.session.utterances:
            return

        transcript = [
            {"role": u.role, "text": u.text}
            for u in self.session.utterances
            if u.text
        ]

        assessment = self.scorer.latest_result
        feedback = await self.feedback_gen.generate(transcript, assessment)
        highlighted = highlight_transcript(transcript)

        await self._send_to_browser({
            "type": "feedback",
            "summary": feedback.get("summary", ""),
            "strengths": feedback.get("strengths", []),
            "weaknesses": feedback.get("weaknesses", []),
            "advice": feedback.get("advice", []),
            "example_corrections": feedback.get(
                "example_corrections", []
            ),
            "final_score": round(assessment.overall_score, 1),
            "toeic_estimate": score_to_toeic(assessment.overall_score),
            "ielts_estimate": score_to_ielts(assessment.overall_score),
            "transcript": highlighted,
        })

    async def _save_session(self) -> None:
        """Save session data to JSON file."""
        path = (
            self.settings.sessions_dir
            / f"{self.session.session_id}.json"
        )
        data = self.session.model_dump_json(indent=2)
        path.write_text(data)
        logger.info("session_saved", path=str(path))

    async def _send_to_browser(self, data: dict) -> None:
        """Send a message to the browser WebSocket."""
        try:
            await self.browser_ws.send_json(data)
        except Exception:
            logger.warning("browser_send_failed")


async def handle_browser_websocket(
    websocket: WebSocket, settings: Settings
) -> None:
    """Handle a browser WebSocket connection."""
    await websocket.accept()
    session_mgr: SessionManager | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "start_session":
                if session_mgr:
                    await session_mgr.stop()
                session_mgr = SessionManager(settings, websocket)
                await session_mgr.start()

            elif msg_type == "stop_session":
                if session_mgr:
                    await session_mgr.stop()
                    session_mgr = None

    except WebSocketDisconnect:
        logger.info("browser_disconnected")
    except Exception:
        logger.exception("websocket_handler_error")
    finally:
        if session_mgr:
            try:
                await session_mgr.stop()
            except Exception:
                pass
