import type { ReactNode } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { font, space, useTheme } from '../theme';
import Card from './Card';

/** Estado de pantalla: cargando, vacío o error, con el mismo aspecto en todas partes. */
export default function StateView({
  kind,
  title,
  message,
  action,
}: {
  kind: 'loading' | 'empty' | 'error';
  title?: string;
  message?: string;
  action?: ReactNode;
}) {
  const { colors } = useTheme();
  if (kind === 'loading') {
    return (
      <View
        accessibilityLiveRegion="polite"
        style={{ flexDirection: 'row', alignItems: 'center', gap: space.md, paddingVertical: space.lg }}
      >
        <ActivityIndicator color={colors.accent} />
        <Text style={{ color: colors.textMuted, fontSize: font.body }}>{title ?? 'Cargando…'}</Text>
      </View>
    );
  }
  const err = kind === 'error';
  return (
    <Card
      style={
        err
          ? { backgroundColor: colors.dangerSoft, borderColor: colors.dangerSoft }
          : { alignItems: 'flex-start' }
      }
    >
      <View accessibilityRole={err ? 'alert' : undefined} style={{ gap: space.sm }}>
        <Text style={{ color: err ? colors.danger : colors.text, fontSize: font.lead, fontWeight: '700' }}>
          {title ?? (err ? 'Algo salió mal' : 'Todavía no hay nada aquí')}
        </Text>
        {message ? (
          <Text
            style={{ color: err ? colors.danger : colors.textMuted, fontSize: font.body, lineHeight: 22 }}
          >
            {message}
          </Text>
        ) : null}
        {action}
      </View>
    </Card>
  );
}
