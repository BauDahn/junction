import { Image, Text, View } from 'react-native';
import { brandBlue, useTheme } from '../theme';

/** calado logo: the "c" mark (a circle with a cut-out and a match dot) followed by the wordmark, "cala" in ink and "do" in #006CFF. */
export default function Logo({ size = 28, mark = true }: { size?: number; mark?: boolean }) {
  const { colors, mode } = useTheme();
  const style = { fontSize: size, lineHeight: Math.round(size * 1.15), fontWeight: '800', letterSpacing: -size * 0.04 } as const;
  return (
    <View accessible accessibilityRole="image" accessibilityLabel="calado" style={{ flexDirection: 'row', alignItems: 'center', gap: Math.round(size * 0.3) }}>
      {mark ? <Image source={require('../../assets/mark.png')} accessibilityElementsHidden style={{ width: Math.round(size * 1.15), height: Math.round(size * 1.15) }} /> : null}
      <View style={{ flexDirection: 'row', alignItems: 'baseline' }}>
        <Text style={{ ...style, color: colors.text }}>cala</Text>
        <Text style={{ ...style, color: mode === 'dark' ? colors.accent : brandBlue }}>do</Text>
      </View>
    </View>
  );
}
