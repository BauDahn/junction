export type Source = { name: string; url: string };
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
      payload?.error?.message ?? payload?.detail ?? `Error HTTP ${response.status}`,
      response.status,
    );
  }
  return body as T;
}
export const health = () => request<HealthStatus>('/api/health');
export async function createSession(): Promise<string> {
  if (mockEnabled) {
    const mock = await import('./mock');
    return mock.createMockSession();
  }
  return (await request<{ session_id: string }>('/api/sessions', { method: 'POST' })).session_id;
}
export function sendText(sessionId: string, text: string): Promise<SendTextResponse> {
  if (mockEnabled) return import('./mock').then((mock) => mock.sendMockText(sessionId, text));
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
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
