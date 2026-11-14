import { createContext, useContext, type ReactNode } from 'react';
import { useColorScheme } from 'react-native';

/** Sistema de diseño de Junction: herramienta de datos sobria; Cala (datos + fuentes) es la protagonista. */
export type Colors = {
  bg: string; // fondo de pantalla
  surface: string; // tarjetas
  surfaceAlt: string; // filas alternas, cabeceras de tabla
  border: string;
  text: string;
  textMuted: string;
  textFaint: string;
  accent: string; // acción principal / enlaces
  accentText: string; // texto sobre accent
  accentSoft: string; // fondo suave de acento
  danger: string;
  dangerSoft: string;
  // veredictos de Cala (texto + fondo suave)
  confirmed: string;
  confirmedSoft: string;
  partial: string;
  partialSoft: string;
  contradicted: string;
  contradictedSoft: string;
  neutral: string;
  neutralSoft: string;
};

export const dark: Colors = {
  bg: '#0a0f1c',
  surface: '#121a2c',
  surfaceAlt: '#17213a',
  border: '#25304a',
  text: '#eef2f9',
  textMuted: '#9aa8c2',
  textFaint: '#6b7a96',
  accent: '#6ea8fe',
  accentText: '#07101f',
  accentSoft: '#15284a',
  danger: '#fca5a5',
  dangerSoft: '#3a1b25',
  confirmed: '#5ddba0',
  confirmedSoft: '#10321f',
  partial: '#f5c451',
  partialSoft: '#38300f',
  contradicted: '#fb8a8a',
  contradictedSoft: '#3d1a22',
  neutral: '#9aa8c2',
  neutralSoft: '#1d2740',
};

export const light: Colors = {
  bg: '#f4f6fb',
  surface: '#ffffff',
  surfaceAlt: '#f0f3f9',
  border: '#dde3ee',
  text: '#0e1626',
  textMuted: '#4d5b75',
  textFaint: '#7a879e',
  accent: '#1f5fd6',
  accentText: '#ffffff',
  accentSoft: '#e3edff',
  danger: '#b42318',
  dangerSoft: '#fdeaea',
  confirmed: '#117a4b',
  confirmedSoft: '#dcf5e8',
  partial: '#8a5a00',
  partialSoft: '#fdf0cc',
  contradicted: '#b42318',
  contradictedSoft: '#fde4e4',
  neutral: '#4d5b75',
  neutralSoft: '#e8ecf4',
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 } as const;
export const font = {
  caption: 12,
  small: 13,
  body: 15,
  lead: 17,
  h2: 20,
  h1: 28,
  display: 34,
} as const;
/** Ancho máximo del contenido (web ancho). */
export const maxWidth = 880;
/** Sombra suave (RN web la traduce a box-shadow). */
export const shadow = {
  shadowColor: '#000',
  shadowOpacity: 0.18,
  shadowRadius: 14,
  shadowOffset: { width: 0, height: 6 },
  elevation: 3,
} as const;

export type Theme = { mode: 'dark' | 'light'; colors: Colors };

const ThemeContext = createContext<Theme>({ mode: 'dark', colors: dark });

/**
 * mode: 'dark' (por defecto, coincide con el resto de la app), 'light', o 'system'.
 * Cuando chat/journal/layout adopten los tokens se puede pasar 'system'.
 */
export function ThemeProvider({
  mode = 'dark',
  children,
}: {
  mode?: 'dark' | 'light' | 'system';
  children: ReactNode;
}) {
  const scheme = useColorScheme();
  const resolved = mode === 'system' ? (scheme === 'light' ? 'light' : 'dark') : mode;
  return (
    <ThemeContext.Provider value={{ mode: resolved, colors: resolved === 'light' ? light : dark }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
