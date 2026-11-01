"""Vision model providers.

Groq and NVIDIA NIM both expose OpenAI-compatible APIs, so one class covers
both. Each instance is configured with a name, base URL, API key and model.

`VisionClient` is the small interface the rest of the app depends on. Tests
replace real providers with fakes that implement it.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import openai
from openai import AsyncOpenAI

from app.config import Settings

logger = logging.getLogger(__name__)

# Network problems get exactly one retry; anything else fails fast.
_NETWORK_ERRORS: tuple[type[Exception], ...] = (
    openai.APIConnectionError,  # also covers openai.APITimeoutError
)
MAX_OUTPUT_TOKENS = 600


class ProviderError(Exception):
    """A provider call failed (network, auth, rate limit, server error, ...)."""

    def __init__(self, provider: str, message: str):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider


@dataclass(frozen=True)
class CompletionResult:
    text: str
    latency_ms: int


class VisionClient(Protocol):
    """What the identify logic needs from a provider."""

    name: str

    async def complete(
        self, *, system_prompt: str, user_prompt: str, image_data_url: str
    ) -> CompletionResult: ...


class VisionProvider:
    """An OpenAI-compatible chat completions endpoint that accepts images."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float = 30.0,
        json_mode: bool = False,
        extra_body: dict[str, Any] | None = None,
        client: AsyncOpenAI | None = None,
    ):
        self.name = name
        self.model = model
        self.json_mode = json_mode
        self.extra_body = extra_body or {}
        # We do our own retry so we control exactly when it happens and can log it,
        # so the SDK's built-in retries are turned off (max_retries=0).
        self._client = client or AsyncOpenAI(
            base_url=base_url, api_key=api_key, timeout=timeout_s, max_retries=0
        )

    async def complete(
        self, *, system_prompt: str, user_prompt: str, image_data_url: str
    ) -> CompletionResult:
        """Send one image plus prompts and return the model's raw text reply."""
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,  # Low randomness: we want consistent identifications.
            "max_tokens": MAX_OUTPUT_TOKENS,
        }
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self.extra_body:
            # Provider-specific fields (e.g. reasoning switches) get merged into the request JSON.
            kwargs["extra_body"] = self.extra_body

        for attempt in (1, 2):
            start = time.perf_counter()
            try:
                response = await self._client.chat.completions.create(**kwargs)
            except _NETWORK_ERRORS as exc:
                latency_ms = _elapsed_ms(start)
                logger.warning(
                    "provider=%s model=%s attempt=%d network error after %dms: %s",
                    self.name, self.model, attempt, latency_ms, exc,
                )
                if attempt == 1:
                    continue  # one retry
                raise ProviderError(self.name, f"network error: {exc}") from exc
            except openai.APIStatusError as exc:
                # 4xx/5xx from the API: bad key, unknown model, rate limit, outage...
                logger.warning(
                    "provider=%s model=%s HTTP %s after %dms: %s",
                    self.name, self.model, exc.status_code, _elapsed_ms(start), exc.message,
                )
                raise ProviderError(self.name, f"HTTP {exc.status_code}: {exc.message}") from exc

            latency_ms = _elapsed_ms(start)
            logger.info(
                "provider=%s model=%s attempt=%d latency_ms=%d",
                self.name, self.model, attempt, latency_ms,
            )
            text = response.choices[0].message.content if response.choices else None
            if not text:
                raise ProviderError(self.name, "empty response from model")
            return CompletionResult(text=text, latency_ms=latency_ms)

        raise AssertionError("unreachable")  # the loop always returns or raises


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def build_providers(settings: Settings) -> list[VisionProvider]:
    """Create providers that have an API key, primary first, fallback second."""
    all_providers = {
        "groq": VisionProvider(
            name="groq",
            base_url=settings.groq_base_url,
            api_key=settings.groq_api_key,
            model=settings.groq_vision_model,
            timeout_s=settings.request_timeout_s,
            json_mode=settings.groq_json_mode,
            extra_body=settings.groq_extra_body,
        )
        if settings.groq_api_key
        else None,
        "nvidia": VisionProvider(
            name="nvidia",
            base_url=settings.nvidia_base_url,
            api_key=settings.nvidia_api_key,
            model=settings.nvidia_vision_model,
            timeout_s=settings.request_timeout_s,
            json_mode=settings.nvidia_json_mode,
            extra_body=settings.nvidia_extra_body,
        )
        if settings.nvidia_api_key
        else None,
    }
    order = [settings.primary_provider] + [n for n in all_providers if n != settings.primary_provider]
    return [p for name in order if (p := all_providers[name]) is not None]
