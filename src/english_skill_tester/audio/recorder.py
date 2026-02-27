"""Bidirectional audio recorder for session archival."""

import wave
from pathlib import Path

import numpy as np
import structlog

logger = structlog.get_logger()


class AudioRecorder:
    """Records both input (user) and output (AI) audio to WAV files.

    Args:
        output_dir: Directory to save recordings.
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
    """

    def __init__(
        self,
        output_dir: Path,
        sample_rate: int = 24000,
        channels: int = 1,
    ):
        self.output_dir = output_dir
        self.sample_rate = sample_rate
        self.channels = channels
        self._input_chunks: list[np.ndarray] = []
        self._output_chunks: list[np.ndarray] = []
        self._recording = False

    def start(self) -> None:
        """Start recording."""
        self._input_chunks.clear()
        self._output_chunks.clear()
        self._recording = True
        logger.info("recorder_started")

    def stop(self) -> None:
        """Stop recording."""
        self._recording = False
        logger.info("recorder_stopped")

    def record_input(self, audio: np.ndarray) -> None:
        """Record an input (user microphone) audio chunk."""
        if self._recording:
            self._input_chunks.append(audio.copy())

    def record_output(self, audio: np.ndarray) -> None:
        """Record an output (AI speaker) audio chunk."""
        if self._recording:
            self._output_chunks.append(audio.copy())

    def save(self, session_id: str) -> dict[str, Path]:
        """Save recorded audio to WAV files.

        Args:
            session_id: Session identifier for file naming.

        Returns:
            Dict with paths to saved files.
        """
        paths: dict[str, Path] = {}
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for label, chunks in [("input", self._input_chunks), ("output", self._output_chunks)]:
            if not chunks:
                continue
            audio = np.concatenate(chunks)
            path = self.output_dir / f"{session_id}_{label}.wav"
            self._write_wav(path, audio)
            paths[label] = path
            logger.info("recording_saved", path=str(path), duration_s=len(audio) / self.sample_rate)

        # Also save mixed version
        if self._input_chunks and self._output_chunks:
            input_audio = np.concatenate(self._input_chunks)
            output_audio = np.concatenate(self._output_chunks)
            max_len = max(len(input_audio), len(output_audio))
            input_padded = np.pad(input_audio, (0, max_len - len(input_audio)))
            output_padded = np.pad(output_audio, (0, max_len - len(output_audio)))
            mixed = (input_padded + output_padded) / 2.0
            path = self.output_dir / f"{session_id}_mixed.wav"
            self._write_wav(path, mixed)
            paths["mixed"] = path

        return paths

    def _write_wav(self, path: Path, audio: np.ndarray) -> None:
        """Write audio array to WAV file."""
        pcm16 = (audio * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm16.tobytes())
