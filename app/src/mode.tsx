import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { ApiError } from './api';
import { getOrCreateSessionId, resetSessionId } from './session';

export type MatchMode = 'raising' | 'investing';

type ModeContextValue = {
  mode: MatchMode;
  setMode: (next: MatchMode) => void;
};

const MODE_KEY = 'cala_match_mode';
const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

const ModeContext = createContext<ModeContextValue>({
  mode: 'raising',
  setMode: () => {},
});

async function postMode(sessionId: string, mode: MatchMode): Promise<Response> {
  return fetch(`${baseUrl}/api/sessions/${encodeURIComponent(sessionId)}/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
}

async function syncSessionMode(mode: MatchMode): Promise<void> {
  if (mockEnabled) return;
  try {
    let sessionId = await getOrCreateSessionId();
    const res = await postMode(sessionId, mode);
    if (res.status === 404) {
      sessionId = await resetSessionId();
      await postMode(sessionId, mode);
    }
  } catch (err) {
    if (err instanceof ApiError) return;
    // Silent fallback when the backend is unavailable.
  }
}

/**
 * Shared Raising / Investing mode context synchronized with POST /api/sessions/{id}/mode.
 */
export function ModeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<MatchMode>('raising');

  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(MODE_KEY)
      .then((stored) => {
        if (!active) return;
        if (stored === 'raising' || stored === 'investing') {
          setModeState(stored);
        }
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  const setMode = useCallback((next: MatchMode) => {
    setModeState((prev) => {
      if (prev === next) return prev;
      void AsyncStorage.setItem(MODE_KEY, next).catch(() => {});
      void syncSessionMode(next);
      return next;
    });
  }, []);

  return <ModeContext.Provider value={{ mode, setMode }}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
