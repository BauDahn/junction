import { ApiError, normalizeSourcesDeep, type Source } from './index';
import type { MatchMode } from '../mode';
import { authFetch } from './auth';

export type FeedCard = {
  id: string;
  type: 'investor' | 'startup';
  name: string;
  one_liner: string;
  tags: string[];
  score: number;
  confidence: number;
  why_match: string[];
  sources: Source[];
};

export type FeedResponse = {
  mode: MatchMode;
  items: FeedCard[];
  next_cursor?: string;
  confidence_note?: string;
  is_sample?: boolean;
};

export type GetFeedParams = {
  sessionId: string;
  mode: MatchMode;
  limit?: number;
  cursor?: string;
  fallbackOnNetworkError?: boolean;
};

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

const makeSamples = (type: FeedCard['type']): FeedCard[] => [1, 2, 3].map((n) => ({
  id: `sample-${type}-${n}`,
  type,
  name: type === 'investor' ? `Sample Fund ${['One', 'Two', 'Three'][n - 1]}` : `Sample Startup ${['One', 'Two', 'Three'][n - 1]}`,
  one_liner: 'Placeholder entry shown only while the backend is offline.',
  tags: [], score: 0, confidence: 0,
  why_match: ['Placeholder sample, not Cala data'], sources: [],
}));
const MOCK_RAISING = makeSamples('investor');
const MOCK_INVESTING = makeSamples('startup');

export function getMockFeed(
  mode: MatchMode,
  note = 'Sample data: the backend is offline, so these are placeholders.',
): FeedResponse {
  return {
    mode,
    items: mode === 'raising' ? MOCK_RAISING : MOCK_INVESTING,
    confidence_note: note,
    is_sample: true,
  };
}

/**
 * Fetches ranked matches from GET /api/feed, falling back cleanly to sample data if the backend is offline.
 */
export async function getFeed({
  sessionId,
  mode,
  limit = 20,
  cursor,
  fallbackOnNetworkError = true,
}: GetFeedParams): Promise<FeedResponse> {
  if (mockEnabled) {
    return getMockFeed(mode, 'Sample mode enabled.');
  }

  const query = new URLSearchParams({
    session_id: sessionId,
    mode,
    limit: String(limit),
  });
  if (cursor) {
    query.set('cursor', cursor);
  }

  try {
    const response = await authFetch(`${baseUrl}/api/feed?${query.toString()}`);
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      throw new ApiError(
        payload?.error?.code ?? 'http_error',
        payload?.error?.message ?? payload?.detail ?? `Request failed with status ${response.status}.`,
        response.status,
      );
    }
    return normalizeSourcesDeep(body) as FeedResponse;
  } catch (err) {
    if (err instanceof ApiError) {
      throw err;
    }
    if (fallbackOnNetworkError) {
      return getMockFeed(mode);
    }
    throw new Error(
      err instanceof Error ? err.message : 'Unable to reach the server. Check your connection.',
    );
  }
}
