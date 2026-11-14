import { ApiError, type Source } from './index';
import type { MatchMode } from '../mode';

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

const MOCK_RAISING: FeedCard[] = [
  {
    id: 'eight-roads-ventures',
    type: 'investor',
    name: 'Eight Roads Ventures',
    one_liner: 'Global venture investor backing European B2B SaaS and fintech scaleups.',
    tags: ['B2B SaaS (AI-tagged)', 'Series A (AI-tagged)', 'UK'],
    score: 92,
    confidence: 0.9,
    why_match: ['Led 3 European enterprise software rounds in the last 24 months'],
    sources: [{ name: 'Eight Roads Ventures', url: 'https://eightroads.com' }],
  },
  {
    id: 'chalfen-ventures',
    type: 'investor',
    name: 'Chalfen Ventures',
    one_liner: 'Solo-GP early-stage fund investing across European software and developer tools.',
    tags: ['Software (AI-tagged)', 'Seed (AI-tagged)', 'UK'],
    score: 87,
    confidence: 0.85,
    why_match: ['Matches target Seed ticket range and European software thesis'],
    sources: [{ name: 'Chalfen Ventures', url: 'https://chalfenventures.com' }],
  },
  {
    id: 'northzone',
    type: 'investor',
    name: 'Northzone',
    one_liner: 'Multi-stage venture firm founded in the Nordics investing from Seed to Growth.',
    tags: ['Fintech (AI-tagged)', 'Seed (AI-tagged)', 'Sweden'],
    score: 81,
    confidence: 0.82,
    why_match: ['2 hops from similar Nordic portfolio companies in the Cala graph'],
    sources: [{ name: 'Northzone', url: 'https://northzone.com' }],
  },
  {
    id: 'point-nine',
    type: 'investor',
    name: 'Point Nine',
    one_liner: 'Early-stage venture capital firm focused on B2B SaaS and marketplaces.',
    tags: ['B2B SaaS (AI-tagged)', 'Pre-seed (AI-tagged)', 'Germany'],
    score: 76,
    confidence: 0.78,
    why_match: ['Active lead investor in European B2B SaaS seed rounds'],
    sources: [{ name: 'Point Nine', url: 'https://pointnine.com' }],
  },
  {
    id: 'lifeline-ventures',
    type: 'investor',
    name: 'Lifeline Ventures',
    one_liner: 'Helsinki-based early-stage fund backing technical founders from day zero.',
    tags: ['ClimateTech (AI-tagged)', 'Pre-seed (AI-tagged)', 'Finland'],
    score: 64,
    confidence: 0.42,
    why_match: ['Active in Helsinki pre-seed ecosystem; limited ticket metadata'],
    sources: [{ name: 'Lifeline Ventures', url: 'https://lifelineventures.com' }],
  },
];

const MOCK_INVESTING: FeedCard[] = [
  {
    id: 'amenitiz',
    type: 'startup',
    name: 'Amenitiz',
    one_liner: 'All-in-one operating system for independent hotels and hospitality operators.',
    tags: ['B2B SaaS (AI-tagged)', 'Series B (AI-tagged)', 'Spain'],
    score: 91,
    confidence: 0.92,
    why_match: ['Matches European B2B software thesis with verified institutional backing'],
    sources: [{ name: 'Amenitiz', url: 'https://amenitiz.com' }],
  },
  {
    id: 'nordleaf',
    type: 'startup',
    name: 'Nordleaf',
    one_liner: 'Building energy optimization and telemetry software for commercial real estate.',
    tags: ['ClimateTech (AI-tagged)', 'Pre-seed (AI-tagged)', 'Finland'],
    score: 85,
    confidence: 0.8,
    why_match: ['Aligned with Nordic pre-seed climate and infrastructure focus'],
    sources: [{ name: 'Cala Knowledge Graph', url: 'https://cala.ai' }],
  },
  {
    id: 'solita-grid',
    type: 'startup',
    name: 'Vektor Grid',
    one_liner: 'Automated grid balancing software for distributed commercial battery assets.',
    tags: ['Energy (AI-tagged)', 'Seed (AI-tagged)', 'Sweden'],
    score: 78,
    confidence: 0.74,
    why_match: ['Raising within target Seed check size in Northern Europe'],
    sources: [{ name: 'Cala Knowledge Graph', url: 'https://cala.ai' }],
  },
  {
    id: 'krono-pay',
    type: 'startup',
    name: 'Krono Treasury',
    one_liner: 'Multi-currency cash management and automated FX hedging for SMEs.',
    tags: ['Fintech (AI-tagged)', 'Seed (AI-tagged)', 'Finland'],
    score: 63,
    confidence: 0.44,
    why_match: ['Operating in target Nordic fintech market; partial round history'],
    sources: [{ name: 'Cala Knowledge Graph', url: 'https://cala.ai' }],
  },
];

export function getMockFeed(
  mode: MatchMode,
  note = 'Showing sample matches while the backend is offline.',
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
    const response = await fetch(`${baseUrl}/api/feed?${query.toString()}`);
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      throw new ApiError(
        payload?.error?.code ?? 'http_error',
        payload?.error?.message ?? payload?.detail ?? `Request failed with status ${response.status}.`,
        response.status,
      );
    }
    return body as FeedResponse;
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
