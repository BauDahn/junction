import { ActivityIndicator, Pressable, Text } from 'react-native';
import { font, radius, space, useTheme } from '../theme';

type Variant = 'primary' | 'secondary' | 'ghost';

export default function Button({
  label,
  onPress,
  variant = 'primary',
  loading,
  disabled,
}: {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  loading?: boolean;
  disabled?: boolean;
}) {
  const { colors } = useTheme();
  const off = disabled || loading;
  const bg =
    variant === 'primary' ? colors.accent : variant === 'secondary' ? colors.surfaceAlt : 'transparent';
  const fg =
    variant === 'primary' ? colors.accentText : variant === 'secondary' ? colors.text : colors.accent;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: !!off, busy: !!loading }}
      disabled={off}
      onPress={onPress}
      style={({ pressed }) => ({
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: space.sm,
        minHeight: 44,
        paddingHorizontal: space.lg,
        borderRadius: radius.md,
        backgroundColor: bg,
        borderWidth: variant === 'secondary' ? 1 : 0,
        borderColor: colors.border,
        opacity: off ? 0.5 : pressed ? 0.85 : 1,
      })}
    >
      {loading ? <ActivityIndicator size="small" color={fg} /> : null}
      <Text style={{ color: fg, fontSize: font.body, fontWeight: '600' }}>{label}</Text>
    </Pressable>
  );
}
