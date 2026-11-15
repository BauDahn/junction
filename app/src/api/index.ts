export type Source = {
  name: string;
  url: string;
  date?: string;
  source_rank?: 'FILING' | 'PRIMARY' | 'PRESS' | 'AGGREGATOR';
};
/** Normalizes one Cala source: backend may send the URL as `document`. Keeps only http/https URLs. */
export function normalizeSource(raw: unknown): Source | null {
  if (!raw || typeof raw !== 'object') return null;
  const s = raw as Record<string, unknown>;
  const candidate = typeof s.url === 'string' && s.url ? s.url : typeof s.document === 'string' ? s.document : '';
  if (!/^https?:\/\//i.test(candidate) || typeof s.name !== 'string') return null;
  const rank = s.source_rank;
  return {
    name: s.name,
    url: candidate,
    ...(typeof s.date === 'string' && s.date ? { date: s.date } : {}),
    ...(rank === 'FILING' || rank === 'PRIMARY' || rank === 'PRESS' || rank === 'AGGREGATOR' ? { source_rank: rank } : {}),
  };
}
export function normalizeSources(raw: unknown): Source[] {
  return Array.isArray(raw) ? raw.map(normalizeSource).filter((s): s is Source => s !== null) : [];
}
/** Walks a parsed payload and normalizes every `sources` array in place. */
export function normalizeSourcesDeep<T>(body: T): T {
  if (Array.isArray(body)) body.forEach(normalizeSourcesDeep);
  else if (body && typeof body === 'object') {
    const obj = body as Record<string, unknown>;
    for (const key of Object.keys(obj)) {
      if (key === 'sources' && Array.isArray(obj[key])) obj[key] = normalizeSources(obj[key]);
      else normalizeSourcesDeep(obj[key]);
    }
  }
  return body;
}
export type CalaCall = { tool: 'knowledge_query' | 'entity' | 'knowledge_search'; query: string };
export type CalaTableBlock = {
  type: 'cala_table';
  title: string;
  summary?: string;
  call: CalaCall;
  columns: string[];
  rows: (string | number | null)[][];
  sources: Source[];
  row_sources?: number[][];
  /** Índices de las filas que responden la pregunta; el resto se muestra con "Ver todas". */
  focus_rows?: number[];
  /** Si la respuesta es una fila: sus celdas de Cala unidas. */
  answer?: string;
};
export type CalaAnswerBlock = {
  type: 'cala_answer';
  title: string;
  call: CalaCall;
  markdown: string;
  sources: Source[];
};
export type ClaimVerdict = 'confirmed' | 'partially_confirmed' | 'contradicted' | 'no_data';
export type ClaimCheckBlock = {
  type: 'claim_check';
  claim: string;
  verdict: ClaimVerdict;
  explanation: string;
  evidence: CalaTableBlock | CalaAnswerBlock;
  sources: Source[];
};
export type ProfileUpdateBlock = { type: 'profile_update'; changes: Record<string, unknown> };
export type NotFoundBlock = {
  type: 'not_found';
  title: string;
  tried: CalaCall[];
  closest?: CalaTableBlock | CalaAnswerBlock;
};
export type TextBlock = { type: 'text'; text: string };
export type Block =
  | CalaTableBlock
  | CalaAnswerBlock
  | ClaimCheckBlock
  | ProfileUpdateBlock
  | NotFoundBlock
  | TextBlock;
export type JournalItem = { id: string; is_new: boolean; block: Block };
export type JournalSection = {
  id: string;
  title: string;
  description: string;
  items: JournalItem[];
};
export type Journal = {
  edition: 'ecosistema' | 'founders';
  date: string;
  status: 'generating' | 'ready' | 'error';
  generated_at?: string;
  progress?: { done: number; total: number };
  sections: JournalSection[];
  error?: string;
};
export type Card = {
  type: 'investor' | 'company' | 'competitor' | 'prospect' | 'claim';
  title: string;
  subtitle?: string;
  reason: string;
  sources: Source[];
};
export type Claim = {
  id: string;
  page: number;
  quote: string;
  category: string;
  publicly_verifiable: boolean;
  cala_question: string;
  verdict:
    'confirmed' | 'partially_confirmed' | 'contradicted' | 'no_data' | 'not_checked' | 'error';
  explanation: string;
  evidence?: string;
  sources: Source[];
};
export type Profile = {
  startup_name?: string;
  one_liner?: string;
  sector?: string;
  stage?: string;
  location?: string;
  raising?: { amount?: number | string; round?: string };
  competitors: string[];
  target_customers?: string;
  facts: { text: string; origin: 'user' | 'deck'; verified?: Claim }[];
  updated_at: string;
  role?: 'founder' | 'investor' | 'other';
  interests?: {
    sectors: string[];
    regions: string[];
    stages: string[];
    follows: { companies: string[]; investors: string[] };
  };
};
export type Recommendations = {
  status: 'idle' | 'running' | 'ready' | 'error';
  updated_at: string;
  investors: Card[];
  competitors: Card[];
  prospects: Card[];
};
export type JobStatus = {
  job_id?: string;
  elapsed_s?: number;
  status: 'queued' | 'extracting' | 'checking' | 'judging' | 'done' | 'error';
  progress: { done: number; total: number };
  report?: {
    startup_name: string;
    provider: string;
    model: string;
    claims: Claim[];
    summary: {
      confirmed: number;
      partially_confirmed: number;
      contradicted: number;
      no_data: number;
      not_checked: number;
    };
    trust_score: number;
    trust_score_formula?: string;
    timings: Record<string, number>;
    dropped_urls: number;
    scanned_pages_without_text?: number[];
  };
  error?: string;
};
export type HealthStatus = {
  provider: string;
  model: string;
  cala: boolean;
  transcription?: string;
};
export type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  transcript?: string;
  created_at: string;
  sources?: Source[];
  cards?: Card[];
  audio?: boolean;
  blocks?: Block[];
};
export type SendTextResponse = {
  message: Message;
  reply: Message;
  profile_updated: boolean;
  recommendations_status: Recommendations['status'];
};

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}
const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const payload = body as { error?: { code?: string; message?: string }; detail?: string } | null;
    throw new ApiError(
      payload?.error?.code ?? 'http_error',
      payload?.error?.message ?? payload?.detail ?? `HTTP error ${response.status}`,
      response.status,
    );
  }
  return normalizeSourcesDeep(body) as T;
}
export const health = () => request<HealthStatus>('/api/health');
export async function createSession(): Promise<string> {
  if (mockEnabled) {
    const mock = await import('./mock');
    return mock.createMockSession();
  }
  return (await request<{ session_id: string }>('/api/sessions', { method: 'POST' })).session_id;
}
export function getEcosystemJournal(date?: string): Promise<Journal> {
  if (mockEnabled) return import('./mock').then((mock) => mock.getMockJournal('ecosistema', date));
  return request(`/api/journal/ecosistema${date ? `?date=${encodeURIComponent(date)}` : ''}`);
}
export function getSessionJournal(sessionId: string, date?: string): Promise<Journal> {
  if (mockEnabled)
    return import('./mock').then((mock) => mock.getMockJournal('founders', date, sessionId));
  return request(
    `/api/sessions/${encodeURIComponent(sessionId)}/journal${date ? `?date=${encodeURIComponent(date)}` : ''}`,
  );
}
export function regenerateEcosystemJournal(): Promise<{ status: 'generating' }> {
  if (mockEnabled) return import('./mock').then((mock) => mock.regenerateMockJournal('ecosistema'));
  return request('/api/journal/ecosistema/regenerate', { method: 'POST' });
}
export function regenerateSessionJournal(sessionId: string): Promise<{ status: 'generating' }> {
  if (mockEnabled)
    return import('./mock').then((mock) => mock.regenerateMockJournal('founders', sessionId));
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/journal/regenerate`, {
    method: 'POST',
  });
}
export function sendText(
  sessionId: string,
  text: string,
  context?: { journal_item_id: string },
): Promise<SendTextResponse> {
  if (mockEnabled) return import('./mock').then((mock) => mock.sendMockText(sessionId, text));
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, ...(context ? { context } : {}) }),
  });
}
export function sendAudio(sessionId: string, audio: Blob | MobileFile): Promise<SendTextResponse> {
  if (mockEnabled) return import('./mock').then((mock) => mock.sendMockAudio(sessionId));
  const form = new FormData();
  if (typeof Blob !== 'undefined' && audio instanceof Blob) {
    form.append('audio', audio, 'audio.webm');
  } else {
    const mobile = audio as MobileFile;
    form.append('audio', { uri: mobile.uri, name: mobile.name, type: mobile.mimeType } as any);
  }
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    body: form,
  });
}
export async function listMessages(sessionId: string): Promise<Message[]> {
  if (mockEnabled) return (await import('./mock')).listMockMessages(sessionId);
  return (
    await request<{ messages: Message[] }>(
      `/api/sessions/${encodeURIComponent(sessionId)}/messages`,
    )
  ).messages;
}
export function getProfile(sessionId: string): Promise<Profile> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/profile`);
}
export function getRecommendations(sessionId: string): Promise<Recommendations> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/recommendations`);
}
export type MobileFile = { uri: string; name: string; mimeType: string };
export async function verifyDeck(
  file: File | MobileFile,
  sessionId?: string,
): Promise<{ job_id: string }> {
  const form = new FormData();
  if (typeof File !== 'undefined' && file instanceof File) form.append('file', file);
  else {
    const mobile = file as MobileFile;
    form.append('file', { uri: mobile.uri, name: mobile.name, type: mobile.mimeType } as any);
  }
  return request(
    sessionId ? `/api/sessions/${encodeURIComponent(sessionId)}/deck` : '/api/verify',
    { method: 'POST', body: form },
  );
}
export function verifySample(): Promise<{ job_id: string }> {
  return request('/api/verify-sample', { method: 'POST' });
}
export function getJob(jobId: string): Promise<JobStatus> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`);
}
