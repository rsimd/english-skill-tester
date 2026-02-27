"""PCM16 audio encoding/decoding utilities for OpenAI Realtime API."""

import base64

import numpy as np


def pcm16_to_base64(audio: np.ndarray) -> str:
    """Convert float32 numpy audio to base64-encoded PCM16.

    Args:
        audio: Float32 audio array in range [-1.0, 1.0].

    Returns:
        Base64 encoded PCM16 string.
    """
    pcm16 = (audio * 32767).astype(np.int16)
    return base64.b64encode(pcm16.tobytes()).decode("ascii")


def base64_to_pcm16(data: str) -> np.ndarray:
    """Convert base64-encoded PCM16 to float32 numpy audio.

    Args:
        data: Base64 encoded PCM16 string.

    Returns:
        Float32 audio array in range [-1.0, 1.0].
    """
    pcm_bytes = base64.b64decode(data)
    pcm16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    return pcm16.astype(np.float32) / 32767.0
