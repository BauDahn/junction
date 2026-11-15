import { ApiError, type Source } from './index';

export type EntityMode = 'raising' | 'investing';

export type EntityMatchSignal = {
  signal: string;
  text: string;
  sources: Source[];
};

export type EntityFact = {
  label: string;
  value: string | number;
  sources: Source[];
};

export type EntityRound = {
  round_type?: string;
  amount?: string;
  date?: string;
  leads: string[];
  investors: string[];
  sources: Source[];
};

export type EntityPortfolioItem = {
  id: string;
  name: string;
};

export type EntityPerson = {
  id: string;
  name: string;
  role: string;
  since?: string;
};

export type EntityDetail = {
  id: string;
  type: 'investor' | 'startup';
  name: string;
  description?: string;
  score?: number;
  confidence?: number;
  why_match: EntityMatchSignal[];
  facts: EntityFact[];
  rounds: EntityRound[];
  portfolio: EntityPortfolioItem[];
  people: EntityPerson[];
  loaded_at: string;
};

export type EntityDetailResult = {
  detail: EntityDetail | null;
  isSample: boolean;
};

const REQUEST_TIMEOUT_MS = 30000;
const CALA_TIMEOUT = () => new ApiError('cala_timeout', 'Cala did not answer in time.', 504);

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

function findMockEntity(id: string, _mode: EntityMode): EntityDetail | null {
  if (!id.trim().toLowerCase().startsWith('sample-')) return null;
  return {
    id, type: 'investor', name: 'Sample Fund One',
    description: 'Placeholder entry shown only while the backend is offline.',
    why_match: [{ signal: 'sample', text: 'Placeholder sample, not Cala data', sources: [] }],
    facts: [], rounds: [], portfolio: [], people: [], loaded_at: '',
  };
}

function sanitizeSources(raw: unknown): Source[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is Source =>
      Boolean(s && typeof s === 'object' && typeof (s as Source).name === 'string' && typeof (s as Source).url === 'string'),
  );
}

function sanitizeStrings(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter((v): v is string => typeof v === 'string' && v.trim().length > 0);
}

function normalizeEntityDetail(raw: unknown): EntityDetail {
  const obj = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;

  const why_match: EntityMatchSignal[] = Array.isArray(obj.why_match)
    ? obj.why_match
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          signal: typeof item.signal === 'string' ? item.signal : 'signal',
          text: typeof item.text === 'string' ? item.text : '',
          sources: sanitizeSources(item.sources),
        }))
        .filter((item) => item.text.length > 0)
    : [];

  const facts: EntityFact[] = Array.isArray(obj.facts)
    ? obj.facts
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          label: typeof item.label === 'string' ? item.label : '',
          value:
            typeof item.value === 'string' || typeof item.value === 'number' ? item.value : '',
          sources: sanitizeSources(item.sources),
        }))
        .filter((item) => item.label.length > 0 && item.value !== '')
    : [];

  const rounds: EntityRound[] = Array.isArray(obj.rounds)
    ? obj.rounds
        .filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
        .map((item) => ({
          ...(typeof item.round_type === 'string' && item.round_type
            ? { round_type: item.round_type }
            : {}),
          ...(typeof item.amount === 'string' && item.amount ? { amount: item.amount } : {}),
          ...(typeof item.date === 'string' && item.date ? { date: item.date } : {}),
          leads: sanitizeStrings(item.leads),
          investors: sanitizeStrings(item.investors),
          sources: sanitizeSources(item.sources),
        }))
    : [];

  const portfolio: EntityPortfolioItem[] = Array.isArray(obj.portfolio)
    ? obj.portfolio
        .filter(
          (item): item is Record<string, unknown> =>
            Boolean(item && typeof item === 'object' && item.id != null && typeof item.name === 'string' && item.name),
        )
        .map((item) => ({ id: String(item.id), name: String(item.name) }))
    : [];

  const people: EntityPerson[] = Array.isArray(obj.people)
    ? obj.people
        .filter(
          (item): item is Record<string, unknown> =>
            Boolean(item && typeof item === 'object' && item.id != null && typeof item.name === 'string' && item.name),
        )
        .map((item) => ({
          id: String(item.id),
          name: String(item.name),
          role: typeof item.role === 'string' && item.role ? item.role : 'Member',
          ...(typeof item.since === 'string' && item.since ? { since: item.since } : {}),
        }))
    : [];

  return {
    id: String(obj.id ?? ''),
    type: obj.type === 'investor' ? 'investor' : 'startup',
    name: String(obj.name ?? ''),
    ...(typeof obj.description === 'string' && obj.description ? { description: obj.description } : {}),
    ...(typeof obj.score === 'number' ? { score: obj.score } : {}),
    ...(typeof obj.confidence === 'number' ? { confidence: obj.confidence } : {}),
    why_match,
    facts,
    rounds,
    portfolio,
    people,
    loaded_at: typeof obj.loaded_at === 'string' ? obj.loaded_at : '',
  };
}

export async function fetchEntityDetail(
  id: string,
  mode: EntityMode = 'raising',
  sessionId?: string | null,
): Promise<EntityDetailResult> {
  const cleanId = id.trim();
  if (!cleanId) return { detail: null, isSample: false };

  if (mockEnabled) {
    if (cleanId.toLowerCase() === 'error') {
      throw new ApiError('mock_error', 'Could not reach the backend. Check your connection and try again.', 503);
    }
    return { detail: findMockEntity(cleanId, mode), isSample: cleanId.toLowerCase().startsWith('sample-') };
  }

  const params = new URLSearchParams();
  params.set('mode', mode);
  if (sessionId) params.set('session_id', sessionId);
  const url = `${baseUrl}/api/entities/${encodeURIComponent(cleanId)}?${params.toString()}`;

  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS) : null;

  try {
    const response = await fetch(url, controller ? { signal: controller.signal } : undefined);
    if (response.status === 504) throw CALA_TIMEOUT();
    const body: unknown = await response.json().catch(() => null);

    if (response.status === 404) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      const msg = payload?.error?.message ?? payload?.detail ?? 'Entity not found.';
      if (/session/i.test(msg)) {
        throw new ApiError('session_not_found', msg, 404);
      }
      return { detail: null, isSample: false };
    }

    if (!response.ok) {
      const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
      throw new ApiError(
        payload?.error?.code ?? 'http_error',
        payload?.error?.message ?? payload?.detail ?? `Request failed with status ${response.status}.`,
        response.status,
      );
    }

    if (!body || typeof body !== 'object' || !('name' in body)) {
      throw new ApiError('invalid_response', 'Received an unexpected response from the server.', response.status);
    }

    return { detail: normalizeEntityDetail(body), isSample: false };
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof Error && err.name === 'AbortError') throw CALA_TIMEOUT();

    const fallback = findMockEntity(cleanId, mode);
    if (fallback) {
      return { detail: fallback, isSample: true };
    }

    throw new ApiError(
      'network_error',
      'Could not reach the backend. Check your connection and try again.',
      0,
    );
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export async function getEntityDetail(
  id: string,
  mode: EntityMode = 'raising',
  sessionId?: string | null,
): Promise<EntityDetail | null> {
  const { detail } = await fetchEntityDetail(id, mode, sessionId);
  return detail;
}
