"""VisionProvider request shape, network retry, and provider ordering.

The OpenAI SDK sends requests through httpx2, so we give it an httpx2 client
with a MockTransport: real SDK code runs, but no request leaves the machine.
"""

import json
from collections.abc import Callable

import httpx2
import pytest
from openai import AsyncOpenAI

from app.providers import ProviderError, VisionProvider, build_providers
from tests.conftest import car_json, make_settings

Handler = Callable[[httpx2.Request], httpx2.Response]
IMAGE = "data:image/jpeg;base64,AAAA"


def completion(text: str) -> httpx2.Response:
    return httpx2.Response(200, json={
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": text}}],
    })


def make_provider(handler: Handler, **kwargs) -> VisionProvider:
    client = AsyncOpenAI(
        api_key="k", base_url="https://provider.test/v1", max_retries=0,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    return VisionProvider(name="test", base_url="unused", api_key="k", model="vision-model",
                          client=client, **kwargs)


async def complete(provider: VisionProvider):
    return await provider.complete(system_prompt="sys", user_prompt="user", image_data_url=IMAGE)


async def test_request_contains_image_model_and_provider_options() -> None:
    seen: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return completion(car_json())

    provider = make_provider(handler, json_mode=True, extra_body={"reasoning_effort": "none"})
    result = await complete(provider)

    body = seen[0]
    assert body["model"] == "vision-model"
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_effort"] == "none"  # extra_body is merged into the JSON
    user_content = body["messages"][1]["content"]
    assert {"type": "image_url", "image_url": {"url": IMAGE}} in user_content
    assert "Mazda" in result.text
    assert result.latency_ms >= 0


async def test_json_mode_off_sends_no_response_format() -> None:
    seen: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return completion("{}")

    await complete(make_provider(handler, json_mode=False))
    assert "response_format" not in seen[0]


async def test_retries_once_on_network_error() -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx2.ConnectError("connection reset", request=request)
        return completion("{}")

    result = await complete(make_provider(handler))
    assert calls == 2
    assert result.text == "{}"


async def test_gives_up_after_second_network_error() -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        raise httpx2.ConnectError("down", request=request)

    with pytest.raises(ProviderError, match="network error"):
        await complete(make_provider(handler))
    assert calls == 2


async def test_http_errors_are_not_retried() -> None:
    calls = 0

    def handler(request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(401, json={"error": {"message": "bad key"}})

    with pytest.raises(ProviderError, match="HTTP 401"):
        await complete(make_provider(handler))
    assert calls == 1


def test_build_providers_puts_primary_first() -> None:
    assert [p.name for p in build_providers(make_settings(primary_provider="nvidia"))] == ["nvidia", "groq"]
    assert [p.name for p in build_providers(make_settings(primary_provider="groq"))] == ["groq", "nvidia"]


def test_build_providers_skips_providers_without_keys() -> None:
    assert [p.name for p in build_providers(make_settings(groq_api_key=""))] == ["nvidia"]
