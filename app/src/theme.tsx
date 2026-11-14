import { createContext, useContext, type ReactNode } from 'react';
import { useColorScheme, type TextStyle } from 'react-native';

/** Minimalist Cala Match design tokens: single indigo accent, clean neutrals, 1px borders, zero decorative shadows. */
export type Colors = {
  bg: string;
  surface: string;
  surfaceAlt: string;
  border: string;
  text: string;
  textMuted: string;
  textFaint: string;
  accent: string;
  accentText: string;
  accentSoft: string;
  danger: string;
  dangerSoft: string;
  confirmed: string;
  confirmedSoft: string;
  partial: string;
  partialSoft: string;
  contradicted: string;
  contradictedSoft: string;
  neutral: string;
  neutralSoft: string;
};

export const light: Colors = {
  bg: '#f8f9fc',
  surface: '#ffffff',
  surfaceAlt: '#f1f5f9',
  border: '#e2e8f0',
  text: '#0f172a',
  textMuted: '#475569',
  textFaint: '#64748b',
  accent: '#3730A3',
  accentText: '#ffffff',
  accentSoft: '#eef2ff',
  danger: '#b42318',
  dangerSoft: '#fef2f2',
  confirmed: '#166534',
  confirmedSoft: '#f0fdf4',
  partial: '#92400e',
  partialSoft: '#fffbeb',
  contradicted: '#991b1b',
  contradictedSoft: '#fef2f2',
  neutral: '#475569',
  neutralSoft: '#f1f5f9',
};

export const dark: Colors = {
  bg: '#0b1120',
  surface: '#111827',
  surfaceAlt: '#1e293b',
  border: '#273449',
  text: '#f1f5f9',
  textMuted: '#94a3b8',
  textFaint: '#64748b',
  accent: '#818cf8',
  accentText: '#0b1120',
  accentSoft: '#1e1b4b',
  danger: '#fca5a5',
  dangerSoft: '#3a1b25',
  confirmed: '#6ee7b7',
  confirmedSoft: '#0f291e',
  partial: '#fcd34d',
  partialSoft: '#2e2409',
  contradicted: '#fca5a5',
  contradictedSoft: '#3a1b25',
  neutral: '#94a3b8',
  neutralSoft: '#1e293b',
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, page: 20, xl: 24, xxl: 32 } as const;
export const pageMargin = 20;
export const radius = { sm: 6, md: 8, lg: 12, pill: 999 } as const;
export const font = {
  caption: 12,
  small: 13,
  body: 15,
  lead: 17,
  h2: 20,
  h1: 28,
  display: 34,
} as const;
export const tabularNums: Pick<TextStyle, 'fontVariant'> = { fontVariant: ['tabular-nums'] };
export const maxWidth = 880;
/** Kept for compatibility with existing components; intentionally flat without decorative shadows. */
export const shadow = {
  shadowColor: 'transparent',
  shadowOpacity: 0,
  shadowRadius: 0,
  shadowOffset: { width: 0, height: 0 },
  elevation: 0,
} as const;

export type Theme = { mode: 'dark' | 'light'; colors: Colors };

const ThemeContext = createContext<Theme>({ mode: 'light', colors: light });

/**
 * Provides theme colors across the app. Defaults to light mode.
 */
export function ThemeProvider({
  mode = 'light',
  children,
}: {
  mode?: 'dark' | 'light' | 'system';
  children: ReactNode;
}) {
  const scheme = useColorScheme();
  const resolved = mode === 'system' ? (scheme === 'dark' ? 'dark' : 'light') : mode;
  return (
    <ThemeContext.Provider value={{ mode: resolved, colors: resolved === 'light' ? light : dark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
