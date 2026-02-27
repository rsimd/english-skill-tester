# English Skill Tester

Real-time English conversation skill assessment using OpenAI Realtime API with a 3D character interface.

## System Requirements

- **Python**: 3.12 or later
- **Package Manager**: uv (https://github.com/astral-sh/uv)
- **OS**: macOS, Linux, or WSL2 on Windows
- **Node.js**: Not required (frontend uses plain HTML/CSS/JS)
- **OpenAI API Key**: Required for Realtime API access

## Architecture

```
[Mic] → sounddevice → Python Backend → OpenAI Realtime API (WebSocket)
[Speaker] ← sounddevice ← Python Backend ← OpenAI Realtime API

Python Backend → FastAPI WebSocket → Browser (3D Character + Score Display + UI)
```

- **Audio I/O**: Python-side microphone/speaker control via sounddevice
- **Realtime API**: Python → OpenAI WebSocket for audio streaming
- **Frontend**: FastAPI serves static files, WebSocket for real-time updates
- **Assessment**: Hybrid rule-based (continuous) + LLM (periodic) scoring

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/rsimd/english-skill-tester.git
cd english-skill-tester
```

### 2. Install Python dependencies
```bash
uv sync
```

### 3. Download spaCy model
```bash
uv run python -m spacy download en_core_web_sm
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 5. (Optional) Add VRM model
Place your VRM avatar file at `frontend/models/avatar.vrm`
(A default model is included)

### 6. Run the application
```bash
uv run python -m english_skill_tester.main
```

Then open `http://localhost:8000` in your browser.

## Usage

```bash
# Start the server
uv run python -m english_skill_tester.main

# Open browser
open http://localhost:8000
```

1. Click **Start Conversation** to begin
2. Speak into your microphone - the AI will respond through your speakers
3. Watch your scores update in real-time on the right panel
4. Click **Stop** to end the session and receive detailed feedback
5. Visit the **Review** page to see past session transcripts

## Scoring

Hybrid assessment combining rule-based linguistic analysis and periodic LLM evaluation:

| Component | Weight | Method |
|-----------|--------|--------|
| Vocabulary | 20% | TTR, word frequency, diversity |
| Grammar | 25% | Error detection, complexity |
| Fluency | 20% | Filler ratio, WPM, sentence length |
| Comprehension | 15% | LLM evaluation |
| Coherence | 15% | LLM evaluation |
| Pronunciation | 5% | Transcript artifact analysis |

Scores map to TOEIC (10-990) and IELTS (1-9) estimates.

## Adaptive Conversation

The AI adjusts its conversation style based on your real-time score:

- **Beginner** (0-20): Simple yes/no questions, encouragement
- **Elementary** (20-40): Simple open-ended questions
- **Intermediate** (40-60): Natural conversation with idioms
- **Upper Intermediate** (60-80): Abstract discussions, hypotheticals
- **Advanced** (80-100): Debate, nuanced analysis

## Development Commands

### Run tests
```bash
uv run pytest
```

### Lint
```bash
uv run ruff check .
```

### Format
```bash
uv run ruff format .
```

### Type check
```bash
uv run mypy src/
```

## Development Status

### ✅ Completed (cmd_001)
- [x] VRM model expression control
- [x] Lip-sync implementation (initial)
- [x] Upper body gestures (5 types)
- [x] Camera adjustment (upper body focus)
- [x] Audio capture latency optimization
- [x] Code quality improvements
- [x] spaCy grammar check integration (highlight only)
- [x] Async LLM evaluation
- [x] GitHub repository setup

### 🔄 In Progress (cmd_002)
- [ ] Fix lip-sync stopping mid-speech (overrideMouth issue)
- [ ] Add 8 new American gestures (total 13 types)
- [ ] Rule-based gesture triggering
- [ ] VRM model dynamic switching via UI
- [ ] AI tutor persona externalization (YAML)
- [ ] Unified YAML configuration

### 📋 Planned / Proposed (cmd_003 review)
- See dashboard.md for 48 improvement proposals (High: 12, Medium: 25, Low: 11)
- Priority: P-SEC-002 (path traversal fix), P-SEC-001 (API key management)

## Project Structure

```
src/english_skill_tester/
├── main.py              # FastAPI entry point
├── config.py            # Settings (pydantic-settings)
├── audio/               # Mic capture, speaker playback, recording
├── realtime/            # OpenAI Realtime API client
├── assessment/          # Hybrid scoring engine
├── conversation/        # Adaptive prompts and strategy
├── analysis/            # Post-session feedback
├── api/                 # REST + WebSocket routes
└── models/              # Pydantic data models
```
