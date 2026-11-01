/**
 * API types. These mirror the Pydantic models in `backend/app/schemas.py`
 * field-for-field (snake_case included). If you change one side, change the other.
 */

/** One possible identification of the car in the photo. */
export interface CarCandidate {
  make: string;
  model: string;
  generation_or_years: string | null;
  body_type: string | null;
  /** 0 to 1. */
  confidence: number;
}

/** POST /identify response. */
export interface IdentifyResponse {
  is_car: boolean;
  /** Up to 3, sorted by confidence (highest first). Empty if not a car or too unclear. */
  candidates: CarCandidate[];
  visible_clues: string;
  /** Added by the backend: which AI provider answered ("groq" | "nvidia"). */
  provider: string;
  /** Added by the backend: time spent calling that provider. */
  latency_ms: number;
}

/** GET /facts response. */
export interface FactsResponse {
  title: string;
  summary: string;
  source_url: string;
  thumbnail_url: string | null;
}

/** GET /health response. */
export interface HealthResponse {
  status: 'ok';
  primary_provider: string;
  providers: string[];
}

/** `code` values the backend can return (ApiError in schemas.py). */
export type BackendErrorCode =
  | 'invalid_image'
  | 'image_too_large'
  | 'no_providers_configured'
  | 'providers_unavailable'
  | 'invalid_model_output'
  | 'facts_not_found'
  | 'facts_unavailable';

/** Body of every error response from the backend. */
export interface ApiErrorBody {
  code: BackendErrorCode;
  message: string;
}
