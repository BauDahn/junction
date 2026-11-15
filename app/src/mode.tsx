import AsyncStorage from '@react-native-async-storage/async-storage';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ApiError } from './api';
import { clearAuthToken, getAuthToken, getMe, loginAccount, logoutAccount, registerAccount, authFetch, onAuthExpired, type AccountRole, type AuthUser } from './api/auth';
import { clearSessionId, getOrCreateSessionId, setSessionId } from './session';

export type MatchMode = 'raising' | 'investing';
export type UserProfile = { name: string; organization: string; role: MatchMode };
type AccountLists = { myEventIds: string[]; favoriteInvestorIds: string[] };
type PersistedState = {
  mode: MatchMode;
  onboarded: boolean;
  userProfile: UserProfile;
  myEventIds: string[];
  favoriteInvestorIds: string[];
  /** Saved lists of the other accounts used on this device, keyed by account id ('guest' when signed out). */
  byAccount?: Record<string, AccountLists>;
  authUser?: AuthUser | null;
};
export type ModeContextValue = PersistedState & {
  hydrated: boolean;
  user: AuthUser | null;
  isAuthenticated: boolean;
  authLoading: boolean;
  sessionExpired: boolean;
  setMode: (mode: MatchMode) => void;
  completeOnboarding: (profile: UserProfile) => void;
  resetOnboarding: () => void;
  toggleMyEvent: (id: string) => void;
  addMyEvent: (id: string) => void;
  toggleFavoriteInvestor: (id: string) => void;
  addFavoriteInvestor: (id: string) => void;
  loginWithCredentials: (input: { email: string; password: string }) => Promise<AuthUser>;
  registerWithCredentials: (input: { email: string; password: string; name: string; company: string; role: AccountRole }) => Promise<AuthUser>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<AuthUser | null>;
};

const STORAGE_KEY = 'cala_v3_state';
const DEFAULT_PROFILE: UserProfile = { name: '', organization: '', role: 'raising' };
const DEFAULT_STATE: PersistedState = {
  mode: 'raising', onboarded: false, userProfile: DEFAULT_PROFILE,
  myEventIds: ['slush-2026'], favoriteInvestorIds: [], authUser: null,
};
const apiBase = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const modeFor = (user: AuthUser): MatchMode => user.role === 'investor' ? 'investing' : 'raising';
const accountKey = (user: AuthUser | null | undefined) => user?.id ?? 'guest';
/** Favorites and events belong to one account: stash the current account's lists and load the next one's. */
function withAccount(current: PersistedState, user: AuthUser | null): PersistedState {
  const from = accountKey(current.authUser), to = accountKey(user);
  if (from === to) return { ...current, authUser: user };
  const byAccount = { ...(current.byAccount ?? {}), [from]: { myEventIds: current.myEventIds, favoriteInvestorIds: current.favoriteInvestorIds } };
  const next = byAccount[to] ?? { myEventIds: DEFAULT_STATE.myEventIds, favoriteInvestorIds: DEFAULT_STATE.favoriteInvestorIds };
  return { ...current, authUser: user, byAccount, myEventIds: next.myEventIds, favoriteInvestorIds: next.favoriteInvestorIds };
}

const ModeContext = createContext<ModeContextValue>({
  ...DEFAULT_STATE, hydrated: false, user: null, isAuthenticated: false, authLoading: false, sessionExpired: false,
  setMode: () => {}, completeOnboarding: () => {}, resetOnboarding: () => {},
  toggleMyEvent: () => {}, addMyEvent: () => {}, toggleFavoriteInvestor: () => {}, addFavoriteInvestor: () => {},
  loginWithCredentials: async () => { throw new Error('ModeProvider is missing.'); },
  registerWithCredentials: async () => { throw new Error('ModeProvider is missing.'); },
  logout: async () => {}, refreshMe: async () => null,
});

export function ModeProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PersistedState>(DEFAULT_STATE);
  const [hydrated, setHydrated] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  const commit = useCallback((updater: (current: PersistedState) => PersistedState) => {
    setState((current) => {
      const next = updater(current);
      void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next)).catch(() => {});
      return next;
    });
  }, []);

  const syncAnonymousMode = useCallback(async (mode: MatchMode) => {
    try {
      const sessionId = await getOrCreateSessionId();
      await authFetch(`${apiBase}/api/sessions/${encodeURIComponent(sessionId)}/mode`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode }),
      });
    } catch { /* Keep local mode available while offline. */ }
  }, []);

  const applyUser = useCallback((user: AuthUser) => {
    setSessionExpired(false);
    const mode = modeFor(user);
    commit((current) => ({
      ...withAccount(current, user), mode, onboarded: true,
      userProfile: { name: user.name, organization: user.company, role: mode },
    }));
  }, [commit]);

  const refreshMe = useCallback(async () => {
    if (!(await getAuthToken())) return null;
    try {
      const user = await getMe();
      await setSessionId(user.session_id);
      applyUser(user);
      return user;
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) {
        await clearAuthToken();
        await clearSessionId();
        commit((current) => ({ ...withAccount(current, null), onboarded: false }));
      }
      return null;
    }
  }, [applyUser, commit]);

  useEffect(() => onAuthExpired(() => {
    void clearSessionId();
    setSessionExpired(true);
    commit((current) => ({ ...withAccount(current, null), onboarded: false, userProfile: DEFAULT_PROFILE, mode: 'raising' }));
  }), [commit]);

  useEffect(() => {
    let active = true;
    void (async () => {
      let saved = DEFAULT_STATE;
      try {
        const raw = await AsyncStorage.getItem(STORAGE_KEY);
        if (raw) {
          const parsed = JSON.parse(raw);
          saved = {
            ...DEFAULT_STATE, ...parsed,
            myEventIds: Array.isArray(parsed.myEventIds) ? parsed.myEventIds : DEFAULT_STATE.myEventIds,
            favoriteInvestorIds: Array.isArray(parsed.favoriteInvestorIds) ? parsed.favoriteInvestorIds : DEFAULT_STATE.favoriteInvestorIds,
          };
        }
      } catch { /* Use defaults when saved state is invalid. */ }
      if (!active) return;
      setState(saved);
      if (await getAuthToken()) {
        try {
          const user = await getMe();
          await setSessionId(user.session_id);
          const mode = modeFor(user);
          saved = { ...withAccount(saved, user), mode, onboarded: true, userProfile: { name: user.name, organization: user.company, role: mode } };
          setState(saved);
          void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
        } catch (failure) {
          if (failure instanceof ApiError && failure.status === 401) {
            await clearAuthToken();
            await clearSessionId();
            saved = { ...withAccount(saved, null), onboarded: false };
            setState(saved);
            void AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
          } else if (!saved.onboarded) {
            saved = { ...withAccount(saved, null), onboarded: false };
            setState(saved);
          }
        }
      } else {
        saved = { ...withAccount(saved, null), onboarded: false };
        setState(saved);
      }
      if (active) setHydrated(true);
    })();
    return () => { active = false; };
  }, []);

  const setMode = useCallback((mode: MatchMode) => {
    let sync = false;
    commit((current) => {
      if (current.authUser && mode !== modeFor(current.authUser)) return current;
      sync = !current.authUser;
      return { ...current, mode };
    });
    if (sync) void syncAnonymousMode(mode);
  }, [commit, syncAnonymousMode]);

  const completeOnboarding = useCallback((profile: UserProfile) => {
    let sync = false;
    commit((current) => {
      if (current.authUser) {
        const mode = modeFor(current.authUser);
        return { ...current, mode, userProfile: { ...current.userProfile, name: profile.name, organization: profile.organization }, onboarded: true };
      }
      sync = true;
      return { ...current, userProfile: profile, mode: profile.role, onboarded: true };
    });
    if (sync) void syncAnonymousMode(profile.role);
  }, [commit, syncAnonymousMode]);

  const resetOnboarding = useCallback(() => commit((current) => ({ ...current, onboarded: false })), [commit]);

  const authenticate = useCallback(async (request: () => Promise<{ user: AuthUser }>) => {
    setAuthLoading(true);
    try {
      const response = await request();
      await setSessionId(response.user.session_id);
      applyUser(response.user);
      return response.user;
    } finally { setAuthLoading(false); }
  }, [applyUser]);
  const loginWithCredentials = useCallback((input: { email: string; password: string }) => authenticate(() => loginAccount(input)), [authenticate]);
  const registerWithCredentials = useCallback((input: { email: string; password: string; name: string; company: string; role: AccountRole }) => authenticate(() => registerAccount(input)), [authenticate]);

  const logout = useCallback(async () => {
    setAuthLoading(true);
    try {
      await logoutAccount();
      await clearSessionId();
      commit((current) => ({ ...withAccount(current, null), onboarded: false, userProfile: DEFAULT_PROFILE, mode: 'raising' }));
    } finally { setAuthLoading(false); }
  }, [commit]);

  const toggleMyEvent = useCallback((id: string) => commit((current) => ({
    ...current,
    myEventIds: current.myEventIds.includes(id) ? current.myEventIds.filter((item) => item !== id) : [...current.myEventIds, id],
  })), [commit]);
  const addMyEvent = useCallback((id: string) => commit((current) => current.myEventIds.includes(id) ? current : ({ ...current, myEventIds: [...current.myEventIds, id] })), [commit]);
  const toggleFavoriteInvestor = useCallback((id: string) => commit((current) => ({
    ...current,
    favoriteInvestorIds: current.favoriteInvestorIds.includes(id) ? current.favoriteInvestorIds.filter((item) => item !== id) : [...current.favoriteInvestorIds, id],
  })), [commit]);
  const addFavoriteInvestor = useCallback((id: string) => commit((current) => current.favoriteInvestorIds.includes(id) ? current : ({ ...current, favoriteInvestorIds: [...current.favoriteInvestorIds, id] })), [commit]);

  const value = useMemo(() => ({
    ...state, hydrated, user: state.authUser ?? null, isAuthenticated: Boolean(state.authUser), authLoading, sessionExpired,
    setMode, completeOnboarding, resetOnboarding, toggleMyEvent, addMyEvent,
    toggleFavoriteInvestor, addFavoriteInvestor, loginWithCredentials, registerWithCredentials, logout, refreshMe,
  }), [state, hydrated, authLoading, sessionExpired, setMode, completeOnboarding, resetOnboarding, toggleMyEvent, addMyEvent, toggleFavoriteInvestor, addFavoriteInvestor, loginWithCredentials, registerWithCredentials, logout, refreshMe]);

  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>;
}

export const useMode = () => useContext(ModeContext);
