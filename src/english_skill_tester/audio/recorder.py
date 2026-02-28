"""Bidirectional audio recorder for session archival."""

import uuid
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
        self._input_file: wave.Wave_write | None = None
        self._output_file: wave.Wave_write | None = None
        self._input_temp_path: Path | None = None
        self._output_temp_path: Path | None = None
        self._recording = False

    def start(self) -> None:
        """Start recording — opens temporary WAV files for streaming write."""
        self._recording = True
        self.output_dir.mkdir(parents=True, exist_ok=True)
        uid = uuid.uuid4().hex[:8]
        self._input_temp_path = self.output_dir / f"_rec_{uid}_input.tmp.wav"
        self._output_temp_path = self.output_dir / f"_rec_{uid}_output.tmp.wav"
        self._input_file = wave.open(str(self._input_temp_path), "wb")
        self._input_file.setnchannels(self.channels)
        self._input_file.setsampwidth(2)  # 16-bit
        self._input_file.setframerate(self.sample_rate)
        self._output_file = wave.open(str(self._output_temp_path), "wb")
        self._output_file.setnchannels(self.channels)
        self._output_file.setsampwidth(2)
        self._output_file.setframerate(self.sample_rate)
        logger.info("recorder_started")

    def stop(self) -> None:
        """Stop recording and finalize WAV files."""
        self._recording = False
        if self._input_file:
            self._input_file.close()
            self._input_file = None
        if self._output_file:
            self._output_file.close()
            self._output_file = None
        logger.info("recorder_stopped")

    def record_input(self, audio: np.ndarray) -> None:
        """Record input audio chunk directly to disk."""
        if self._recording and self._input_file:
            pcm16 = (audio * 32767).astype(np.int16)
            self._input_file.writeframes(pcm16.tobytes())

    def record_output(self, audio: np.ndarray) -> None:
        """Record output audio chunk directly to disk."""
        if self._recording and self._output_file:
            pcm16 = (audio * 32767).astype(np.int16)
            self._output_file.writeframes(pcm16.tobytes())

    def save(self, session_id: str) -> dict[str, Path]:
        """Rename temp files to session-named files and generate mixed track.

        Args:
            session_id: Session identifier for file naming.

        Returns:
            Dict with paths to saved files.
        """
        paths: dict[str, Path] = {}

        if self._input_temp_path and self._input_temp_path.exists():
            dest = self.output_dir / f"{session_id}_input.wav"
            self._input_temp_path.rename(dest)
            paths["input"] = dest
            logger.info("recording_saved", path=str(dest))

        if self._output_temp_path and self._output_temp_path.exists():
            dest = self.output_dir / f"{session_id}_output.wav"
            self._output_temp_path.rename(dest)
            paths["output"] = dest
            logger.info("recording_saved", path=str(dest))

        if "input" in paths and "output" in paths:
            input_audio = self._read_wav(paths["input"])
            output_audio = self._read_wav(paths["output"])
            max_len = max(len(input_audio), len(output_audio))
            input_padded = np.pad(input_audio, (0, max_len - len(input_audio)))
            output_padded = np.pad(output_audio, (0, max_len - len(output_audio)))
            mixed = (
                input_padded.astype(np.float32) / 32767.0
                + output_padded.astype(np.float32) / 32767.0
            ) / 2.0
            mixed_path = self.output_dir / f"{session_id}_mixed.wav"
            self._write_wav(mixed_path, mixed)
            paths["mixed"] = mixed_path

        return paths

    def _read_wav(self, path: Path) -> np.ndarray:
        """Read WAV file to int16 numpy array."""
        with wave.open(str(path), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            return np.frombuffer(frames, dtype=np.int16)

    def _write_wav(self, path: Path, audio: np.ndarray) -> None:
        """Write audio array to WAV file."""
        pcm16 = (audio * 32767).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm16.tobytes())
