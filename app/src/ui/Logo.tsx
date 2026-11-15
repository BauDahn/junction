import { Text, View } from 'react-native';
import { brandBlue, useTheme } from '../theme';

/** calado wordmark: "cala" in ink, "do" in the corporate blue (#006CFF). */
export default function Logo({ size = 28 }: { size?: number }) {
  const { colors, mode } = useTheme();
  const style = { fontSize: size, lineHeight: Math.round(size * 1.15), fontWeight: '800', letterSpacing: -size * 0.04 } as const;
  return (
    <View accessible accessibilityRole="image" accessibilityLabel="calado" style={{ flexDirection: 'row', alignItems: 'baseline' }}>
      <Text style={{ ...style, color: colors.text }}>cala</Text>
      <Text style={{ ...style, color: mode === 'dark' ? colors.accent : brandBlue }}>do</Text>
    </View>
  );
}
