"""Tests for Realtime API event builders and tools."""



from english_skill_tester.realtime.events import (
    conversation_item_create_event,
    function_call_output_event,
    input_audio_buffer_append_event,
    response_create_event,
    session_update_event,
)
from english_skill_tester.realtime.tools import REALTIME_TOOLS


class TestEventBuilders:
    def test_session_update(self):
        event = session_update_event(
            instructions="Test prompt",
            tools=REALTIME_TOOLS,
        )
        assert event["type"] == "session.update"
        assert event["session"]["instructions"] == "Test prompt"
        assert "audio" in event["session"]["modalities"]
        assert "text" in event["session"]["modalities"]
        assert event["session"]["voice"] == "alloy"

    def test_audio_buffer_append(self):
        event = input_audio_buffer_append_event("dGVzdA==")
        assert event["type"] == "input_audio_buffer.append"
        assert event["audio"] == "dGVzdA=="

    def test_conversation_item_create(self):
        event = conversation_item_create_event("user", "Hello world")
        assert event["type"] == "conversation.item.create"
        assert event["item"]["role"] == "user"
        assert event["item"]["content"][0]["text"] == "Hello world"

    def test_response_create(self):
        event = response_create_event()
        assert event["type"] == "response.create"

    def test_function_call_output(self):
        event = function_call_output_event("call_123", '{"status": "ok"}')
        assert event["type"] == "conversation.item.create"
        assert event["item"]["call_id"] == "call_123"
        assert event["item"]["output"] == '{"status": "ok"}'


class TestRealtimeTools:
    def test_tools_defined(self):
        assert len(REALTIME_TOOLS) == 3

    def test_set_expression_tool(self):
        tool = REALTIME_TOOLS[0]
        assert tool["name"] == "set_expression"
        params = tool["parameters"]["properties"]["expression"]
        assert "neutral" in params["enum"]
        assert "happy" in params["enum"]

    def test_play_gesture_tool(self):
        tool = REALTIME_TOOLS[1]
        assert tool["name"] == "play_gesture"
        params = tool["parameters"]["properties"]["gesture"]
        assert "nod" in params["enum"]
        assert "wave" in params["enum"]

    def test_end_session_tool(self):
        tool = REALTIME_TOOLS[2]
        assert tool["name"] == "end_session"
        params = tool["parameters"]["properties"]["farewell_reason"]
        assert "user_request" in params["enum"]
        assert "time_limit" in params["enum"]
