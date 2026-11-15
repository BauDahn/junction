import { ApiError } from './index';

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const REPORT_TIMEOUT_MS = 100_000;

type FavoritesReportOptions = {
  sessionId?: string | null;
  authToken?: string | null;
  mode?: 'raising' | 'investing';
  signal?: AbortSignal;
};

export async function requestFavoritesReport(
  entityIds: string[],
  opts: FavoritesReportOptions = {},
): Promise<{ blob: Blob; notIncluded: string[] }> {
  if (process.env.EXPO_PUBLIC_MOCK === '1') {
    throw new ApiError('mock_unavailable', 'The PDF report needs the live backend.', 503);
  }

  const ids = [...new Set(entityIds)].slice(0, 10);
  const controller = new AbortController();
  const abortFromCaller = () => controller.abort();
  if (opts.signal?.aborted) controller.abort();
  else opts.signal?.addEventListener('abort', abortFromCaller, { once: true });
  const timer = setTimeout(() => controller.abort(), REPORT_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetch(`${baseUrl}/api/favorites/report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(opts.authToken ? { Authorization: `Bearer ${opts.authToken}` } : {}),
        },
        body: JSON.stringify({
          entity_ids: ids,
          ...(opts.sessionId ? { session_id: opts.sessionId } : {}),
          ...(opts.mode ? { mode: opts.mode } : {}),
        }),
        signal: controller.signal,
      });
    } catch (error) {
      if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) {
        throw new ApiError('report_timeout', 'The report took too long. Try again.', 504);
      }
      throw new ApiError('network_error', 'Cannot reach the server.', 0);
    }

    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const payload = body as { error?: { code?: string; message?: string } } | null;
      const stateMessages: Record<number, string> = {
        401: 'Sign in to download the report.',
        422: 'Some favorites are not valid Cala entities.',
        429: 'Too many reports. Try again in a minute.',
        404: 'None of your favorites were found in Cala.',
        503: 'Cala reached its daily call limit. Try again later.',
        502: 'Cala could not load your favorites right now.',
        504: 'The report took too long. Try again.',
      };
      throw new ApiError(
        payload?.error?.code ?? 'http_error',
        stateMessages[response.status] ?? payload?.error?.message ?? `Request failed (${response.status}).`,
        response.status,
      );
    }

    let blob: Blob;
    try {
      blob = await response.blob();
    } catch (error) {
      if (controller.signal.aborted || (error instanceof Error && error.name === 'AbortError')) {
        throw new ApiError('report_timeout', 'The report took too long. Try again.', 504);
      }
      throw new ApiError('network_error', 'Cannot reach the server.', 0);
    }
    const notIncludedHeader = response.headers.get('X-Favorites-Not-Included') ?? '';
    const notIncluded = notIncludedHeader.split(',').map((id) => id.trim()).filter(Boolean);
    return { blob, notIncluded };
  } finally {
    clearTimeout(timer);
    opts.signal?.removeEventListener('abort', abortFromCaller);
  }
}
