"""Core identification pipeline: prompt a provider, validate the JSON, fall back if needed.

For each provider, in order (primary first):
1. Ask the model with the normal prompt.
2. If the reply isn't valid JSON matching `ModelOutput`, ask once more with a
   stricter prompt.
3. If that fails too, or the provider itself errors, move on to the next provider.
If every provider fails, raise `IdentificationError` with a clear code and message.
"""

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.prompts import SYSTEM_PROMPT, USER_PROMPT, strict_system_prompt
from app.providers import ProviderError, VisionClient
from app.schemas import ErrorCode, IdentifyResponse, ModelOutput

logger = logging.getLogger(__name__)


class InvalidModelOutputError(Exception):
    """The model's reply wasn't valid JSON or didn't match the schema."""


class IdentificationError(Exception):
    """Every provider failed. `code` matches `ApiError.code`."""

    def __init__(self, code: ErrorCode, message: str):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message


@dataclass(frozen=True)
class ProviderAnswer:
    output: ModelOutput
    latency_ms: int  # total time spent on this provider, including the JSON retry


# Some models wrap answers in reasoning tags or markdown fences even when asked not to.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_model_output(text: str) -> ModelOutput:
    """Extract and validate the JSON object from a model reply.

    Raises InvalidModelOutputError with a short, human-readable reason.
    """
    cleaned = _THINK_BLOCK.sub("", text).strip()
    # Take everything from the first "{" to the last "}". This drops ```json fences
    # and any chatter before or after the object.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise InvalidModelOutputError("reply did not contain a JSON object")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidModelOutputError(f"invalid JSON: {exc.msg}") from exc
    try:
        return ModelOutput.model_validate(data)
    except ValidationError as exc:
        # Summarise the errors as "field: problem; ..." for logs and the retry prompt.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'root'}: {err['msg']}" for err in exc.errors()
        )
        raise InvalidModelOutputError(f"JSON did not match schema: {problems}") from exc


async def identify_with_provider(provider: VisionClient, image_data_url: str) -> ProviderAnswer:
    """Ask one provider, retrying once with a stricter prompt if the JSON is invalid.

    Raises ProviderError (call failed) or InvalidModelOutputError (bad JSON twice).
    """
    first = await provider.complete(
        system_prompt=SYSTEM_PROMPT, user_prompt=USER_PROMPT, image_data_url=image_data_url
    )
    try:
        return ProviderAnswer(parse_model_output(first.text), first.latency_ms)
    except InvalidModelOutputError as exc:
        logger.warning("provider=%s invalid output, retrying strictly: %s", provider.name, exc)
        first_error = str(exc)

    second = await provider.complete(
        system_prompt=strict_system_prompt(first_error),
        user_prompt=USER_PROMPT,
        image_data_url=image_data_url,
    )
    total_ms = first.latency_ms + second.latency_ms
    # If this raises too, the caller treats the provider as failed.
    return ProviderAnswer(parse_model_output(second.text), total_ms)


async def identify_car(
    image_data_url: str, providers: Sequence[VisionClient]
) -> IdentifyResponse:
    """Run the image through providers in order until one gives a valid answer."""
    if not providers:
        raise IdentificationError(
            "no_providers_configured",
            "No AI provider is configured. Set GROQ_API_KEY and/or NVIDIA_API_KEY in backend/.env.",
        )

    saw_invalid_output = False
    failures: list[str] = []
    for provider in providers:
        try:
            answer = await identify_with_provider(provider, image_data_url)
        except ProviderError as exc:
            failures.append(str(exc))
            logger.warning("provider=%s failed, trying next: %s", provider.name, exc)
            continue
        except InvalidModelOutputError as exc:
            saw_invalid_output = True
            failures.append(f"[{provider.name}] {exc}")
            logger.warning("provider=%s gave invalid output twice: %s", provider.name, exc)
            continue

        return IdentifyResponse(
            **answer.output.model_dump(), provider=provider.name, latency_ms=answer.latency_ms
        )

    logger.error("all providers failed: %s", " | ".join(failures))
    if saw_invalid_output:
        raise IdentificationError(
            "invalid_model_output",
            "The AI model returned an answer we couldn't understand. Please try again.",
        )
    raise IdentificationError(
        "providers_unavailable",
        "The AI providers are unavailable right now. Please try again in a moment.",
    )
