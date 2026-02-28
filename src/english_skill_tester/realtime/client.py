"""OpenAI Realtime API WebSocket client."""

import asyncio
import json
from collections.abc import Callable, Coroutine
from typing import Any

import structlog
import websockets
from websockets.asyncio.client import ClientConnection

from english_skill_tester.realtime.events import (
    conversation_item_create_event,
    function_call_output_event,
    input_audio_buffer_append_event,
    response_create_event,
    session_update_event,
)
from english_skill_tester.realtime.tools import REALTIME_TOOLS

logger = structlog.get_logger()

REALTIME_API_URL = "wss://api.openai.com/v1/realtime"

# Type alias for event handler callbacks
EventHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class RealtimeClient:
    """WebSocket client for OpenAI Realtime API.

    Args:
        api_key: OpenAI API key.
        model: Realtime model identifier.
    """

    def __init__(self, api_key: str, model: str = "gpt-realtime-1.5"):
        self.api_key = api_key
        self.model = model
        self._ws: ClientConnection | None = None
        self._running = False
        self._event_handlers: dict[str, list[EventHandler]] = {}
        self._function_handlers: dict[str, Callable[..., str]] = {}

        # Transcript accumulation
        self._current_transcript = ""
        self._current_audio_chunks: list[str] = []

        # Reconnection state
        self._instructions: str | None = None

    def on(self, event_type: str, handler: EventHandler) -> None:
        """Register an event handler for a specific event type.

        Args:
            event_type: The Realtime API event type to handle.
            handler: Async callback function.
        """
        self._event_handlers.setdefault(event_type, []).append(handler)

    def register_function(self, name: str, handler: Callable[..., str]) -> None:
        """Register a function call handler.

        Args:
            name: Function name matching tool definition.
            handler: Function that takes kwargs and returns string result.
        """
        self._function_handlers[name] = handler

    async def connect(self, instructions: str) -> None:
        """Connect to the Realtime API and configure the session.

        Args:
            instructions: System instructions for the AI.
        """
        self._instructions = instructions  # Save for reconnection
        url = f"{REALTIME_API_URL}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        self._ws = await websockets.connect(url, additional_headers=headers)
        self._running = True
        logger.info("realtime_connected", model=self.model)

        # Configure session
        config = session_update_event(instructions=instructions, tools=REALTIME_TOOLS)
        await self._send(config)

    async def disconnect(self) -> None:
        """Disconnect from the Realtime API."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("realtime_disconnected")

    async def send_audio(self, audio_base64: str) -> None:
        """Send audio data to the Realtime API.

        Args:
            audio_base64: Base64-encoded PCM16 audio.
        """
        await self._send(input_audio_buffer_append_event(audio_base64))

    async def update_session(self, instructions: str) -> None:
        """Update the session with new instructions (for adaptive difficulty).

        Args:
            instructions: New system instructions.
        """
        self._instructions = instructions  # Update for future reconnections
        config = session_update_event(instructions=instructions, tools=REALTIME_TOOLS)
        await self._send(config)
        logger.info("session_updated")

    async def receive_loop(self) -> None:
        """Main loop to receive and dispatch events from the Realtime API.

        Implements automatic reconnection with exponential backoff on connection loss.
        """
        if not self._ws:
            raise RuntimeError("Not connected")

        reconnect_attempts = 0
        max_attempts = 5
        backoff_delays = [0, 1, 2, 4, 8]

        while self._running:
            try:
                async for message in self._ws:
                    if not self._running:
                        break
                    event = json.loads(message)
                    await self._dispatch(event)
                break  # Normal exit when connection closes gracefully

            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "realtime_connection_closed",
                    attempt=reconnect_attempts + 1,
                    max_attempts=max_attempts,
                )

                # Check if we've exhausted retry attempts
                if reconnect_attempts >= max_attempts:
                    logger.error("realtime_reconnect_failed", attempts=reconnect_attempts)
                    # Notify browser of permanent failure
                    await self._dispatch({
                        "type": "session_state",
                        "status": "error",
                        "reason": "connection_lost",
                    })
                    break

                # Apply exponential backoff delay
                delay = backoff_delays[reconnect_attempts]
                if delay > 0:
                    logger.info(
                        "realtime_reconnecting",
                        delay_seconds=delay,
                        attempt=reconnect_attempts + 1,
                    )
                    await asyncio.sleep(delay)

                # Attempt to re-establish connection
                try:
                    url = f"{REALTIME_API_URL}?model={self.model}"
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "OpenAI-Beta": "realtime=v1",
                    }
                    self._ws = await websockets.connect(url, additional_headers=headers)
                    logger.info("realtime_reconnected", attempt=reconnect_attempts + 1)

                    # Re-send session configuration
                    if self._instructions:
                        config = session_update_event(
                            instructions=self._instructions,
                            tools=REALTIME_TOOLS,
                        )
                        await self._send(config)
                        logger.info("session_config_resent")

                    # Send conversation context message to maintain continuity
                    context_message = conversation_item_create_event(
                        role="system",
                        text=(
                            "[Connection was temporarily lost and has been "
                            "restored. Continuing conversation.]"
                        ),
                    )
                    await self._send(context_message)

                    # Notify browser of successful reconnection
                    await self._dispatch({"type": "reconnected"})

                    # Reset attempt counter on successful reconnection
                    reconnect_attempts = 0

                except Exception as reconnect_error:
                    logger.exception("realtime_reconnect_error", error=str(reconnect_error))
                    reconnect_attempts += 1
                    # Continue to next iteration to retry

            except Exception:
                logger.exception("realtime_receive_error")
                break

        self._running = False

    async def _send(self, event: dict[str, Any]) -> None:
        """Send an event to the Realtime API."""
        if self._ws:
            await self._ws.send(json.dumps(event))

    async def _dispatch(self, event: dict[str, Any]) -> None:
        """Dispatch a received event to registered handlers."""
        event_type = event.get("type", "")

        # Handle function calls internally
        if event_type == "response.function_call_arguments.done":
            await self._handle_function_call(event)

        # Handle transcript events
        if event_type == "response.audio_transcript.delta":
            delta = event.get("delta", "")
            self._current_transcript += delta

        if event_type == "response.audio_transcript.done":
            self._current_transcript = ""

        # Dispatch to registered handlers
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.exception("event_handler_error", event_type=event_type)

        # Also dispatch to wildcard handlers
        for handler in self._event_handlers.get("*", []):
            try:
                await handler(event)
            except Exception:
                logger.exception("wildcard_handler_error", event_type=event_type)

    async def _handle_function_call(self, event: dict[str, Any]) -> None:
        """Handle a completed function call from the AI."""
        name = event.get("name", "")
        call_id = event.get("call_id", "")
        args_str = event.get("arguments", "{}")

        handler = self._function_handlers.get(name)
        if not handler:
            logger.warning("unknown_function_call", name=name)
            result = '{"error": "unknown function"}'
        else:
            try:
                args = json.loads(args_str)
                result = handler(**args)
                logger.info("function_call_executed", name=name, args=args)
            except Exception as e:
                logger.exception("function_call_error", name=name)
                result = json.dumps({"error": str(e)})

        # Send function result back
        await self._send(function_call_output_event(call_id, result))
        # Trigger a new response after function call
        await self._send(response_create_event())
