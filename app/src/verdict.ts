import type { ClaimVerdict } from './api';

export const verdictLabels: Record<ClaimVerdict, string> = {
  confirmed: 'Confirmada',
  partially_confirmed: 'Parcial',
  contradicted: 'Contradicha',
  no_data: 'Sin datos',
};
export const verdictColors: Record<ClaimVerdict, string> = {
  confirmed: '#34d399',
  partially_confirmed: '#fbbf24',
  contradicted: '#f87171',
  no_data: '#94a3b8',
};
