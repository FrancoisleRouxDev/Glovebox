"""Shared test helpers. No test here ever calls a real AI provider or Wikipedia."""

import io
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings, get_settings
from app.main import app, get_providers
from app.providers import CompletionResult, ProviderError


def make_settings(**overrides: Any) -> Settings:
    """Settings built in code, so tests never depend on your real .env."""
    values: dict[str, Any] = {
        "groq_api_key": "test-groq",
        "groq_base_url": "https://groq.test/v1",
        "groq_vision_model": "groq-test-model",
        "nvidia_api_key": "test-nvidia",
        "nvidia_base_url": "https://nvidia.test/v1",
        "nvidia_vision_model": "nvidia-test-model",
        "primary_provider": "groq",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class FakeProvider:
    """Stands in for VisionProvider. Replays scripted replies (text or exceptions) in order."""

    def __init__(self, name: str, replies: list[str | Exception], latency_ms: int = 100):
        self.name = name
        self._replies = list(replies)
        self.latency_ms = latency_ms
        self.system_prompts: list[str] = []

    @property
    def call_count(self) -> int:
        return len(self.system_prompts)

    async def complete(
        self, *, system_prompt: str, user_prompt: str, image_data_url: str
    ) -> CompletionResult:
        self.system_prompts.append(system_prompt)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return CompletionResult(text=reply, latency_ms=self.latency_ms)


def provider_down(name: str) -> ProviderError:
    return ProviderError(name, "network error: connection refused")


def car_json(**overrides: Any) -> str:
    """A valid model reply, as the JSON text a model would send back."""
    body: dict[str, Any] = {
        "is_car": True,
        "candidates": [
            {"make": "Mazda", "model": "MX-5", "generation_or_years": "ND (2015-present)",
             "body_type": "roadster", "confidence": 0.81},
            {"make": "Fiat", "model": "124 Spider", "generation_or_years": "2016-2020",
             "body_type": "roadster", "confidence": 0.12},
        ],
        "visible_clues": "Small two-seat roadster, Mazda grille shape.",
    }
    body.update(overrides)
    return json.dumps(body)


NOT_A_CAR_JSON = json.dumps({"is_car": False, "candidates": [], "visible_clues": "A cat on a sofa."})


def jpeg_bytes(width: int = 64, height: int = 48, color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Test client with fake settings. Tests set providers via `use_providers`."""
    app.dependency_overrides[get_settings] = lambda: make_settings()
    # Not used as a context manager, so the real lifespan (real clients) never runs.
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_providers(*providers: FakeProvider) -> None:
    app.dependency_overrides[get_providers] = lambda: list(providers)
