/**
 * Typed client for the Car Spotter backend.
 *
 * The app never talks to AI providers directly and never holds API keys.
 * It only talks to our backend, whose address comes from EXPO_PUBLIC_API_URL
 * (set in mobile/.env). On a phone this must be your computer's LAN IP, e.g.
 * http://192.168.1.20:8000. "localhost" on a phone means the phone itself.
 */
import type {
  ApiErrorBody,
  BackendErrorCode,
  FactsResponse,
  HealthResponse,
  IdentifyResponse,
} from './types';

// Must be written exactly like this (not process.env[name]) so Expo can inline it at build time.
const API_URL = process.env.EXPO_PUBLIC_API_URL?.replace(/\/+$/, '');

/** Errors the client itself can produce, in addition to the backend's codes. */
export type ClientErrorCode = 'not_configured' | 'network_error' | 'timeout' | 'unexpected_response';

export class ApiError extends Error {
  constructor(
    public readonly code: BackendErrorCode | ClientErrorCode,
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getApiUrl(): string | undefined {
  return API_URL;
}

const DEFAULT_TIMEOUT_MS = 15_000;
// Identification may try two providers, each with retries, so allow plenty of time.
const IDENTIFY_TIMEOUT_MS = 120_000;

interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: FormData;
  timeoutMs?: number;
  /** Lets a screen cancel the request, e.g. when the user navigates away. */
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      'not_configured',
      'EXPO_PUBLIC_API_URL is not set. Add it to mobile/.env and restart Expo.',
    );
  }

  // One AbortController handles both our timeout and the caller's cancel signal.
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const onCallerAbort = () => controller.abort();
  options.signal?.addEventListener('abort', onCallerAbort);

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: options.method ?? 'GET',
      body: options.body,
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
  } catch (err) {
    if (timedOut) {
      throw new ApiError('timeout', 'The server took too long to respond. Please try again.');
    }
    if (options.signal?.aborted) throw err; // the caller cancelled; let them ignore it
    throw new ApiError(
      'network_error',
      `Can't reach the backend at ${API_URL}. Is it running with --host 0.0.0.0, and is your phone on the same Wi-Fi?`,
    );
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', onCallerAbort);
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new ApiError('unexpected_response', `Unexpected response from server (HTTP ${response.status}).`, response.status);
  }

  if (!response.ok) {
    if (isApiErrorBody(data)) throw new ApiError(data.code, data.message, response.status);
    // e.g. FastAPI's own 422 validation errors, which have a different shape.
    throw new ApiError('unexpected_response', `Request failed (HTTP ${response.status}).`, response.status);
  }
  // We trust the backend to match ./types.ts (both sides are kept in sync by hand).
  return data as T;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ApiErrorBody).code === 'string' &&
    typeof (value as ApiErrorBody).message === 'string'
  );
}

/** Is the backend reachable, and which providers does it have? */
export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal, timeoutMs: 5_000 });
}

/** Upload a local photo (file:// URI, already resized to JPEG) and get up to 3 guesses. */
export function identifyCar(photoUri: string, signal?: AbortSignal): Promise<IdentifyResponse> {
  const form = new FormData();
  // React Native's FormData accepts { uri, name, type } for files. The DOM
  // typings don't know about that shape, hence the cast.
  form.append('image', { uri: photoUri, name: 'photo.jpg', type: 'image/jpeg' } as unknown as Blob);
  return request<IdentifyResponse>('/identify', {
    method: 'POST',
    body: form,
    timeoutMs: IDENTIFY_TIMEOUT_MS,
    signal,
  });
}

/** Wikipedia summary for a make/model. Throws ApiError with code 'facts_not_found' on 404. */
export function getFacts(make: string, model: string, signal?: AbortSignal): Promise<FactsResponse> {
  const query = `make=${encodeURIComponent(make)}&model=${encodeURIComponent(model)}`;
  return request<FactsResponse>(`/facts?${query}`, { signal });
}
