import AsyncStorage from '@react-native-async-storage/async-storage';
import { createSession } from './api';

const SESSION_KEY = 'junction_session_id';

export function getSessionId(): Promise<string | null> {
  return AsyncStorage.getItem(SESSION_KEY);
}

export async function getOrCreateSessionId(): Promise<string> {
  const existing = await getSessionId();
  if (existing) return existing;
  const sessionId = await createSession();
  await AsyncStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}

export async function resetSessionId(): Promise<string> {
  await AsyncStorage.removeItem(SESSION_KEY);
  return getOrCreateSessionId();
}
