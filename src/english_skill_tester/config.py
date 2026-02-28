"""Application configuration using pydantic-settings."""

import functools
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


def _find_project_root() -> Path:
    """Find project root by locating pyproject.toml."""
    current = Path(__file__).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    # Fallback to old behavior if pyproject.toml not found
    return Path(__file__).resolve().parent.parent.parent


class YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from settings.yaml."""

    def get_field_value(self, field_name: str) -> tuple[Any, str, bool]:
        """Not used - we implement __call__ instead."""
        return None, "", False

    def __call__(self) -> dict[str, Any]:
        """Load settings from YAML file."""
        yaml_path = _find_project_root() / "config" / "settings.yaml"
        if not yaml_path.exists():
            return {}

        with open(yaml_path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # Flatten nested structure to match Settings field names
        flattened = {}
        if 'server' in data:
            flattened['host'] = data['server'].get('host')
            flattened['port'] = data['server'].get('port')
        if 'audio' in data:
            flattened['audio_sample_rate'] = data['audio'].get('sample_rate')
            flattened['audio_channels'] = data['audio'].get('channels')
            flattened['audio_chunk_duration_ms'] = data['audio'].get('chunk_duration_ms')
        if 'assessment' in data:
            assessment = data['assessment']
            flattened['llm_eval_interval_utterances'] = (
                assessment.get('llm_eval_interval_utterances')
            )
            flattened['llm_eval_interval_seconds'] = assessment.get('llm_eval_interval_seconds')
            flattened['score_update_interval_seconds'] = (
                assessment.get('score_update_interval_seconds')
            )
        if 'openai' in data:
            flattened['realtime_model'] = data['openai'].get('realtime_model')
            flattened['evaluation_model'] = data['openai'].get('evaluation_model')

        # Remove None values
        return {k: v for k, v in flattened.items() if v is not None}


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

    # Authentication (optional: None disables auth)
    app_secret: str | None = Field(default=None)

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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customise settings sources to include YAML file.

        Priority order (highest to lowest):
        1. init_settings (arguments passed to Settings())
        2. env_settings (environment variables)
        3. dotenv_settings (.env file)
        4. YamlSettingsSource (settings.yaml)
        5. file_secret_settings
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlSettingsSource(settings_cls),
            file_secret_settings,
        )


@functools.lru_cache
def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()


def load_persona(persona_name: str = "default") -> dict:
    """Load persona configuration from YAML file."""
    persona_path = _find_project_root() / "config" / "personas" / f"{persona_name}.yaml"
    if not persona_path.exists():
        raise FileNotFoundError(f"Persona file not found: {persona_path}")
    with open(persona_path, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('persona', {})


def load_level_prompts() -> dict:
    """Load level-specific prompts from YAML file."""
    prompts_path = _find_project_root() / "config" / "prompts" / "levels.yaml"
    if not prompts_path.exists():
        raise FileNotFoundError(f"Prompts file not found: {prompts_path}")
    with open(prompts_path, encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('levels', {})
