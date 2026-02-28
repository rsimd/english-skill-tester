"""Event type definitions for OpenAI Realtime API."""

from typing import Any

# Client → Server event builders


def session_update_event(
    instructions: str,
    tools: list[dict],
    voice: str = "alloy",
    input_audio_format: str = "pcm16",
    output_audio_format: str = "pcm16",
    temperature: float = 0.8,
    turn_detection: dict[str, Any] | None = None,
    vad_threshold: float = 0.3,
    vad_silence_duration_ms: int = 1000,
) -> dict[str, Any]:
    """Build a session.update event."""
    if turn_detection is None:
        turn_detection = {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": 500,
            "silence_duration_ms": vad_silence_duration_ms,
        }
    return {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": instructions,
            "voice": voice,
            "input_audio_format": input_audio_format,
            "output_audio_format": output_audio_format,
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": turn_detection,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        },
    }


def input_audio_buffer_append_event(audio_base64: str) -> dict[str, Any]:
    """Build an input_audio_buffer.append event."""
    return {
        "type": "input_audio_buffer.append",
        "audio": audio_base64,
    }


def input_audio_buffer_commit_event() -> dict[str, Any]:
    """Build an input_audio_buffer.commit event."""
    return {"type": "input_audio_buffer.commit"}


def conversation_item_create_event(role: str, text: str) -> dict[str, Any]:
    """Build a conversation.item.create event for text input."""
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text", "text": text}],
        },
    }


def response_create_event() -> dict[str, Any]:
    """Build a response.create event."""
    return {"type": "response.create"}


def function_call_output_event(call_id: str, output: str) -> dict[str, Any]:
    """Build a conversation.item.create event for function call output."""
    return {
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
        },
    }
