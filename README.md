# English Skill Tester

Real-time English conversation skill assessment using OpenAI Realtime API with a 3D character interface.

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

```bash
# Clone and enter directory
cd english-skill-tester

# Install dependencies
uv sync

# Copy environment file and set your API key
cp .env.example .env
# Edit .env with your OPENAI_API_KEY

# Download spaCy model (for NLP analysis)
uv run python -m spacy download en_core_web_sm

# (Optional) Place a VRM model at frontend/models/avatar.vrm
# Without it, the app uses an emoji fallback avatar
```

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

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/
```

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
