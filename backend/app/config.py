"""Application settings, loaded from environment variables and `backend/.env`.

pydantic-settings reads each field from an env var with the same name in upper
case (e.g. `groq_base_url` <- `GROQ_BASE_URL`) and validates its type. Model
IDs and base URLs have no defaults in code on purpose, so `.env` is the
single source of truth for which models we call.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["groq", "nvidia"]

# Resolve `.env` relative to the backend folder so it is found no matter
# which directory you start the server from.
BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Groq ---
    groq_api_key: str = ""
    groq_base_url: str
    groq_vision_model: str
    groq_json_mode: bool = True
    # Dict fields are parsed from JSON strings in the env, e.g. {"reasoning_effort": "none"}.
    groq_extra_body: dict[str, Any] = Field(default_factory=dict)

    # --- NVIDIA NIM ---
    nvidia_api_key: str = ""
    nvidia_base_url: str
    nvidia_vision_model: str
    nvidia_json_mode: bool = False
    nvidia_extra_body: dict[str, Any] = Field(default_factory=dict)

    # --- Behaviour ---
    primary_provider: ProviderName = "groq"
    request_timeout_s: float = Field(default=30.0, gt=0)
    max_upload_mb: int = Field(default=10, gt=0)
    wikipedia_user_agent: str = "CarSpotter/0.1 (learning project)"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (the env is only read once)."""
    return Settings()  # type: ignore[call-arg]  # required fields come from the env
