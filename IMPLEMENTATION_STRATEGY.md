# English Skill Tester — Implementation Strategy

## Phase Overview

| Phase | Focus | Priority | Effort | Dependency |
|-------|-------|----------|--------|------------|
| Phase 1 | VRM Character Enhancement | High | Medium | None |
| Phase 2 | Voice & Audio Stability | High | Medium | None |
| Phase 3 | Assessment Quality | Medium | Medium | None |
| Phase 4 | Bug Fixes & Code Quality | Medium | Low | None |
| Phase 5 | Security & Production Readiness | Low | Medium | Phase 4 |

Phases 1-3 can be parallelized. Phase 4 is quick wins. Phase 5 is for production deployment.

---

## Phase 1: VRM Character Enhancement

### 1A. Arm & Body Gesture Animations (V-1)

**Current state**: Gestures (wave, thumbs_up, explain) only rotate the head bone.

**Approach**: Access VRM humanoid arm bones (`rightUpperArm`, `rightLowerArm`, `rightHand`, `leftUpperArm`, etc.) and define keyframe-style rotation sequences for each gesture.

**Implementation plan**:
1. In `character.js`, define gesture functions that access multiple bones:
   ```
   wave     → rightUpperArm rotation Z (-60°→-45°→-60°), rightLowerArm Z oscillation
   thumbs_up → rightUpperArm rotation Z (-45°), rightLowerArm rotation X (90°)
   explain  → both arms slight rotation outward, subtle oscillation
   listen   → head tilt + slight body lean (spine bone)
   nod      → keep as head-only (natural)
   ```
2. Store original bone rotations before gesture starts; restore after.
3. Use easing functions (ease-in-out) for smooth transitions.

**Technical considerations**:
- VRM bone names follow the VRM specification (`rightUpperArm`, not Three.js conventions). Use `vrm.humanoid.getNormalizedBoneNode('rightUpperArm')`.
- Some VRM models may lack certain bones. Check for null before animating.
- Gesture duration should be 0.5-1.5s to feel natural.

**Risk**: Different VRM models have different rest poses. Hard-coded rotation targets may not look correct on all models.
**Mitigation**: Use relative rotations (delta from rest pose) rather than absolute values.

### 1B. Smooth Expression Transitions (V-2)

**Current state**: `setExpression()` instantly sets values to 0/0.7.

**Approach**: Implement a lerp-based transition system.

**Implementation plan**:
1. Track target expression values as a dict: `{happy: 0.7, neutral: 0}`.
2. In the `animate()` loop, interpolate current values toward targets using `lerp(current, target, delta * 5)`.
3. On expression change, update targets only; let the animation loop handle the transition.

**Effort**: Small (30 lines of code change).

### 1C. Body Idle Animations (V-5)

**Approach**: Add subtle spine and shoulder oscillations.

**Implementation plan**:
1. Access `spine` and `upperChest` bones.
2. Apply low-frequency sine waves (0.1-0.3 Hz) with very small amplitude (0.005-0.01 radians).
3. Add slight shoulder rotation offset to prevent symmetric look.

**Effort**: Small.

### 1D. Camera Improvements (V-3)

**Approach**: Add OrbitControls for user-controllable camera, with sensible limits.

**Implementation plan**:
1. Import `OrbitControls` from `three/addons/controls/OrbitControls.js`.
2. Set target to character's head height (0, 1.25, 0).
3. Limit zoom range (min distance 1.0, max distance 4.0).
4. Limit polar angle to prevent looking from below.
5. Enable damping for smooth movement.

**Technical consideration**: OrbitControls adds ~15KB. Acceptable for this app.

---

## Phase 2: Voice & Audio Stability

### 2A. Realtime API Reconnection (R-1) — Highest Priority

**Current state**: Connection drop = session death. No recovery.

**Approach**: Implement reconnection with exponential backoff inside `RealtimeClient`.

**Implementation plan**:
1. In `receive_loop`, catch `ConnectionClosed` and attempt reconnect:
   - Attempt 1: immediate
   - Attempt 2: 1s delay
   - Attempt 3: 2s delay
   - Attempt 4: 4s delay
   - Max 5 attempts
2. On reconnect:
   - Re-send `session.update` with current instructions and tools.
   - Notify browser via WebSocket: `{type: "reconnecting"}` / `{type: "reconnected"}`.
   - Resume `_audio_send_loop` if it was running.
3. On permanent failure (5 attempts exhausted):
   - Notify browser: `{type: "session_state", status: "error", reason: "connection_lost"}`.
   - Save partial session data.

**Risk**: Realtime API doesn't guarantee conversation state survives reconnection. The conversation history may be lost.
**Mitigation**: Send a text summary of recent conversation via `conversation.item.create` after reconnect to provide context.

### 2B. Improve Audio Capture Latency (R-2)

**Approach**: Replace polling `queue.get(timeout=0.5)` with `asyncio.Queue`.

**Implementation plan**:
1. Create an `asyncio.Queue` alongside the thread queue.
2. In `_audio_callback`, put to thread queue, then use `loop.call_soon_threadsafe(asyncio_queue.put_nowait, chunk)`.
3. In `chunks()`, directly `await asyncio_queue.get()`.

**Effort**: Small. Eliminates up to 500ms latency on first chunk.

### 2C. Non-blocking LLM Evaluation (A-6)

**Current state**: `HybridScorer.update()` awaits the LLM call inline, blocking the score update loop.

**Approach**: Run LLM evaluation in a background task.

**Implementation plan**:
1. When LLM evaluation is triggered, spawn it as `asyncio.create_task()`.
2. Continue returning rule-based scores immediately.
3. When the LLM task completes, update `_latest_llm_scores` and the next `update()` call will incorporate them.
4. Protect `_latest_llm_scores` with a lock or use atomic reference replacement.

**Effort**: Medium. Core logic change to `scorer.py`.

### 2D. Streaming-to-Disk Recording (P-1)

**Current state**: All audio chunks accumulate in memory lists.

**Approach**: Write audio chunks to disk in real-time using a WAV writer.

**Implementation plan**:
1. Open WAV files at `start()` time.
2. In `record_input()` / `record_output()`, write directly to the WAV file.
3. At `stop()`, close the file handles and compute the mixed version.

**Risk**: Disk I/O latency could slow recording.
**Mitigation**: Use a background thread for disk writes.

---

## Phase 3: Assessment Quality

### 3A. Improve Grammar Detection (A-1)

**Approach A: Use spaCy's dependency parser** (already a dependency).

**Implementation plan**:
1. Load `en_core_web_sm` model at initialization.
2. Parse user text with spaCy.
3. Check for:
   - Subject-verb agreement violations (using POS tags and dependency arcs)
   - Missing articles (determiner analysis)
   - Tense consistency (verb form analysis)
   - Word order issues (dependency tree structure)
4. Combine with existing regex patterns as a fallback.

**Technical consideration**: spaCy parsing adds ~50ms per evaluation. Acceptable at 3s intervals.

**Approach B: Use LLM for grammar analysis** (more accurate, higher cost).

Not recommended as the primary approach since it would double the LLM calls.

**Recommendation**: Approach A. spaCy is already in `pyproject.toml` but unused.

### 3B. Expand Word Frequency List (A-3)

**Approach**: Use an established word frequency list.

**Implementation plan**:
1. Use the first 3000 words from a frequency corpus (e.g., BNC/COCA most frequent words).
2. Store as a set for O(1) lookup.
3. Create tiers: top 1000 (basic), 1000-3000 (intermediate), 3000+ (advanced).
4. Score based on the proportion in each tier.

**Effort**: Small. Data preparation + scoring formula update.

### 3C. Context-Aware Filler Detection (A-4)

**Approach**: Check surrounding words to distinguish fillers from legitimate usage.

**Implementation plan**:
1. "like" is a filler only when not preceded by a verb ("I like" → not filler) or "would" ("would like" → not filler).
2. "well" is a filler only at sentence start, not after "very" or "quite".
3. "actually" and "basically" remain always-fillers (they rarely add meaning in speech).
4. Use spaCy POS tagging for disambiguation.

**Effort**: Medium.

### 3D. Truncate Transcript for LLM Evaluation (P-2)

**Approach**: Send only the last N utterances to the LLM evaluator.

**Implementation plan**:
1. Cap transcript at last 20 utterances (10 user + 10 AI).
2. If total utterances > 20, prepend a brief summary: "This is a continued conversation. Prior context: [N exchanges about topic X]."
3. Keeps token usage bounded regardless of conversation length.

**Effort**: Small.

---

## Phase 4: Bug Fixes & Code Quality

### 4A. Fix Settings Singleton (C-1)

Use `functools.lru_cache` on `get_settings()` or FastAPI's `Depends()` with a cached dependency.

### 4B. Remove Dead Code (C-2, C-3)

1. Either delete `config/prompts/*.txt` or load them in `prompts.py` (replacing hardcoded strings).
2. Either delete `models/protocol.py` or use the models for WebSocket serialization.

**Recommendation**: Load prompts from files (more maintainable). Keep protocol models as documentation.

### 4C. Configure structlog (C-4)

Add `structlog.configure()` in `main.py` with JSON output format for production, console format for development.

### 4D. Fix `project_root` for Package Installation (C-5)

Use `importlib.resources` or detect project root from a marker file (e.g., `pyproject.toml`).

### 4E. Improve Test Coverage

Priority additions:
1. `ConversationStrategy` — pure logic, easy to test:
   - Test level transitions at boundary scores (19→20, 39→40, etc.)
   - Test callback invocation
2. `HybridScorer.update()` — mock OpenAI API:
   - Test rule-only mode (before LLM threshold)
   - Test blending with mocked LLM scores
3. `transcript.py` highlights — unit tests:
   - Filler detection
   - Grammar pattern matching
   - Advanced vocab tagging
4. `SessionManager` — integration test with mocked Realtime API

---

## Phase 5: Security & Production Readiness

### 5A. Add Authentication (S-3)

**Approach**: Simple API key or OAuth, depending on use case.

**Options**:
1. **Single-user (personal use)**: Environment variable `APP_SECRET` checked via middleware.
2. **Multi-user**: FastAPI OAuth2 with JWT tokens.

**Recommendation**: Option 1 for MVP. Add JWT when multi-user is needed.

### 5B. CORS Configuration (S-2)

Add `CORSMiddleware` with explicit origins list. Default to `localhost:8000` only.

### 5C. Session ID Validation (S-4)

Validate `session_id` as UUID format before using in file paths:
```python
try:
    uuid.UUID(session_id)
except ValueError:
    raise HTTPException(400, "Invalid session ID")
```

### 5D. Rate Limiting

Add rate limiting middleware to prevent API credit abuse. Limit to N sessions per hour.

---

## Recommended Execution Order

For maximum user-visible impact with minimal risk:

```
1. R-1 (Realtime reconnection)     — fixes session-breaking bug
2. V-1 (Arm gestures)              — biggest visual improvement
3. A-6 (Non-blocking LLM eval)     — fixes score update stalls
4. 4A-4D (Code quality quick wins) — 1-2 hours total
5. 3A (spaCy grammar)              — biggest assessment improvement
6. 1B (Expression transitions)     — polish
7. 2B (Audio latency)              — polish
8. 3B (Word frequency expansion)   — assessment refinement
9. 3D (Transcript truncation)      — cost optimization
10. Phase 5 (Security)             — when deploying publicly
```
