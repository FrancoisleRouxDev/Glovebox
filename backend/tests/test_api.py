"""HTTP-level tests for /health, /identify and /facts."""

from collections.abc import Callable

import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app, get_http_client
from tests.conftest import (
    NOT_A_CAR_JSON, FakeProvider, car_json, jpeg_bytes, make_settings, provider_down, use_providers,
)


def upload(client: TestClient, data: bytes):
    return client.post("/identify", files={"image": ("car.jpg", data, "image/jpeg")})


# --- /health ---

def test_health_lists_configured_providers(client: TestClient) -> None:
    use_providers(FakeProvider("groq", []), FakeProvider("nvidia", []))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "primary_provider": "groq", "providers": ["groq", "nvidia"]}


# --- /identify ---

def test_identify_returns_validated_result_with_backend_fields(client: TestClient) -> None:
    use_providers(FakeProvider("groq", [car_json()], latency_ms=321))

    resp = upload(client, jpeg_bytes())

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_car"] is True
    assert body["provider"] == "groq" and body["latency_ms"] == 321
    assert [c["make"] for c in body["candidates"]] == ["Mazda", "Fiat"]
    assert set(body["candidates"][0]) == {"make", "model", "generation_or_years", "body_type", "confidence"}


def test_identify_not_a_car(client: TestClient) -> None:
    use_providers(FakeProvider("groq", [NOT_A_CAR_JSON]))
    body = upload(client, jpeg_bytes()).json()
    assert body["is_car"] is False and body["candidates"] == []


def test_identify_uses_fallback_provider(client: TestClient) -> None:
    use_providers(FakeProvider("groq", [provider_down("groq")]), FakeProvider("nvidia", [car_json()]))
    assert upload(client, jpeg_bytes()).json()["provider"] == "nvidia"


def test_identify_rejects_non_image(client: TestClient) -> None:
    use_providers(FakeProvider("groq", []))
    resp = upload(client, b"hello")
    assert resp.status_code == 400
    assert resp.json()["code"] == "invalid_image"


def test_identify_rejects_oversized_upload(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: make_settings(max_upload_mb=1)
    use_providers(FakeProvider("groq", []))
    resp = upload(client, b"0" * (1024 * 1024 + 10))
    assert resp.status_code == 413
    assert resp.json()["code"] == "image_too_large"


def test_identify_all_providers_failing_returns_clear_error(client: TestClient) -> None:
    use_providers(FakeProvider("groq", ["bad", "bad"]), FakeProvider("nvidia", [provider_down("nvidia")]))
    resp = upload(client, jpeg_bytes())
    assert resp.status_code == 502
    assert resp.json()["code"] == "invalid_model_output"
    assert resp.json()["message"]


def test_identify_with_no_providers_configured(client: TestClient) -> None:
    use_providers()
    resp = upload(client, jpeg_bytes())
    assert resp.status_code == 503
    assert resp.json()["code"] == "no_providers_configured"


# --- /facts ---

def fake_wikipedia(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    mock = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    app.dependency_overrides[get_http_client] = lambda: mock


def _summary(title: str, page_type: str = "standard") -> dict:
    return {
        "type": page_type, "title": title, "extract": f"{title} is a car.",
        "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"}},
    }


def test_facts_picks_page_matching_make_and_model(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/w/api.php":
            assert request.url.params["srsearch"] == "Mazda MX-5"
            return httpx.Response(200, json={"query": {"search": [
                {"title": "Roadster (automobile)"}, {"title": "Mazda MX-5"}]}})
        assert request.url.path.endswith("/Mazda_MX-5")
        return httpx.Response(200, json=_summary("Mazda MX-5"))

    fake_wikipedia(handler)
    resp = client.get("/facts", params={"make": "Mazda", "model": "MX-5"})

    assert resp.status_code == 200
    assert resp.json() == {
        "title": "Mazda MX-5",
        "summary": "Mazda MX-5 is a car.",
        "source_url": "https://en.wikipedia.org/wiki/Mazda_MX-5",
        "thumbnail_url": None,
    }


def test_facts_skips_disambiguation_pages(client: TestClient) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/w/api.php":
            return httpx.Response(200, json={"query": {"search": [
                {"title": "Ford Mustang (disambiguation)"}, {"title": "Ford Mustang"}]}})
        if "disambiguation" in request.url.path:
            return httpx.Response(200, json=_summary("Ford Mustang (disambiguation)", "disambiguation"))
        return httpx.Response(200, json=_summary("Ford Mustang"))

    fake_wikipedia(handler)
    assert client.get("/facts", params={"make": "Ford", "model": "Mustang"}).json()["title"] == "Ford Mustang"


def test_facts_not_found(client: TestClient) -> None:
    fake_wikipedia(lambda r: httpx.Response(200, json={"query": {"search": []}}))
    resp = client.get("/facts", params={"make": "Nope", "model": "Nothing"})
    assert resp.status_code == 404
    assert resp.json()["code"] == "facts_not_found"


def test_facts_wikipedia_down(client: TestClient) -> None:
    fake_wikipedia(lambda r: httpx.Response(503))
    resp = client.get("/facts", params={"make": "Ford", "model": "Focus"})
    assert resp.status_code == 502
    assert resp.json()["code"] == "facts_unavailable"


def test_facts_requires_make_and_model(client: TestClient) -> None:
    fake_wikipedia(lambda r: httpx.Response(500))  # must never be reached
    assert client.get("/facts", params={"make": "Ford"}).status_code == 422
