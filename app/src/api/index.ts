export type Source = { name: string; url: string };

export type Card = {
  type: 'investor' | 'company' | 'competitor' | 'prospect' | 'claim';
  title: string;
  subtitle?: string;
  reason: string;
  sources: Source[];
};

export type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  transcript?: string;
  created_at: string;
  sources?: Source[];
  cards?: Card[];
};

export type Claim = {
  id: string;
  page: number;
  quote: string;
  category: string;
  publicly_verifiable: boolean;
  cala_question: string;
  verdict: 'confirmed' | 'partially_confirmed' | 'contradicted' | 'no_data' | 'not_checked' | 'error';
  explanation: string;
  evidence: unknown;
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
  status: 'queued' | 'extracting' | 'checking' | 'judging' | 'done' | 'error';
  progress: { done: number; total: number };
  report?: {
    startup_name: string;
    provider: string;
    model: string;
    claims: Claim[];
    summary: { confirmed: number; partially_confirmed: number; contradicted: number; no_data: number; not_checked: number };
    trust_score: number;
    timings: Record<string, unknown>;
    dropped_urls: string[];
  };
  error?: string;
};

export type HealthStatus = { provider: string; model: string; cala: boolean; transcription: string };
export type SendTextResponse = {
  message: Message;
  reply: Message;
  profile_updated: boolean;
  recommendations_status: Recommendations['status'];
};

export class ApiError extends Error {
  constructor(public readonly code: string, message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, init);
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = (body as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(error?.code ?? 'http_error', error?.message ?? `Error HTTP ${response.status}`, response.status);
  }
  return body as T;
}

export const health = () => request<HealthStatus>('/api/health');

export async function createSession(): Promise<string> {
  const result = await request<{ session_id: string }>('/api/sessions', { method: 'POST' });
  return result.session_id;
}

export function sendText(sessionId: string, text: string): Promise<SendTextResponse> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text })
  });
}

export async function listMessages(sessionId: string): Promise<Message[]> {
  const result = await request<{ messages: Message[] }>(`/api/sessions/${encodeURIComponent(sessionId)}/messages`);
  return result.messages;
}

export function getProfile(sessionId: string): Promise<Profile> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/profile`);
}

export function getRecommendations(sessionId: string): Promise<Recommendations> {
  return request(`/api/sessions/${encodeURIComponent(sessionId)}/recommendations`);
}

export async function verifyDeck(file: File, sessionId?: string): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append('file', file);
  const path = sessionId ? `/api/sessions/${encodeURIComponent(sessionId)}/deck` : '/api/verify';
  return request(path, { method: 'POST', body: form });
}

export function getJob(jobId: string): Promise<JobStatus> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`);
}
