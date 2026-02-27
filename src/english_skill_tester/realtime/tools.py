"""Function calling tool definitions for OpenAI Realtime API.

These tools allow the AI to control the 3D character's expressions and gestures.
"""

REALTIME_TOOLS: list[dict] = [
    {
        "type": "function",
        "name": "set_expression",
        "description": (
            "Set the 3D character's facial expression to match the conversation mood. "
            "Call this when your emotional tone changes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "enum": ["neutral", "happy", "thinking", "encouraging", "surprised"],
                    "description": "The facial expression to display.",
                },
            },
            "required": ["expression"],
        },
    },
    {
        "type": "function",
        "name": "play_gesture",
        "description": (
            "Play a gesture animation on the 3D character. "
            "Use gestures to make the conversation feel more natural and engaging."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "gesture": {
                    "type": "string",
                    "enum": [
                        "nod", "wave", "thumbs_up", "explain", "listen",
                        "shrug", "thinking_pose", "open_palms", "head_shake",
                        "lean_forward", "celebration", "point", "idle_rest"
                    ],
                    "description": "The gesture animation to play.",
                },
            },
            "required": ["gesture"],
        },
    },
]
