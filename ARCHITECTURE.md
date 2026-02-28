# English Skill Tester — System Architecture

## Overview

Real-time English conversation skill assessment system.
Users converse with an AI via voice; the system continuously evaluates their English ability
and renders a 3D VRM character in the browser as a visual conversation partner.

```
┌───────────────────────────────────────────────────────────────────┐
│                          Browser (Frontend)                       │
│  ┌──────────┐   ┌───────────┐   ┌──────────────┐   ┌──────────┐ │
│  │ WebSocket │   │    UI     │   │  Three.js +  │   │  Review  │ │
│  │  Client   │   │ Controller│   │  VRM Loader  │   │   Page   │ │
│  └─────┬─────┘   └─────┬─────┘   └──────┬───────┘   └─────┬────┘ │
│        │               │                │                  │      │
│   JSON messages    DOM updates    3D render + lip sync   REST API │
└────────┼───────────────┼────────────────┼──────────────────┼──────┘
         │ WebSocket /ws │                │                  │
─────────┼───────────────┼────────────────┼──────────────────┼──────
         │               │                │       GET /api/sessions
┌────────▼───────────────▼────────────────┼──────────────────▼──────┐
│                    Python Backend (FastAPI)                        │
│                                                                   │
│  ┌──────────────────────────────────┐                             │
│  │        SessionManager            │                             │
│  │  ┌─────────────┐ ┌────────────┐  │   ┌────────────────┐       │
│  │  │ AudioCapture│ │AudioPlayback│  │   │   REST Routes  │       │
│  │  │ (sounddevice│ │(sounddevice │  │   │  /api/sessions │       │
│  │  │  InputStream│ │OutputStream)│  │   │  /api/health   │       │
│  │  └──────┬──────┘ └──────┬──────┘  │   └────────────────┘       │
│  │         │               │         │                             │
│  │  ┌──────▼───────────────▼──────┐  │                             │
│  │  │        AudioRecorder        │  │  → data/recordings/*.wav    │
│  │  │   (WAV file archival)       │  │                             │
│  │  └─────────────────────────────┘  │                             │
│  │                                   │                             │
│  │  ┌─────────────────────────────┐  │                             │
│  │  │      RealtimeClient         │  │                             │
│  │  │  (WebSocket to OpenAI)      │──┼──→ OpenAI Realtime API      │
│  │  │  - send_audio (PCM16/b64)   │  │     gpt-realtime-1.5        │
│  │  │  - receive_loop (events)    │  │                             │
│  │  │  - function call dispatch   │  │                             │
│  │  └──────────────┬──────────────┘  │                             │
│  │                 │                 │                             │
│  │  ┌──────────────▼──────────────┐  │                             │
│  │  │ ConversationStrategy        │  │                             │
│  │  │ (adaptive difficulty)       │  │                             │
│  │  └─────────────────────────────┘  │                             │
│  │                                   │                             │
│  │  ┌─────────────────────────────┐  │                             │
│  │  │     HybridScorer            │  │                             │
│  │  │  ┌──────────┐ ┌──────────┐  │  │                             │
│  │  │  │Rule-based│ │   LLM    │  │──┼──→ OpenAI Chat API          │
│  │  │  │ (metrics)│ │Evaluator │  │  │     gpt-4o-mini             │
│  │  │  └──────────┘ └──────────┘  │  │                             │
│  │  └─────────────────────────────┘  │                             │
│  │                                   │                             │
│  │  ┌─────────────────────────────┐  │                             │
│  │  │    FeedbackGenerator        │──┼──→ OpenAI Chat API          │
│  │  │  (post-session analysis)    │  │     gpt-4o-mini             │
│  │  └─────────────────────────────┘  │                             │
│  └──────────────────────────────────┘                             │
└───────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. FastAPI Application (`main.py`)

- Entry point: `uvicorn` server on `0.0.0.0:8000`
- Routes:
  - `WebSocket /ws` → `handle_browser_websocket()` (real-time session)
  - `GET /api/sessions` → list saved sessions
  - `GET /api/sessions/{id}` → get session detail JSON
  - `GET /api/health` → health check
- Static files: `frontend/` directory mounted at `/` (html=True)

### 2. Configuration (`config.py`)

- `pydantic-settings.BaseSettings` loading from `.env`
- Key settings: `openai_api_key`, `realtime_model`, `evaluation_model`,
  `audio_sample_rate` (24000Hz), `audio_channels` (1/mono)
- Computed paths: `recordings_dir`, `sessions_dir`, `prompts_dir`, `frontend_dir`

### 3. Audio Subsystem (`audio/`)

| Module | Role | Implementation |
|--------|------|----------------|
| `capture.py` | Mic input | `sounddevice.InputStream` (float32) → thread-safe queue → async iterator |
| `playback.py` | Speaker output | Dedicated writer thread → `sounddevice.OutputStream.write()` (blocking) |
| `encoder.py` | Format conversion | `float32 ↔ PCM16 ↔ base64` for Realtime API transport |
| `recorder.py` | WAV archival | Accumulates input/output chunks → saves input, output, mixed WAVs |

**Data flow:**
```
Mic → sounddevice callback → thread queue → async chunks() → PCM16→base64 → Realtime API
Realtime API → base64→PCM16 → playback queue → writer thread → sounddevice → Speaker
```

### 4. OpenAI Realtime API Client (`realtime/`)

| Module | Role |
|--------|------|
| `client.py` | WebSocket client: connect, send_audio, receive_loop, event dispatch |
| `events.py` | Event builder functions (session.update, input_audio_buffer.append, etc.) |
| `tools.py` | Function call definitions: `set_expression`, `play_gesture` |

- **Connection**: Direct WebSocket to `wss://api.openai.com/v1/realtime?model=...`
- **Session config**: server_vad turn detection (threshold=0.3, silence=1000ms), whisper-1 transcription
- **Function calling**: AI can call `set_expression(expression)` and `play_gesture(gesture)` to control the VRM character
- **Event handlers**: Registered via `.on(event_type, handler)` pattern

### 5. Assessment Engine (`assessment/`)

| Module | Role |
|--------|------|
| `scorer.py` | `HybridScorer` — orchestrates rule-based + LLM scoring |
| `rule_based.py` | Continuous: vocabulary richness, grammar errors, fluency metrics |
| `llm_evaluator.py` | Periodic: comprehension, coherence, pronunciation via gpt-4o-mini |
| `metrics.py` | Raw metric computation (TTR, filler ratio, WPM, grammar patterns) |
| `calibration.py` | Maps raw metrics to 0-100 scores; TOEIC/IELTS conversion |

**Scoring architecture:**
```
Every 3 seconds:
  Rule-based → vocabulary (TTR + frequency), grammar (patterns + readability), fluency (fillers + WPM)

Every 10 utterances or 120 seconds:
  LLM eval  → comprehension, coherence, pronunciation_proxy, vocabulary, grammar

Merge: blend rule + LLM (rule_weight=0.6-0.7 for vocab/grammar/fluency; LLM-only for comprehension/coherence/pronunciation)

Overall = weighted sum: vocab(20%) + grammar(25%) + fluency(20%) + comprehension(15%) + coherence(15%) + pronunciation(5%)
```

### 6. Conversation Strategy (`conversation/`)

| Module | Role |
|--------|------|
| `strategy.py` | Tracks current level, triggers prompt updates on level change |
| `prompts.py` | Level-specific system prompts (beginner → advanced) |

- 5 levels: beginner (<20), elementary (20-40), intermediate (40-60), upper_intermediate (60-80), advanced (80+)
- On level change: sends `session.update` to Realtime API with new instructions

### 7. Analysis (`analysis/`)

| Module | Role |
|--------|------|
| `feedback.py` | Post-session LLM feedback (strengths, weaknesses, corrections) |
| `transcript.py` | Highlight annotations (fillers, grammar errors, advanced vocab) |

### 8. Data Models (`models/`)

| Module | Role |
|--------|------|
| `session.py` | `Session`, `Utterance`, `SessionStatus`, `SkillLevel` |
| `assessment.py` | `ComponentScores`, `AssessmentResult`, `ScoreMapping`, TOEIC/IELTS converters |
| `protocol.py` | WebSocket message schemas (not actively used for serialization) |

### 9. Frontend

| File | Role |
|------|------|
| `index.html` | Main page: 3D character + score panel + transcript + controls |
| `review.html` | Session review: past sessions list + transcript viewer + audio playback |
| `js/websocket.js` | `WebSocketClient` with auto-reconnect (exponential backoff, max 5 attempts) |
| `js/ui.js` | `UIController` — score bars, transcript rendering, feedback overlay, timer |
| `js/character.js` | Three.js + @pixiv/three-vrm: VRM loading, idle animations, expressions, lip sync, gestures |
| `js/app.js` | Glue: connects WebSocket events → UI + CharacterController |
| `css/styles.css` | Light theme, grid layout, responsive (768px breakpoint) |

**VRM character features:**
- Idle breathing (sine-wave Y position)
- Auto-blinking (2-5s random interval, occasional double-blink)
- Head idle sway (multi-frequency sine waves)
- Lip sync (audio level → aa/oh/ee blend shapes with vowel cycling)
- Expressions: neutral, happy, thinking, encouraging, surprised (mapped to VRM presets)
- Gestures: nod, wave, explain, listen, thumbs_up (head rotation animations)
- Fallback: emoji avatar when VRM model fails to load

### 10. Data Storage

- **Sessions**: `data/sessions/{uuid}.json` (Pydantic model dump)
- **Recordings**: `data/recordings/{uuid}_{input|output|mixed}.wav`
- **Config prompts**: `config/prompts/{beginner|intermediate|advanced}.txt` (currently unused; prompts are hardcoded in `prompts.py`)

## Data Flow (Complete Session Lifecycle)

```
1. Browser connects WebSocket /ws
2. User clicks "Start" → sends {type: "start_session"}
3. Backend creates SessionManager:
   - AudioCapture.start()     → mic stream begins
   - AudioPlayback.start()    → speaker thread starts
   - AudioRecorder.start()    → recording accumulation begins
   - RealtimeClient.connect() → WebSocket to OpenAI with system prompt + tools
   - Spawns 3 async tasks:
     a. _audio_send_loop   — mic chunks → base64 → Realtime API
     b. receive_loop       — Realtime API events → dispatch to handlers
     c. _score_update_loop — every 3s, run HybridScorer → send scores to browser

4. During conversation:
   - AI audio arrives → decoded → played through speaker + sent as audio_level to browser
   - AI transcripts → stored in session + sent to browser
   - User speech detected → audio buffer sent → transcription completed → stored + sent
   - AI function calls (set_expression, play_gesture) → forwarded to browser
   - Periodic scoring → rule-based + LLM → blended → sent to browser
   - Level changes → session.update sent to Realtime API with new prompt

5. User clicks "Stop":
   - Audio streams stopped
   - Realtime API disconnected
   - Recordings saved to WAV files
   - FeedbackGenerator produces LLM summary (strengths, weaknesses, advice, corrections)
   - Session data saved to JSON
   - Feedback sent to browser overlay
```

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, uvicorn |
| AI | OpenAI Realtime API (gpt-realtime-1.5), gpt-4o-mini |
| Audio | sounddevice (PortAudio), numpy, scipy |
| NLP | textstat (readability), spaCy en_core_web_sm (dependency, currently unused) |
| Frontend | Vanilla JS, Three.js r169, @pixiv/three-vrm 3.3.3 |
| Data | JSON files (sessions), WAV files (recordings) |
| Config | pydantic-settings (.env), YAML (settings) |
| Dev tools | uv, pytest, ruff |
