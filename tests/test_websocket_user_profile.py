"""Tests for websocket handler - user profile integration (subtask_175i)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from english_skill_tester.api.websocket import SessionManager, handle_browser_websocket
from english_skill_tester.models.user_profile import UserProfile


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.openai_api_key = "test-key"
    settings.evaluation_model = "gpt-4o-mini"
    settings.realtime_model = "gpt-realtime-1.5"
    settings.audio_sample_rate = 24000
    settings.audio_channels = 1
    settings.audio_chunk_size = 2400
    settings.audio_input_device = None
    settings.audio_output_device = None
    settings.vad_threshold = 0.3
    settings.vad_silence_duration_ms = 1000
    settings.llm_eval_interval_utterances = 10
    settings.llm_eval_interval_seconds = 120.0
    settings.score_update_interval_seconds = 3.0
    settings.sessions_dir = MagicMock()
    settings.recordings_dir = MagicMock()
    return settings


class TestStartSessionCreatesProfile:
    def test_session_manager_stores_user_id_and_profile(self, mock_settings):
        """SessionManager correctly stores user_id and user_profile."""
        ws = MagicMock(spec=WebSocket)
        profile = UserProfile(user_id="test_user")

        mgr = SessionManager(
            mock_settings, ws, user_id="test_user", user_profile=profile
        )

        assert mgr.user_id == "test_user"
        assert mgr.user_profile is profile

    def test_session_manager_default_user_id(self, mock_settings):
        """SessionManager uses 'default' when no user_id provided."""
        ws = MagicMock(spec=WebSocket)

        mgr = SessionManager(mock_settings, ws)

        assert mgr.user_id == "default"
        assert mgr.user_profile is None

    async def test_start_session_loads_profile(self, mock_settings):
        """handle_browser_websocket calls load_profile on start_session."""
        mock_ws = AsyncMock(spec=WebSocket)
        call_count = 0

        async def fake_receive_json():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"type": "start_session", "user_id": "alice"}
            raise WebSocketDisconnect()

        mock_ws.receive_json = fake_receive_json
        mock_ws.accept = AsyncMock()

        fake_profile = UserProfile(user_id="alice")

        with (
            patch(
                "english_skill_tester.api.websocket.load_profile",
                return_value=fake_profile,
            ) as mock_load,
            patch("english_skill_tester.api.websocket.SessionManager") as mock_sm_cls,
        ):
            mock_sm_instance = AsyncMock()
            mock_sm_cls.return_value = mock_sm_instance

            await handle_browser_websocket(mock_ws, mock_settings)

        mock_load.assert_called_once_with("alice")
        mock_sm_cls.assert_called_once()
        call_kwargs = mock_sm_cls.call_args.kwargs
        assert call_kwargs["user_id"] == "alice"
        assert call_kwargs["user_profile"] is fake_profile


class TestSelfReportedLevelSaved:
    async def test_self_reported_level_saved(self, mock_settings):
        """handle_browser_websocket saves self_reported_level to profile."""
        mock_ws = AsyncMock(spec=WebSocket)
        call_count = 0

        async def fake_receive_json():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "type": "start_session",
                    "user_id": "user_xyz",
                    "self_reported_level": "B2",
                }
            raise WebSocketDisconnect()

        mock_ws.receive_json = fake_receive_json
        mock_ws.accept = AsyncMock()

        fake_profile = UserProfile(user_id="user_xyz")

        with (
            patch(
                "english_skill_tester.api.websocket.load_profile",
                return_value=fake_profile,
            ),
            patch(
                "english_skill_tester.api.websocket.save_profile"
            ) as mock_save,
            patch("english_skill_tester.api.websocket.SessionManager") as mock_sm_cls,
        ):
            mock_sm_instance = AsyncMock()
            mock_sm_cls.return_value = mock_sm_instance

            await handle_browser_websocket(mock_ws, mock_settings)

        mock_save.assert_called_once()
        saved_profile = mock_save.call_args[0][0]
        assert saved_profile.self_reported_level == "B2"
