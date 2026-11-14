import { ApiError, type MobileFile, type Profile } from './index';

export const UNDERSTOOD_KEYS = [
  'sector_focus',
  'target_stage',
  'target_round_size',
  'geography',
  'seeking',
] as const;

export type UnderstoodKey = (typeof UNDERSTOOD_KEYS)[number];
export type WhatWeUnderstood = Record<UnderstoodKey, string[]>;

export type ContextSourceKind = 'pdf' | 'voice' | 'note';

export type ContextSource = {
  id: string;
  kind: ContextSourceKind;
  title: string;
  subtitle: string;
  status?: string;
  created_at?: string;
  pages?: number;
  duration_s?: number;
  transcript?: string;
};

export type ContextStrength = {
  score: number;
  signals_added: number;
  signals_total: number;
  label: string;
};

export type TicketRange = {
  min: number;
  max: number;
  currency?: string | null;
};

export type ContextProfile = Profile & {
  ticket?: string;
  ticket_range?: TicketRange;
  seeking?: string[];
  what_we_understood?: WhatWeUnderstood;
  context_sources?: ContextSource[];
};

export type ContextPayload = {
  session_id: string;
  profile: ContextProfile;
  what_we_understood: WhatWeUnderstood;
  sources: ContextSource[];
  context_strength: ContextStrength;
  source?: ContextSource;
  is_demo?: boolean;
};

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

function emptyUnderstood(): WhatWeUnderstood {
  return {
    sector_focus: [],
    target_stage: [],
    target_round_size: [],
    geography: [],
    seeking: [],
  };
}

function dedupeItems(values: readonly string[]): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const trimmed = raw.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(trimmed);
  }
  return result;
}

function normalizeUnderstood(raw?: Partial<Record<UnderstoodKey, unknown>> | null): WhatWeUnderstood {
  const out = emptyUnderstood();
  if (!raw) return out;
  for (const key of UNDERSTOOD_KEYS) {
    const val = raw[key];
    if (Array.isArray(val)) {
      out[key] = dedupeItems(val.filter((item): item is string => typeof item === 'string'));
    }
  }
  return out;
}

function normalizePayload(raw: ContextPayload): ContextPayload {
  const understood = normalizeUnderstood(raw.what_we_understood);
  const signals =
    UNDERSTOOD_KEYS.filter((k) => understood[k].length > 0).length +
    (raw.profile?.one_liner ? 1 : 0);
  const fallbackStrength: ContextStrength = {
    score: Math.round((signals / 6) * 100),
    signals_added: signals,
    signals_total: 6,
    label:
      signals <= 2
        ? 'Needs Context'
        : signals <= 4
          ? 'Calibrating'
          : signals === 5
            ? 'Good Calibration'
            : 'High Signal',
  };
  return {
    session_id: raw.session_id,
    profile: raw.profile,
    what_we_understood: understood,
    sources: Array.isArray(raw.sources) ? raw.sources : [],
    context_strength: raw.context_strength ?? fallbackStrength,
    ...(raw.source ? { source: raw.source } : {}),
    ...(raw.is_demo ? { is_demo: true } : {}),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const payload = body as {
      error?: { code?: string; message?: string };
      detail?: string;
    } | null;
    const message =
      payload?.error?.message ?? payload?.detail ?? `Request failed (HTTP ${response.status}).`;
    throw new ApiError(payload?.error?.code ?? 'http_error', message, response.status);
  }
  return body as T;
}

async function withFallback<T>(remote: () => Promise<T>, fallback: () => Promise<T>): Promise<T> {
  if (mockEnabled) return fallback();
  try {
    return await remote();
  } catch (err) {
    // Only fall back to local demo state when the server is unreachable (network error).
    // Preserve real HTTP errors (4xx/5xx) so 404 session resets and validation errors work.
    if (err instanceof ApiError) throw err;
    return fallback();
  }
}

type MockSessionState = {
  profile: ContextProfile;
  understood: WhatWeUnderstood;
  sources: ContextSource[];
};

const demoSessions = new Map<string, MockSessionState>();
const demoWait = () => new Promise((resolve) => setTimeout(resolve, 220));

function getDemoState(sessionId: string): MockSessionState {
  const existing = demoSessions.get(sessionId);
  if (existing) return existing;

  const initial: MockSessionState = {
    profile: {
      startup_name: 'Nordleaf',
      one_liner:
        'Automated energy optimization and sub-metering software for commercial buildings in the Nordics.',
      sector: 'ClimateTech',
      stage: 'Seed',
      location: 'Helsinki',
      ticket: '€2.0M - €3.0M',
      ticket_range: { min: 2000000, max: 3000000, currency: 'EUR' },
      raising: { amount: '€2.0M - €3.0M', round: 'Seed' },
      competitors: ['GreenBuild', 'Wattwise'],
      target_customers: 'Commercial real estate operators',
      facts: [],
      updated_at: new Date().toISOString(),
    },
    understood: {
      sector_focus: ['ClimateTech', 'B2B SaaS'],
      target_stage: ['Seed'],
      target_round_size: ['€2.0M - €3.0M'],
      geography: ['Nordics'],
      seeking: [],
    },
    sources: [
      {
        id: 'demo-pdf-1',
        kind: 'pdf',
        title: 'Nordleaf_Seed_Deck_2026.pdf',
        subtitle: 'Pitch deck analyzed',
        status: 'ready',
        created_at: new Date(Date.now() - 3600 * 1000 * 5).toISOString(),
        pages: 14,
      },
      {
        id: 'demo-voice-1',
        kind: 'voice',
        title: 'Voice note',
        subtitle: 'Voice note analyzed',
        status: 'ready',
        created_at: new Date(Date.now() - 3600 * 1000 * 2).toISOString(),
        duration_s: 48,
        transcript:
          'We are raising a €2M to €3M seed round in Helsinki and looking for European climate or B2B software investors.',
      },
    ],
  };
  demoSessions.set(sessionId, initial);
  return initial;
}

function buildDemoPayload(sessionId: string, state: MockSessionState, source?: ContextSource): ContextPayload {
  const signals =
    UNDERSTOOD_KEYS.filter((key) => state.understood[key].length > 0).length +
    (state.profile.one_liner ? 1 : 0);
  const label =
    signals <= 2
      ? 'Needs Context'
      : signals <= 4
        ? 'Calibrating'
        : signals === 5
          ? 'Good Calibration'
          : 'High Signal';

  const profile: ContextProfile = {
    ...state.profile,
    what_we_understood: { ...state.understood },
    seeking: [...state.understood.seeking],
    context_sources: [...state.sources],
  };

  return {
    session_id: sessionId,
    profile,
    what_we_understood: {
      sector_focus: [...state.understood.sector_focus],
      target_stage: [...state.understood.target_stage],
      target_round_size: [...state.understood.target_round_size],
      geography: [...state.understood.geography],
      seeking: [...state.understood.seeking],
    },
    sources: [...state.sources],
    context_strength: {
      score: Math.round((signals / 6) * 100),
      signals_added: signals,
      signals_total: 6,
      label,
    },
    ...(source ? { source } : {}),
    is_demo: true,
  };
}

function applyTextSignals(state: MockSessionState, text: string) {
  const lower = text.toLowerCase();
  const add = (key: UnderstoodKey, value: string) => {
    state.understood[key] = dedupeItems([...state.understood[key], value]);
  };

  if (lower.includes('fintech')) add('sector_focus', 'Fintech');
  if (lower.includes('ai') || lower.includes('ml')) add('sector_focus', 'Applied AI');
  if (lower.includes('saas') || lower.includes('b2b')) add('sector_focus', 'B2B SaaS');
  if (lower.includes('climate') || lower.includes('energy')) add('sector_focus', 'ClimateTech');
  if (lower.includes('health') || lower.includes('bio')) add('sector_focus', 'Healthtech');

  if (lower.includes('pre-seed') || lower.includes('preseed')) add('target_stage', 'Pre-seed');
  if (lower.includes('seed')) add('target_stage', 'Seed');
  if (lower.includes('series a')) add('target_stage', 'Series A');
  if (lower.includes('series b')) add('target_stage', 'Series B');

  if (lower.includes('nordic') || lower.includes('finland') || lower.includes('helsinki')) {
    add('geography', 'Nordics');
  }
  if (lower.includes('europe') || lower.includes('eu')) add('geography', 'Europe');
  if (lower.includes('uk') || lower.includes('london')) add('geography', 'UK');
  if (lower.includes('us') || lower.includes('usa')) add('geography', 'US');

  if (lower.includes('lead')) add('seeking', 'Lead investor');
  if (lower.includes('operator')) add('seeking', 'Operator background');
  if (lower.includes('board')) add('seeking', 'Board seat');
  if (lower.includes('co-invest')) add('seeking', 'Co-investor');

  const amountMatch = text.match(/([€$£]\s?\d+(?:\.\d+)?(?:\s?-\s?[€$£]?\d+(?:\.\d+)?)?\s?[mkbMK]?\b)/);
  if (amountMatch?.[1]) {
    add('target_round_size', amountMatch[1].trim());
  }

  // Ensure demo note/voice adds at least one visible signal if user wrote freeform preferences
  if (
    !amountMatch &&
    !lower.includes('lead') &&
    !lower.includes('operator') &&
    state.understood.seeking.length === 0
  ) {
    const snippet = text.trim().split(/[.!?\n]/)[0]?.slice(0, 42).trim();
    if (snippet) add('seeking', snippet);
  }
}

export async function getContext(sessionId: string): Promise<ContextPayload> {
  return withFallback(
    async () => {
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context`,
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      return buildDemoPayload(sessionId, getDemoState(sessionId));
    },
  );
}

export async function uploadContextPdf(
  sessionId: string,
  file: File | MobileFile,
): Promise<ContextPayload> {
  const fileName =
    typeof File !== 'undefined' && file instanceof File
      ? file.name || 'Pitch_Deck.pdf'
      : file.name || 'Pitch_Deck.pdf';

  return withFallback(
    async () => {
      const form = new FormData();
      if (typeof File !== 'undefined' && file instanceof File) {
        form.append('file', file, fileName);
      } else {
        const mobile = file as MobileFile;
        form.append(
          'file',
          { uri: mobile.uri, name: mobile.name, type: mobile.mimeType } as unknown as Blob,
        );
      }
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context/pdf`,
        { method: 'POST', body: form },
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      const state = getDemoState(sessionId);
      applyTextSignals(state, fileName.replace(/[_-]+/g, ' '));
      const source: ContextSource = {
        id: `demo-pdf-${Date.now()}`,
        kind: 'pdf',
        title: fileName,
        subtitle: 'Pitch deck analyzed',
        status: 'ready',
        created_at: new Date().toISOString(),
        pages: 12,
      };
      state.sources = [...state.sources, source];
      state.profile.updated_at = new Date().toISOString();
      return buildDemoPayload(sessionId, state, source);
    },
  );
}

export async function uploadContextVoice(
  sessionId: string,
  audio: Blob | MobileFile,
  durationSeconds?: number,
): Promise<ContextPayload> {
  return withFallback(
    async () => {
      const form = new FormData();
      if (typeof Blob !== 'undefined' && audio instanceof Blob) {
        const type = audio.type.toLowerCase();
        const ext = type.includes('mp4')
          ? 'm4a'
          : type.includes('ogg')
            ? 'ogg'
            : type.includes('wav')
              ? 'wav'
              : type.includes('mpeg')
                ? 'mp3'
                : 'webm';
        form.append('audio', audio, `voice-note.${ext}`);
      } else {
        const mobile = audio as MobileFile;
        form.append(
          'audio',
          { uri: mobile.uri, name: mobile.name, type: mobile.mimeType } as unknown as Blob,
        );
      }
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context/voice`,
        { method: 'POST', body: form },
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      const state = getDemoState(sessionId);
      const transcript =
        'Looking for a lead investor with European B2B SaaS experience for our upcoming €2.5M seed round.';
      applyTextSignals(state, transcript);
      const source: ContextSource = {
        id: `demo-voice-${Date.now()}`,
        kind: 'voice',
        title: 'Voice note',
        subtitle: 'Voice note analyzed',
        status: 'ready',
        created_at: new Date().toISOString(),
        duration_s: durationSeconds && durationSeconds > 0 ? durationSeconds : 18,
        transcript,
      };
      state.sources = [...state.sources, source];
      state.profile.updated_at = new Date().toISOString();
      return buildDemoPayload(sessionId, state, source);
    },
  );
}

export async function addContextNote(
  sessionId: string,
  text: string,
  title?: string,
): Promise<ContextPayload> {
  const cleanText = text.trim();
  const cleanTitle = title?.trim();

  return withFallback(
    async () => {
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context/note`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: cleanText,
            ...(cleanTitle ? { title: cleanTitle } : {}),
          }),
        },
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      const state = getDemoState(sessionId);
      applyTextSignals(state, cleanText);
      const source: ContextSource = {
        id: `demo-note-${Date.now()}`,
        kind: 'note',
        title: cleanTitle || 'Quick note',
        subtitle: cleanText.slice(0, 80) + (cleanText.length > 80 ? '...' : ''),
        status: 'ready',
        created_at: new Date().toISOString(),
      };
      state.sources = [...state.sources, source];
      state.profile.updated_at = new Date().toISOString();
      return buildDemoPayload(sessionId, state, source);
    },
  );
}

export async function updateUnderstood(
  sessionId: string,
  patch: Partial<WhatWeUnderstood>,
): Promise<ContextPayload> {
  const cleanPatch: Partial<WhatWeUnderstood> = {};
  for (const key of UNDERSTOOD_KEYS) {
    if (patch[key] !== undefined) {
      cleanPatch[key] = dedupeItems(patch[key] ?? []);
    }
  }

  return withFallback(
    async () => {
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context/understood`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cleanPatch),
        },
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      const state = getDemoState(sessionId);
      for (const key of UNDERSTOOD_KEYS) {
        if (cleanPatch[key] !== undefined) {
          state.understood[key] = [...(cleanPatch[key] ?? [])];
        }
      }
      state.profile.sector = state.understood.sector_focus[0];
      state.profile.stage = state.understood.target_stage[0];
      state.profile.location = state.understood.geography[0];
      state.profile.ticket = state.understood.target_round_size[0];
      state.profile.updated_at = new Date().toISOString();
      return buildDemoPayload(sessionId, state);
    },
  );
}

export async function deleteContextSource(
  sessionId: string,
  sourceId: string,
): Promise<ContextPayload> {
  return withFallback(
    async () => {
      const payload = await request<ContextPayload>(
        `/api/sessions/${encodeURIComponent(sessionId)}/context/sources/${encodeURIComponent(sourceId)}`,
        { method: 'DELETE' },
      );
      return normalizePayload(payload);
    },
    async () => {
      await demoWait();
      const state = getDemoState(sessionId);
      state.sources = state.sources.filter((item) => item.id !== sourceId);
      state.profile.updated_at = new Date().toISOString();
      return buildDemoPayload(sessionId, state);
    },
  );
}
