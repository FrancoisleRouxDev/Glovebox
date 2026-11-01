"""Pydantic models for everything that crosses a boundary.

* `ModelOutput` is what we require the AI model to return.
* `IdentifyResponse`, `FactsResponse`, `HealthResponse` and `ApiError` are what
  our HTTP API returns. The mobile app mirrors these in
  `mobile/src/api/types.ts`. Keep the two files in sync.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

MAX_CANDIDATES = 3


class CarCandidate(BaseModel):
    """One possible identification of the car in the photo."""

    make: str = Field(min_length=1, description="Manufacturer, e.g. 'Toyota'.")
    model: str = Field(min_length=1, description="Model name, e.g. 'Corolla'.")
    generation_or_years: str | None = Field(
        default=None, description="Generation code or year range, e.g. 'E210 (2018-present)'."
    )
    body_type: str | None = Field(default=None, description="e.g. 'sedan', 'hatchback', 'SUV'.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model's confidence, 0 to 1.")


class ModelOutput(BaseModel):
    """The JSON the vision model must return. Validated before we trust it."""

    is_car: bool
    candidates: list[CarCandidate] = Field(default_factory=list)
    visible_clues: str = ""

    @model_validator(mode="after")
    def _normalise(self) -> "ModelOutput":
        # When there's no car we never want guesses, even if the model sent some.
        if not self.is_car:
            self.candidates = []
        # Sort here rather than trusting the model to order them, and keep the top 3.
        self.candidates = sorted(self.candidates, key=lambda c: c.confidence, reverse=True)[
            :MAX_CANDIDATES
        ]
        return self


class IdentifyResponse(ModelOutput):
    """Response of POST /identify: the model's answer plus backend metadata."""

    provider: str = Field(description="Which provider produced this answer.")
    latency_ms: int = Field(ge=0, description="Time spent calling that provider, in ms.")


class FactsResponse(BaseModel):
    """Response of GET /facts: a Wikipedia summary for a make/model."""

    title: str
    summary: str
    source_url: str
    thumbnail_url: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    primary_provider: str
    # Providers that have an API key configured, in the order they are tried.
    providers: list[str]


ErrorCode = Literal[
    "invalid_image",
    "image_too_large",
    "no_providers_configured",
    "providers_unavailable",
    "invalid_model_output",
    "facts_not_found",
    "facts_unavailable",
]


class ApiError(BaseModel):
    """Body of every error response from our API."""

    code: ErrorCode
    message: str
