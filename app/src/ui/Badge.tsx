import { Text, View } from 'react-native';
import { font, radius, useTheme } from '../theme';

export type Tone = 'confirmed' | 'partial' | 'contradicted' | 'neutral' | 'accent';

/** Etiqueta pequeña con color de tono (fondo suave + texto). */
export default function Badge({ label, tone = 'neutral' }: { label: string; tone?: Tone }) {
  const c = useTheme().colors;
  const map = {
    confirmed: [c.confirmed, c.confirmedSoft],
    partial: [c.partial, c.partialSoft],
    contradicted: [c.contradicted, c.contradictedSoft],
    neutral: [c.neutral, c.neutralSoft],
    accent: [c.accent, c.accentSoft],
  }[tone];
  return (
    <View
      style={{
        alignSelf: 'flex-start',
        backgroundColor: map[1],
        borderRadius: radius.pill,
        paddingHorizontal: 10,
        paddingVertical: 3,
      }}
    >
      <Text style={{ color: map[0], fontSize: font.caption, fontWeight: '700', letterSpacing: 0.3 }}>
        {label}
      </Text>
    </View>
  );
}
