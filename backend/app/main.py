"""FastAPI app: HTTP routes that wire the pieces together.

Run from the `backend/` folder:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
`--host 0.0.0.0` matters: it lets your phone reach the server over Wi-Fi.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.identify import IdentificationError, identify_car
from app.image_prep import InvalidImageError, prepare_image
from app.providers import VisionClient, build_providers
from app.schemas import ApiError, ErrorCode, FactsResponse, HealthResponse, IdentifyResponse
from app.wikipedia import FactsUnavailableError, fetch_car_facts

logger = logging.getLogger(__name__)


class ApiException(Exception):
    """Raise this from a route to return an `ApiError` body with the given status."""

    def __init__(self, status_code: int, code: ErrorCode, message: str):
        self.status_code = status_code
        self.error = ApiError(code=code, message=message)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create long-lived clients once at startup and close them on shutdown."""
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app.state.providers = build_providers(settings)
    app.state.http = httpx.AsyncClient(
        timeout=10.0, headers={"User-Agent": settings.wikipedia_user_agent}
    )
    logger.info("providers in order: %s", [p.name for p in app.state.providers] or "NONE")
    yield
    await app.state.http.aclose()


app = FastAPI(title="Car Spotter API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(ApiException)
async def _api_exception_handler(_: Request, exc: ApiException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.error.model_dump())


# --- Dependencies (overridden in tests) -------------------------------------------


def get_providers(request: Request) -> list[VisionClient]:
    return request.app.state.providers


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


SettingsDep = Annotated[Settings, Depends(get_settings)]
ProvidersDep = Annotated[list[VisionClient], Depends(get_providers)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

_ERROR_RESPONSES = {
    code: {"model": ApiError} for code in (400, 413, 502, 503)
}


# --- Routes -----------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health(settings: SettingsDep, providers: ProvidersDep) -> HealthResponse:
    return HealthResponse(
        primary_provider=settings.primary_provider, providers=[p.name for p in providers]
    )


@app.post("/identify", response_model=IdentifyResponse, responses=_ERROR_RESPONSES)
async def identify(
    settings: SettingsDep,
    providers: ProvidersDep,
    image: Annotated[UploadFile, File(description="Photo of a car (JPEG, PNG, ...).")],
) -> IdentifyResponse:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    raw = await image.read(max_bytes + 1)  # read one extra byte to detect oversize files
    if len(raw) > max_bytes:
        raise ApiException(413, "image_too_large", f"Image is larger than {settings.max_upload_mb} MB.")
    if not raw:
        raise ApiException(400, "invalid_image", "The uploaded file is empty.")

    try:
        prepared = prepare_image(raw)
    except InvalidImageError:
        raise ApiException(400, "invalid_image", "That file isn't an image we can read.") from None

    try:
        return await identify_car(prepared.data_url, providers)
    except IdentificationError as exc:
        status = 503 if exc.code == "no_providers_configured" else 502
        raise ApiException(status, exc.code, exc.message) from exc


@app.get("/facts", response_model=FactsResponse, responses={404: {"model": ApiError}, 502: {"model": ApiError}})
async def facts(
    http: HttpDep,
    make: Annotated[str, Query(min_length=1, max_length=100)],
    model: Annotated[str, Query(min_length=1, max_length=100)],
) -> FactsResponse:
    try:
        result = await fetch_car_facts(http, make.strip(), model.strip())
    except FactsUnavailableError as exc:
        raise ApiException(502, "facts_unavailable", "Couldn't reach Wikipedia right now.") from exc
    if result is None:
        raise ApiException(404, "facts_not_found", f"No Wikipedia page found for {make} {model}.")
    return result
