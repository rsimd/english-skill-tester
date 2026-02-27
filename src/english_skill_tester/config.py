"""Application configuration using pydantic-settings."""

import functools
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """Find project root by locating pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to old behavior if pyproject.toml not found
    return Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment and config files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = Field(description="OpenAI API key")
    realtime_model: str = Field(default="gpt-4o-realtime-preview-2024-12-17")
    evaluation_model: str = Field(default="gpt-4o-mini")

    # Audio
    audio_sample_rate: int = Field(default=24000)
    audio_channels: int = Field(default=1)
    audio_chunk_duration_ms: int = Field(default=100)
    audio_input_device: int | None = Field(default=None)
    audio_output_device: int | None = Field(default=None)

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Assessment
    llm_eval_interval_utterances: int = Field(default=10)
    llm_eval_interval_seconds: float = Field(default=120.0)
    score_update_interval_seconds: float = Field(default=3.0)

    # Paths
    project_root: Path = Field(default_factory=_find_project_root)

    @property
    def recordings_dir(self) -> Path:
        d = self.project_root / "data" / "recordings"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def sessions_dir(self) -> Path:
        d = self.project_root / "data" / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def prompts_dir(self) -> Path:
        return self.project_root / "config" / "prompts"

    @property
    def frontend_dir(self) -> Path:
        return self.project_root / "frontend"

    @property
    def audio_chunk_size(self) -> int:
        """Number of samples per audio chunk."""
        return int(self.audio_sample_rate * self.audio_chunk_duration_ms / 1000)


@functools.lru_cache()
def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
