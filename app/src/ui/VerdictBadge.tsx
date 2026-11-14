import Badge, { type Tone } from './Badge';

const VERDICTS: Record<string, { label: string; tone: Tone }> = {
  confirmed: { label: 'Confirmado', tone: 'confirmed' },
  partially_confirmed: { label: 'Parcial', tone: 'partial' },
  contradicted: { label: 'Contradicho', tone: 'contradicted' },
  no_data: { label: 'Sin datos', tone: 'neutral' },
  not_checked: { label: 'No verificado', tone: 'neutral' },
  error: { label: 'Error', tone: 'contradicted' },
};

/** Veredicto de Cala para una afirmación (claves de `Claim['verdict']`). */
export default function VerdictBadge({ verdict }: { verdict: string }) {
  const v = VERDICTS[verdict] ?? { label: verdict, tone: 'neutral' as Tone };
  return <Badge label={v.label} tone={v.tone} />;
}
