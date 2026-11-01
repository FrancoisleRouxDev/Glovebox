"""Fallback between providers and invalid-JSON handling."""

import pytest

from app.identify import IdentificationError, identify_car
from app.prompts import SYSTEM_PROMPT
from tests.conftest import NOT_A_CAR_JSON, FakeProvider, car_json, provider_down

IMAGE = "data:image/jpeg;base64,AAAA"


async def test_primary_success_does_not_touch_fallback() -> None:
    primary = FakeProvider("groq", [car_json()], latency_ms=250)
    fallback = FakeProvider("nvidia", [car_json()])

    result = await identify_car(IMAGE, [primary, fallback])

    assert result.provider == "groq"
    assert result.latency_ms == 250
    assert result.candidates[0].model == "MX-5"
    assert fallback.call_count == 0


async def test_falls_back_when_primary_errors() -> None:
    primary = FakeProvider("groq", [provider_down("groq")])
    fallback = FakeProvider("nvidia", [car_json()])

    result = await identify_car(IMAGE, [primary, fallback])

    assert result.provider == "nvidia"
    assert primary.call_count == 1 and fallback.call_count == 1


async def test_invalid_json_retries_once_with_stricter_prompt() -> None:
    primary = FakeProvider("groq", ["not json at all", car_json()], latency_ms=100)

    result = await identify_car(IMAGE, [primary])

    assert result.provider == "groq"
    assert primary.call_count == 2
    assert primary.system_prompts[0] == SYSTEM_PROMPT
    assert "previous answer could not be parsed" in primary.system_prompts[1]
    assert result.latency_ms == 200  # both calls count toward latency


async def test_invalid_json_twice_falls_back_to_other_provider() -> None:
    primary = FakeProvider("groq", ["nope", "{bad json"])
    fallback = FakeProvider("nvidia", [car_json()])

    result = await identify_car(IMAGE, [primary, fallback])

    assert result.provider == "nvidia"
    assert primary.call_count == 2


async def test_invalid_json_everywhere_gives_clear_error() -> None:
    providers = [FakeProvider("groq", ["x", "y"]), FakeProvider("nvidia", ["x", "y"])]

    with pytest.raises(IdentificationError) as err:
        await identify_car(IMAGE, providers)

    assert err.value.code == "invalid_model_output"


async def test_all_providers_down_gives_unavailable_error() -> None:
    providers = [FakeProvider("groq", [provider_down("groq")]),
                 FakeProvider("nvidia", [provider_down("nvidia")])]

    with pytest.raises(IdentificationError) as err:
        await identify_car(IMAGE, providers)

    assert err.value.code == "providers_unavailable"


async def test_no_providers_configured() -> None:
    with pytest.raises(IdentificationError) as err:
        await identify_car(IMAGE, [])
    assert err.value.code == "no_providers_configured"


async def test_not_a_car_is_a_valid_answer_not_a_failure() -> None:
    primary = FakeProvider("groq", [NOT_A_CAR_JSON])
    fallback = FakeProvider("nvidia", [car_json()])

    result = await identify_car(IMAGE, [primary, fallback])

    assert result.is_car is False
    assert result.candidates == []
    assert fallback.call_count == 0  # "no car" must not trigger a fallback guess
