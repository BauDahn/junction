import AsyncStorage from '@react-native-async-storage/async-storage';
import { ApiError, type MobileFile } from './index';
import { emitContextChanged } from '../contextEvents';
export type AccountRole = 'raiser' | 'investor';
export type AuthUser = { id: string; email: string; name: string; company: string; role: AccountRole; session_id: string; created_at: string };
export type AuthResponse = { token: string; user: AuthUser };
export type RawContextResponse = { text: string; updated_at: string | null; profile_updated?: boolean };
export type TranscribePreviewResponse = { transcript: string; text: string };
const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const KEY = 'cala_auth_token';
export const getAuthToken = () => AsyncStorage.getItem(KEY);
export async function setAuthToken(token: string) { await AsyncStorage.setItem(KEY, token); }
export async function clearAuthToken() { await AsyncStorage.removeItem(KEY); }
type AuthExpiredListener = () => void;
const authExpiredListeners = new Set<AuthExpiredListener>();
export function onAuthExpired(listener: AuthExpiredListener) {
 authExpiredListeners.add(listener);
 return () => { authExpiredListeners.delete(listener); };
}
/** Adds the stored bearer token to API requests and clears an expired session on 401. */
export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
 const token = await getAuthToken();
 const headers = new Headers(init.headers);
 if (token) headers.set('Authorization', `Bearer ${token}`);
 const response = await fetch(input, { ...init, headers });
 if (response.status === 401 && token) {
  await clearAuthToken();
  authExpiredListeners.forEach((listener) => listener());
 }
 return response;
}
async function request<T>(path: string, init: RequestInit = {}, kind = ''): Promise<T> {
 let res: Response;
 try { res = await authFetch(baseUrl + path, init); } catch { throw new ApiError('network_error', 'Could not connect. Check your internet connection and try again.', 0); }
 if (res.status === 204) return undefined as T;
 const body: any = await res.json().catch(() => null);
 if (!res.ok) {
  const code = body?.error?.code ?? 'http_error'; const detail = body?.error?.message ?? body?.detail;
  let message = detail || `Request failed (${res.status}).`;
  if (res.status === 401) message = kind === 'login' || code === 'invalid_credentials' ? 'Invalid email or password.' : kind === 'me' ? 'Your session has expired. Please sign in again.' : message;
  if (res.status === 409 && code === 'email_taken') message = 'An account with this email already exists. Try signing in.';
  if (res.status === 413) message = detail || 'Audio exceeds the 10 MB or 2-minute limit.';
  if (res.status === 415) message = 'Unsupported audio format. Please record again.';
  if (res.status === 422 && kind === 'transcribe') message = 'Could not understand the audio. Try speaking clearly and try again.';
  if (res.status === 422 && kind === 'raw') message = 'Context must be 8,000 characters or fewer.';
  if (res.status === 502) message = kind === 'transcribe' ? 'Audio transcription failed. Please try again.' : 'Could not update matching profile right now. Try again.';
  if (res.status === 503) message = 'Voice transcription is not configured right now.';
  throw new ApiError(code, message, res.status);
 }
 return body as T;
}
const auth = async () => { const t = await getAuthToken(); if (!t) throw new ApiError('unauthorized','Not signed in.',401); return { Authorization: `Bearer ${t}` }; };
export async function registerAccount(input: {email:string;password:string;name:string;company:string;role:AccountRole}) { const r=await request<AuthResponse>('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)}); await setAuthToken(r.token); return r; }
export async function loginAccount(input:{email:string;password:string}) { const r=await request<AuthResponse>('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)},'login'); await setAuthToken(r.token); return r; }
export async function logoutAccount() { try { const h=await auth(); await request('/api/auth/logout',{method:'POST',headers:h}); } catch {} finally { await clearAuthToken(); } }
export async function getMe() { return request<AuthUser>('/api/me',{headers:await auth()},'me'); }
export async function getRawContext() { return request<RawContextResponse>('/api/me/context/raw',{headers:await auth()},'me'); }
export async function putRawContext(text:string) { const result = await request<RawContextResponse>('/api/me/context/raw',{method:'PUT',headers:{...(await auth()),'Content-Type':'application/json'},body:JSON.stringify({text})},'raw'); emitContextChanged(); return result; }
export async function appendRawContext(text:string) { const result = await request<RawContextResponse>('/api/me/context/raw/append',{method:'POST',headers:{...(await auth()),'Content-Type':'application/json'},body:JSON.stringify({text})},'raw'); emitContextChanged(); return result; }
export async function transcribePreview(audio:Blob|MobileFile,durationSeconds?:number) {
 if(durationSeconds && durationSeconds>120) throw new ApiError('payload_too_large','Audio must be 2 minutes or shorter.',413);
 const form=new FormData();
 if(typeof Blob!=='undefined' && audio instanceof Blob) { const type=audio.type.toLowerCase(); const ext=type.includes('m4a')||type.includes('mp4')?'m4a':type.includes('ogg')?'ogg':type.includes('wav')?'wav':type.includes('mpeg')||type.includes('mp3')?'mp3':'webm'; form.append('audio',audio,`voice-note.${ext}`); }
 else { const f=audio as MobileFile; form.append('audio',{uri:f.uri,name:f.name,type:f.mimeType} as any); }
 return request<TranscribePreviewResponse>('/api/transcribe',{method:'POST',body:form},'transcribe');
}
