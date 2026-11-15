import type { ReactNode } from 'react';
import { View, type StyleProp, type ViewStyle } from 'react-native';
import { radius, shadow, space, useTheme } from '../theme';

/** Base card: surface with a thin border. `raised` adds a shadow. */
export default function Card({
  children,
  raised,
  style,
}: {
  children: ReactNode;
  raised?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.surface,
          borderColor: colors.border,
          borderWidth: 1,
          borderRadius: radius.lg,
          padding: space.lg,
        },
        raised ? shadow : null,
        style,
      ]}
    >
      {children}
    </View>
  );
}
