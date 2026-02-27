"""Speaker audio playback using sounddevice blocking write in a dedicated thread."""

import queue
import threading

import numpy as np
import sounddevice as sd
import structlog

logger = structlog.get_logger()

# Sentinel to signal the thread to stop
_STOP = None


class AudioPlayback:
    """Plays audio through speaker using a dedicated writer thread.

    Uses sd.OutputStream.write() in blocking mode for reliable
    streaming playback without callback timing issues.

    Args:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        device: Output device index (None for default).
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        channels: int = 1,
        chunk_size: int = 2400,
        device: int | None = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.device = device
        self._queue: queue.Queue[np.ndarray | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        """Whether audio is currently being played (AI speaking)."""
        return self._is_playing

    def start(self) -> None:
        """Start the playback thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._thread.start()
        logger.info(
            "audio_playback_started",
            sample_rate=self.sample_rate,
            device=self.device,
        )

    def stop(self) -> None:
        """Stop playback and join the thread."""
        self._running = False
        self._is_playing = False
        # Signal thread to exit
        self._queue.put(_STOP)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        # Drain queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        logger.info("audio_playback_stopped")

    def clear(self) -> None:
        """Clear buffered audio (e.g. when AI response is interrupted)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
        self._is_playing = False

    async def play(self, audio: np.ndarray) -> None:
        """Queue audio for playback.

        Args:
            audio: Float32 audio array.
        """
        if self._running:
            self._is_playing = True
            self._queue.put(audio)

    def _writer_loop(self) -> None:
        """Background thread: pull audio from queue, write to stream."""
        try:
            stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self.chunk_size,
                device=self.device,
            )
            stream.start()
        except Exception:
            logger.exception("audio_stream_open_failed")
            return

        try:
            while self._running:
                try:
                    chunk = self._queue.get(timeout=0.1)
                except queue.Empty:
                    self._is_playing = False
                    continue

                if chunk is _STOP:
                    break

                # Write in blocksize pieces for smooth output
                data = chunk.reshape(-1, 1) if chunk.ndim == 1 else chunk
                try:
                    stream.write(data)
                except sd.PortAudioError:
                    logger.warning("audio_write_error")
        except Exception:
            logger.exception("audio_writer_loop_error")
        finally:
            self._is_playing = False
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
