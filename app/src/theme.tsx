import { createContext, useContext, type ReactNode } from 'react';
import { useColorScheme, type TextStyle } from 'react-native';

/** calado design tokens: corporate colors are white and #006CFF. Single blue accent, hairline 1px borders, zero decorative shadows. */
export const brandBlue = '#006CFF';
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
  secondary: string;
  secondarySoft: string;
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
  bg: '#f1f6ff',
  surface: '#ffffff',
  surfaceAlt: '#e8f0fd',
  border: '#e6edf8',
  text: '#0b1424',
  textMuted: '#475569',
  textFaint: '#475569',
  accent: '#006CFF',
  accentText: '#ffffff',
  accentSoft: '#e8f1ff',
  secondary: '#006CFF',
  secondarySoft: '#e8f1ff',
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
  bg: '#070d1a',
  surface: '#0d1526',
  surfaceAlt: '#16213a',
  border: '#1b2a45',
  text: '#f1f5f9',
  textMuted: '#94a3b8',
  textFaint: '#94a3b8',
  accent: '#4D96FF',
  accentText: '#04101f',
  accentSoft: '#0f2747',
  secondary: '#4D96FF',
  secondarySoft: '#0f2747',
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

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const pageMargin = 20;
export const radius = { sm: 8, md: 12, lg: 20, pill: 999 } as const;
export const font = {
  caption: 12,
  small: 13,
  body: 15,
  lead: 17,
  h2: 20,
  h1: 28,
} as const;
export const tabularNums: Pick<TextStyle, 'fontVariant'> = { fontVariant: ['tabular-nums'] };
export const maxWidth = 760;
/** Altura de la barra inferior: el boton flotante debe usar bottom >= tabBarHeight + space.md para no tapar pestanas. */
export const tabBarHeight = 64;
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
