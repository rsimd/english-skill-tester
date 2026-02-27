# English Skill Tester — Current Analysis & Issues

## 1. Implementation Status Summary

### VRM 3D Character

| Feature | Status | Implementation |
|---------|--------|----------------|
| VRM model loading | **Implemented** | GLTFLoader + VRMLoaderPlugin, fallback to emoji avatar |
| Idle breathing | **Implemented** | Sine-wave Y oscillation (amplitude 0.003) |
| Auto-blinking | **Implemented** | Random 2-5s interval, double-blink 20% chance, `blink` blend shape |
| Head idle sway | **Implemented** | Multi-frequency sine waves on X/Y/Z rotation |
| Lip sync | **Implemented** | Audio level → `aa`/`oh`/`ee` blend shapes with vowel cycling |
| Expressions | **Implemented** | 5 types mapped to VRM presets (`happy`, `surprised`, `relaxed`) |
| Gestures | **Partially implemented** | Head-only animations (nod, wave, explain, listen, thumbs_up). No arm/body animation. |
| Camera control | **Static** | Fixed position (0, 1.35, 2.0), looking at (0, 1.25, 0). No zoom/pan/orbit. |
| Window resize | **Implemented** | Responsive canvas resize with aspect ratio update |
| Fallback mode | **Implemented** | Emoji + CSS animations when VRM not available |

### Realtime API Voice

| Feature | Status | Implementation |
|---------|--------|----------------|
| WebSocket connection | **Implemented** | Direct `websockets` to `wss://api.openai.com/v1/realtime` |
| Audio streaming (mic→API) | **Implemented** | `sounddevice` → thread queue → async → base64 PCM16 |
| Audio streaming (API→speaker) | **Implemented** | base64 → PCM16 → dedicated writer thread → `sounddevice` |
| User speech detection | **Implemented** | server_vad (threshold=0.3, silence=1000ms) |
| User transcription | **Implemented** | whisper-1 via `input_audio_transcription` |
| AI transcription | **Implemented** | `response.audio_transcript.done` event |
| Interruption handling | **Implemented** | `input_audio_buffer.speech_started` → clears playback buffer |
| Function calling | **Implemented** | `set_expression`, `play_gesture` defined and dispatched |
| Session update (adaptive) | **Implemented** | `session.update` with new prompt on level change |
| Reconnection | **Not implemented** | No automatic reconnect for Realtime API WebSocket |
| Error recovery | **Minimal** | Exception logged, `_running = False`, no retry |

### Assessment & Scoring

| Feature | Status | Implementation |
|---------|--------|----------------|
| Rule-based: vocabulary | **Implemented** | TTR, unique words, avg word length, word frequency |
| Rule-based: grammar | **Implemented** | Regex pattern matching (11 patterns) + Flesch-Kincaid grade |
| Rule-based: fluency | **Implemented** | Filler ratio, WPM (requires duration), avg sentence length |
| LLM evaluation | **Implemented** | gpt-4o-mini periodic eval (every 10 utterances or 120s) |
| Hybrid blending | **Implemented** | Rule 60-70% + LLM 30-40% for vocab/grammar/fluency |
| TOEIC/IELTS mapping | **Implemented** | Linear mapping (crude) |
| Adaptive difficulty | **Implemented** | 5 levels with distinct system prompts |
| Post-session feedback | **Implemented** | LLM-generated summary, strengths, weaknesses, corrections |
| Transcript highlighting | **Implemented** | Filler detection, grammar patterns, advanced vocab tagging |

### Frontend UI

| Feature | Status | Implementation |
|---------|--------|----------------|
| Score bars (5 components) | **Implemented** | Animated CSS bars with numeric display |
| TOEIC/IELTS estimates | **Implemented** | Real-time update |
| Chat-style transcript | **Implemented** | Color-coded user/assistant bubbles, auto-scroll |
| Session timer | **Implemented** | MM:SS counter |
| Start/Stop controls | **Implemented** | Button state management |
| Feedback overlay | **Implemented** | Modal with score, strengths, weaknesses, corrections |
| Review page | **Implemented** | Session list, transcript viewer, audio playback link |
| Connection status | **Implemented** | Green/red dot with label |
| WebSocket reconnect | **Implemented** | Exponential backoff, max 5 attempts |
| Responsive layout | **Implemented** | Grid → single column at 768px |
| Dark mode | **Not implemented** | Light theme only |

### Testing

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_assessment.py` | 16 tests | Metrics, calibration, scoring models, rule-based scorer |
| `test_audio.py` | 4 tests | PCM16 encoder roundtrip, silence, clipping |
| `test_realtime.py` | 6 tests | Event builders, tool definitions |
| **Total** | **26 tests** | Unit tests only. No integration, no E2E, no WebSocket tests. |

**Notable gaps**: No tests for `SessionManager`, `ConversationStrategy`, `FeedbackGenerator`, `HybridScorer.update()`, `AudioCapture`, `AudioPlayback`.

---

## 2. Issues & Problems

### VRM / Character

#### V-1: Gestures are head-only
**Severity**: Medium
**Location**: `frontend/js/character.js:260-314`
**Detail**: All "gesture" animations (nod, wave, explain, listen, thumbs_up) only manipulate `head` bone rotation. There is no arm, hand, or body animation. "Wave" and "thumbs_up" visually manifest as head movements, which looks unnatural.
**Root cause**: VRM humanoid bones for arms (`leftUpperArm`, `rightUpperArm`, etc.) are not accessed. Only `head` is used via `getNormalizedBoneNode('head')`.

#### V-2: No smooth expression transitions
**Severity**: Low
**Location**: `frontend/js/character.js:318-354`
**Detail**: Expression changes are instant (`setValue(preset, 0.7)` immediately). Previous expression is reset to 0 instantly. This creates jarring jumps instead of smooth fades between emotions.

#### V-3: Fixed camera, no zoom control
**Severity**: Low
**Location**: `frontend/js/character.js:47-54`
**Detail**: Camera is hardcoded at position (0, 1.35, 2.0) looking at (0, 1.25, 0). User cannot zoom in/out or orbit. The framing may not suit all VRM models (different heights, proportions).

#### V-4: Lip sync quality is basic
**Severity**: Medium
**Location**: `frontend/js/character.js:232-256`
**Detail**: Lip sync uses a simple audio level → blend shape mapping with a sine-wave vowel cycling effect. It doesn't analyze the actual phonemes being spoken. The mouth movements don't match the words. The vowel cycle frequency (12 Hz) is arbitrary.

#### V-5: No body idle animations
**Severity**: Low
**Detail**: Beyond breathing (Y position oscillation) and head sway, the body is completely static. Arms hang motionlessly. This reduces realism.

### Realtime API / Voice

#### R-1: No reconnection on Realtime API disconnect
**Severity**: High
**Location**: `src/english_skill_tester/realtime/client.py:110-126`
**Detail**: If the Realtime API WebSocket connection drops (network issue, API timeout, server error), `receive_loop` ends silently and `_running` is set to `False`. There is no reconnection logic. The user's session dies without notification.

#### R-2: Audio thread → async bridge uses polling
**Severity**: Low
**Location**: `src/english_skill_tester/audio/capture.py:86-98`
**Detail**: `chunks()` uses `run_in_executor` with a 0.5s timeout `queue.get()`. This means audio has up to 500ms latency for the first chunk after a silent period. Using `asyncio.Event` or a proper async queue would be more efficient.

#### R-3: No audio device selection UI
**Severity**: Low
**Location**: `src/english_skill_tester/config.py:27-28`
**Detail**: `audio_input_device` and `audio_output_device` are configurable via env vars but there's no UI or API to enumerate or select devices. Users must manually set device indices in `.env`.

#### R-4: VAD threshold is fixed
**Severity**: Low
**Location**: `src/english_skill_tester/realtime/events.py:19-23`
**Detail**: `server_vad` threshold is hardcoded at 0.3 with 1000ms silence duration. This may cause issues in noisy environments (false triggers) or with quiet speakers (missed speech). No user-configurable settings exposed.

#### R-5: Potential audio buffer overflow
**Severity**: Low
**Location**: `src/english_skill_tester/audio/capture.py:36`
**Detail**: `_thread_queue` has `maxsize=200`. At 100ms chunks, this is 20 seconds of buffer. If the consumer falls behind, frames are silently dropped. While the design is intentional (drop vs block), there's no metric tracking or warning for dropped frames.

### Assessment / Scoring

#### A-1: Grammar detection is rudimentary
**Severity**: Medium
**Location**: `src/english_skill_tester/assessment/metrics.py:79-91`
**Detail**: Only 11 hardcoded regex patterns for grammar errors (e.g., "he don't", "more better", "goed"). This catches very few real-world grammar mistakes. spaCy is listed as a dependency but is not used for grammar analysis.

#### A-2: TOEIC/IELTS mapping is linear approximation
**Severity**: Low
**Location**: `src/english_skill_tester/models/assessment.py:66-72`
**Detail**: `score_to_toeic(score) = 10 + (score/100) * 980` is a simple linear mapping. Real TOEIC/IELTS scores have non-linear distributions. The mapping is misleading at extreme scores.

#### A-3: Word frequency list is small
**Severity**: Low
**Location**: `src/english_skill_tester/assessment/metrics.py:129-138`
**Detail**: `HIGH_FREQ_WORDS` contains only ~80 words. Any word not in this set is treated as "advanced". Common words like "house", "car", "because" would score as advanced vocabulary, inflating the frequency score.

#### A-4: Filler words detection has false positives
**Severity**: Low
**Location**: `src/english_skill_tester/assessment/metrics.py:35-38`
**Detail**: "well", "like", "actually" are in the FILLERS set, but these are legitimate words in many contexts ("I like dogs", "Well done"). Context-free matching produces false positives.

#### A-5: No score persistence across sessions
**Severity**: Low
**Detail**: Each session starts with default scores (50.0). There's no tracking of improvement over time or historical trend analysis.

#### A-6: LLM evaluation can block score updates
**Severity**: Medium
**Location**: `src/english_skill_tester/assessment/scorer.py:85-94`
**Detail**: `HybridScorer.update()` calls `await self.llm_evaluator.evaluate(transcript)` inline. If the LLM API is slow (2-5 seconds), the `_score_update_loop` is blocked, causing a gap in real-time score updates.

### Code Quality

#### C-1: Settings singleton is recreated per request
**Severity**: Low
**Location**: `src/english_skill_tester/api/routes.py:14-16`
**Detail**: `get_settings()` creates a new `Settings()` instance every call. While pydantic-settings caches env reads, this is wasteful. Should use a proper singleton or FastAPI dependency.

#### C-2: Config prompts files are unused
**Severity**: Very Low
**Location**: `config/prompts/{beginner,intermediate,advanced}.txt`
**Detail**: These text files exist but are never loaded. System prompts are hardcoded in `conversation/prompts.py`. The files and the `prompts_dir` config property are dead code.

#### C-3: Protocol models are unused
**Severity**: Very Low
**Location**: `src/english_skill_tester/models/protocol.py`
**Detail**: `WSMessage`, `ScoreUpdate`, `TranscriptUpdate`, `CharacterAction`, `SessionStateUpdate`, `FeedbackResult` are defined but never used for serialization. The WebSocket handler constructs dicts directly.

#### C-4: No structured logging configuration
**Severity**: Low
**Detail**: `structlog` is used throughout but never configured (no `structlog.configure()` call). Default configuration is used.

#### C-5: `config.py` — `project_root` computation
**Severity**: Low
**Location**: `src/english_skill_tester/config.py:41-42`
**Detail**: `project_root` defaults to `Path(__file__).resolve().parent.parent.parent` which is `src/`. If installed as a package, this would point to `site-packages/`, not the project root. Works only in development (running from source).

### Security

#### S-1: API key exposed via WebSocket handler
**Severity**: Medium
**Location**: `src/english_skill_tester/api/websocket.py:43-44`
**Detail**: `settings.openai_api_key` is passed directly to `HybridScorer` and `FeedbackGenerator` constructors each time a WebSocket connects. While not exposed to the client, a careless log statement could leak it. Should centralize API client creation.

#### S-2: No CORS configuration
**Severity**: Low
**Detail**: FastAPI has no CORS middleware configured. Currently not an issue (same-origin), but will be if the frontend is served from a different domain.

#### S-3: No authentication
**Severity**: Medium
**Detail**: Anyone with network access to port 8000 can start sessions and consume OpenAI API credits. No auth, rate limiting, or session management.

#### S-4: Session ID in URL without validation
**Severity**: Low
**Location**: `src/english_skill_tester/api/routes.py:42-48`
**Detail**: `session_id` from URL is directly used in a file path (`sessions_dir / f"{session_id}.json"`). While FastAPI's path parameter won't accept `/`, a crafted `session_id` like `..%2F..%2Fetc%2Fpasswd` could theoretically escape if URL decoding occurs. Current risk is low (`.json` suffix limits exploitation).

### Performance

#### P-1: In-memory recording accumulation
**Severity**: Medium
**Location**: `src/english_skill_tester/audio/recorder.py:30-31`
**Detail**: All audio chunks are accumulated in memory lists (`_input_chunks`, `_output_chunks`). For long sessions (>30 min at 24kHz mono), this could consume significant memory (~86MB per channel per 30 min).

#### P-2: Full transcript sent to LLM on each evaluation
**Severity**: Low
**Location**: `src/english_skill_tester/assessment/llm_evaluator.py:73-77`
**Detail**: The entire conversation transcript is sent to gpt-4o-mini on each LLM evaluation. For long conversations, this increases token usage and cost linearly. Should send only recent utterances or a summary.

---

## 3. Test Coverage Analysis

**Covered:**
- Audio encoder (roundtrip, edge cases) — good coverage
- Assessment metrics (vocabulary, fluency, grammar) — good coverage
- Calibration functions — good coverage
- Score models and conversions — good coverage
- Realtime event builders — good coverage
- Realtime tool definitions — good coverage
- Rule-based scorer — basic coverage

**Not covered:**
- `SessionManager` (integration: audio + realtime + scoring + browser WS)
- `RealtimeClient` (WebSocket connection, event dispatch, function calling)
- `AudioCapture` / `AudioPlayback` (hardware-dependent)
- `HybridScorer.update()` (async LLM integration)
- `ConversationStrategy` (level change callbacks)
- `FeedbackGenerator` (LLM integration)
- `transcript.py` highlight logic
- Frontend JavaScript (no JS tests)
- WebSocket protocol handling
- Error paths and edge cases

**Test infrastructure:**
- pytest with asyncio_mode="auto"
- No mocking framework for OpenAI API calls
- No fixtures for session data
- No CI configuration found
