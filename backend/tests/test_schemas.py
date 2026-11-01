"""Schema validation and parsing of raw model replies."""

import json

import pytest
from pydantic import ValidationError

from app.identify import InvalidModelOutputError, parse_model_output
from app.schemas import ModelOutput
from tests.conftest import car_json


def _candidate(make: str, conf: float) -> dict:
    return {"make": make, "model": "X", "confidence": conf}


def test_candidates_are_sorted_by_confidence_and_capped_at_three() -> None:
    out = ModelOutput.model_validate({
        "is_car": True,
        "candidates": [_candidate("A", 0.1), _candidate("B", 0.9), _candidate("C", 0.5), _candidate("D", 0.3)],
    })
    assert [c.make for c in out.candidates] == ["B", "C", "D"]


def test_not_a_car_drops_any_candidates() -> None:
    out = ModelOutput.model_validate({"is_car": False, "candidates": [_candidate("A", 0.4)]})
    assert out.candidates == []


def test_optional_fields_may_be_null_or_missing() -> None:
    out = ModelOutput.model_validate({
        "is_car": True,
        "candidates": [{"make": "Ford", "model": "Focus", "generation_or_years": None, "confidence": 0.5}],
    })
    assert out.candidates[0].body_type is None
    assert out.visible_clues == ""


@pytest.mark.parametrize("bad", [
    {"is_car": True, "candidates": [_candidate("A", 1.5)]},     # confidence > 1
    {"is_car": True, "candidates": [_candidate("A", -0.1)]},    # confidence < 0
    {"is_car": True, "candidates": [{"make": "", "model": "X", "confidence": 0.5}]},  # empty make
    {"is_car": True, "candidates": [{"model": "X", "confidence": 0.5}]},  # missing make
    {"candidates": []},                                          # missing is_car
])
def test_invalid_shapes_are_rejected(bad: dict) -> None:
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(bad)


@pytest.mark.parametrize("wrap", [
    "{}",
    "```json\n{}\n```",
    "Sure! Here is the JSON:\n{}\nHope that helps.",
    "<think>Looks like a roadster {maybe}.</think>\n{}",
])
def test_parse_extracts_json_from_common_wrappers(wrap: str) -> None:
    out = parse_model_output(wrap.replace("{}", car_json(), 1) if wrap != "{}" else car_json())
    assert out.is_car is True
    assert out.candidates[0].make == "Mazda"


@pytest.mark.parametrize("text, reason", [
    ("I think it's a Mazda.", "did not contain a JSON object"),
    ("{'is_car': true}", "invalid JSON"),
    (json.dumps({"is_car": "maybe"}), "did not match schema"),
])
def test_parse_rejects_bad_output_with_clear_reason(text: str, reason: str) -> None:
    with pytest.raises(InvalidModelOutputError, match=reason):
        parse_model_output(text)
