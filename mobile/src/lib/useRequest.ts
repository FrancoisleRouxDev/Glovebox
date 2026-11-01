/**
 * Tiny data-fetching hook used by every screen that calls the backend.
 *
 * - Starts in 'loading', runs `fetcher` on mount, and ends in 'success' or 'error'.
 * - Aborts the request on unmount, so leaving a screen cancels its upload.
 * - `retry()` puts the state back to 'loading' and runs the fetcher again.
 *
 * `fetcher` must be stable (wrap it in useCallback), otherwise it would re-run on every render.
 */
import { useCallback, useEffect, useState } from 'react';

export type RequestState<T> =
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: unknown };

export function useRequest<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
): [RequestState<T>, () => void] {
  const [state, setState] = useState<RequestState<T>>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    fetcher(controller.signal).then(
      (data) => setState({ status: 'success', data }),
      (error: unknown) => {
        // A cancelled request isn't an error the user needs to see.
        if (!controller.signal.aborted) setState({ status: 'error', error });
      },
    );
    return () => controller.abort();
  }, [fetcher, attempt]);

  const retry = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((n) => n + 1);
  }, []);

  return [state, retry];
}
