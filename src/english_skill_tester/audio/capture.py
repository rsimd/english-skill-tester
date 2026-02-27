"""Microphone audio capture using sounddevice."""

import asyncio
import queue
from collections.abc import AsyncIterator

import numpy as np
import sounddevice as sd
import structlog

logger = structlog.get_logger()


class AudioCapture:
    """Captures audio from microphone and yields chunks asynchronously.

    Args:
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels.
        chunk_size: Number of samples per chunk.
        device: Input device index (None for default).
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
        # Thread-safe queue for audio callback (called from audio thread)
        self._thread_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        # Asyncio queue for async iteration (populated from audio thread via loop.call_soon_threadsafe)
        self._asyncio_queue: asyncio.Queue[np.ndarray] = asyncio.Queue(maxsize=200)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream: sd.InputStream | None = None
        self._running = False

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """Sounddevice callback - pushes audio to thread-safe queue."""
        if status:
            logger.warning("audio_capture_status", status=str(status))
        if self._running:
            chunk = indata.copy().flatten()
            try:
                self._thread_queue.put_nowait(chunk)
            except queue.Full:
                pass  # Drop frame rather than block audio thread
            # Also push to asyncio queue (thread-safe via call_soon_threadsafe)
            if self._loop is not None:
                try:
                    self._loop.call_soon_threadsafe(self._asyncio_queue.put_nowait, chunk)
                except asyncio.QueueFull:
                    pass  # Drop frame rather than block audio thread

    def start(self) -> None:
        """Start capturing audio from microphone."""
        if self._running:
            return
        self._running = True
        # Capture event loop for thread-safe asyncio queue operations
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("audio_capture_start_failed", reason="No running event loop")
            raise
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocksize=self.chunk_size,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()
        logger.info(
            "audio_capture_started",
            sample_rate=self.sample_rate,
            device=self.device,
        )

    def stop(self) -> None:
        """Stop capturing audio."""
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        logger.info("audio_capture_stopped")

    async def chunks(self) -> AsyncIterator[np.ndarray]:
        """Async iterator yielding audio chunks.

        Uses asyncio.Queue for immediate chunk delivery (no polling delay).
        """
        while self._running:
            chunk = await self._asyncio_queue.get()
            yield chunk
