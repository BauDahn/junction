import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError } from './api';
import { getOrCreateSessionId, resetSessionId } from './session';

export type MatchMode = 'raising' | 'investing';
export type UserProfile = { name: string; organization: string; role: MatchMode };
export type ModeContextValue = {
  mode: MatchMode;
  setMode: (next: MatchMode) => void;
  hydrated: boolean;
  onboarded: boolean;
  userProfile: UserProfile;
  myEventIds: string[];
  favoriteInvestorIds: string[];
  completeOnboarding: (profile: UserProfile) => void;
  resetOnboarding: () => void;
  toggleMyEvent: (eventId: string) => void;
  addMyEvent: (eventId: string) => void;
  toggleFavoriteInvestor: (investorId: string) => void;
  addFavoriteInvestor: (investorId: string) => void;
};

type PersistedState = Pick<ModeContextValue, 'mode' | 'onboarded' | 'userProfile' | 'myEventIds' | 'favoriteInvestorIds'>;
const STORAGE_KEY = 'cala_v3_state';
const DEFAULT_PROFILE: UserProfile = { name: 'Alex Lindqvist', organization: 'Nordleaf', role: 'raising' };
const DEFAULT_STATE: PersistedState = {
  mode: 'raising', onboarded: false, userProfile: DEFAULT_PROFILE,
  myEventIds: ['slush-2026'], favoriteInvestorIds: ['eight-roads-ventures'],
};
const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';
const ModeContext = createContext<ModeContextValue>({
  ...DEFAULT_STATE, hydrated: false, setMode: () => {}, completeOnboarding: () => {}, resetOnboarding: () => {},
  toggleMyEvent: () => {}, addMyEvent: () => {}, toggleFavoriteInvestor: () => {}, addFavoriteInvestor: () => {},
});

async function syncSessionMode(mode: MatchMode) {
  if (mockEnabled) return;
  try {
    let id = await getOrCreateSessionId();
    let response = await fetch(`${baseUrl}/api/sessions/${encodeURIComponent(id)}/mode`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }),
    });
    if (response.status === 404) {
      id = await resetSessionId();
      response = await fetch(`${baseUrl}/api/sessions/${encodeURIComponent(id)}/mode`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }),
      });
    }
    if (!response.ok) return;
  } catch (error) { if (error instanceof ApiError) return; }
}

export function ModeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PersistedState>(DEFAULT_STATE);
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(STORAGE_KEY).then((raw) => {
      if (!active || !raw) return;
      try {
        const saved = JSON.parse(raw) as Partial<PersistedState>;
        const mode = saved.mode === 'investing' ? 'investing' : 'raising';
        setState({
          mode, onboarded: Boolean(saved.onboarded),
          userProfile: saved.userProfile && typeof saved.userProfile.name === 'string'
            ? { ...DEFAULT_PROFILE, ...saved.userProfile, role: saved.userProfile.role === 'investing' ? 'investing' : 'raising' }
            : DEFAULT_PROFILE,
          myEventIds: Array.isArray(saved.myEventIds) ? saved.myEventIds.filter((id): id is string => typeof id === 'string') : DEFAULT_STATE.myEventIds,
          favoriteInvestorIds: Array.isArray(saved.favoriteInvestorIds) ? saved.favoriteInvestorIds.filter((id): id is string => typeof id === 'string') : DEFAULT_STATE.favoriteInvestorIds,
        });
      } catch { /* Use the fresh-start state when storage is invalid. */ }
    }).catch(() => {}).finally(() => {
      if (active) setHydrated(true);
    });
    return () => { active = false; };
  }, []);
  const commit = useCallback((updater: (current: PersistedState) => PersistedState) => {
    setState((current) => {
      const next = updater(current);
      void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      if (next.mode !== current.mode) void syncSessionMode(next.mode);
      return next;
    });
  }, []);
  const setMode = useCallback((mode: MatchMode) => commit((current) => ({ ...current, mode })), [commit]);
  const completeOnboarding = useCallback((profile: UserProfile) => {
    commit((current) => ({ ...current, userProfile: profile, mode: profile.role, onboarded: true }));
    void syncSessionMode(profile.role);
  }, [commit]);
  const resetOnboarding = useCallback(() => commit((current) => ({ ...current, onboarded: false })), [commit]);
  const toggleMyEvent = useCallback((id: string) => commit((current) => ({
    ...current, myEventIds: current.myEventIds.includes(id) ? current.myEventIds.filter((item) => item !== id) : [...current.myEventIds, id],
  })), [commit]);
  const addMyEvent = useCallback((id: string) => commit((current) => current.myEventIds.includes(id) ? current : ({ ...current, myEventIds: [...current.myEventIds, id] })), [commit]);
  const toggleFavoriteInvestor = useCallback((id: string) => commit((current) => ({
    ...current, favoriteInvestorIds: current.favoriteInvestorIds.includes(id) ? current.favoriteInvestorIds.filter((item) => item !== id) : [...current.favoriteInvestorIds, id],
  })), [commit]);
  const addFavoriteInvestor = useCallback((id: string) => commit((current) => current.favoriteInvestorIds.includes(id) ? current : ({ ...current, favoriteInvestorIds: [...current.favoriteInvestorIds, id] })), [commit]);
  const value = useMemo(() => ({ ...state, hydrated, setMode, completeOnboarding, resetOnboarding, toggleMyEvent, addMyEvent, toggleFavoriteInvestor, addFavoriteInvestor }), [state, hydrated, setMode, completeOnboarding, resetOnboarding, toggleMyEvent, addMyEvent, toggleFavoriteInvestor, addFavoriteInvestor]);
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}
export const useMode = () => useContext(ModeContext);
