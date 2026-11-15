import AsyncStorage from '@react-native-async-storage/async-storage';
import { createSession } from './api';
import { clearAuthToken, getAuthToken, getMe } from './api/auth';
const SESSION_KEY = 'junction_session_id';
export function getSessionId() { return AsyncStorage.getItem(SESSION_KEY); }
export async function setSessionId(id:string) { await AsyncStorage.setItem(SESSION_KEY,id); }
export async function clearSessionId() { await AsyncStorage.removeItem(SESSION_KEY); }
export async function getOrCreateSessionId():Promise<string> {
 const existing=await getSessionId(); if(existing) return existing;
 if(await getAuthToken()) { try { const me=await getMe(); await setSessionId(me.session_id); return me.session_id; } catch(e) { if((e as any)?.status===401) await clearAuthToken(); } }
 const id=await createSession(); await setSessionId(id); return id;
}
export async function resetSessionId():Promise<string> {
 if(await getAuthToken()) { try { const me=await getMe(); await setSessionId(me.session_id); return me.session_id; } catch(e) { if((e as any)?.status!==401) { const old=await getSessionId(); if(old) return old; throw e; } await clearAuthToken(); } }
 await clearSessionId(); return getOrCreateSessionId();
}
