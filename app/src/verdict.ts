import type { ClaimVerdict } from './api';

export const verdictLabels: Record<ClaimVerdict, string> = {
  confirmed: 'Confirmada',
  partially_confirmed: 'Parcial',
  contradicted: 'Contradicha',
  no_data: 'Sin datos',
};
