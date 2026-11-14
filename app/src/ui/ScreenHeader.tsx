import type { ReactNode } from 'react';
import { Text, View } from 'react-native';
import { font, space, useTheme } from '../theme';

/** Encabezado de pantalla: eyebrow + título + subtítulo + acción opcional a la derecha. */
export default function ScreenHeader({
  title,
  subtitle,
  eyebrow = 'JUNCTION · DATOS DE CALA',
  right,
}: {
  title: string;
  subtitle?: string;
  eyebrow?: string;
  right?: ReactNode;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: space.lg,
        marginBottom: space.xl,
      }}
    >
      <View style={{ flexShrink: 1 }}>
        <Text
          style={{
            color: colors.accent,
            fontSize: font.caption,
            fontWeight: '700',
            letterSpacing: 1.6,
            marginBottom: space.sm,
          }}
        >
          {eyebrow}
        </Text>
        <Text
          accessibilityRole="header"
          style={{ color: colors.text, fontSize: font.h1, fontWeight: '800' }}
        >
          {title}
        </Text>
        {subtitle ? (
          <Text
            style={{ color: colors.textMuted, fontSize: font.body, lineHeight: 22, marginTop: space.xs }}
          >
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right}
    </View>
  );
}
