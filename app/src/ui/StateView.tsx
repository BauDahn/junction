import type { ReactNode } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { font, radius, space, useTheme } from '../theme';

/** Screen state: loading skeleton, empty state, or error state with consistent minimalist styling. */
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
        style={{ gap: space.md, paddingVertical: space.lg }}
      >
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={{ color: colors.textMuted, fontSize: font.small }}>
            {title ?? 'Loading…'}
          </Text>
        </View>
        <View style={{ gap: space.sm }}>
          <View
            style={{
              height: 12,
              width: '55%',
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.sm,
            }}
          />
          <View
            style={{
              height: 12,
              width: '85%',
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.sm,
            }}
          />
          <View
            style={{
              height: 12,
              width: '40%',
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.sm,
            }}
          />
        </View>
      </View>
    );
  }

  const err = kind === 'error';
  return (
    <View
      accessibilityRole={err ? 'alert' : undefined}
      style={{
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderWidth: 1,
        borderRadius: radius.sm,
        padding: space.lg,
        gap: space.sm,
        alignItems: 'flex-start',
      }}
    >
      <Text
        style={{
          color: err ? colors.danger : colors.text,
          fontSize: font.lead,
          fontWeight: '600',
        }}
      >
        {title ?? (err ? 'Something went wrong' : 'Nothing here yet')}
      </Text>
      {message ? (
        <Text
          style={{
            color: colors.textMuted,
            fontSize: font.body,
            lineHeight: 22,
          }}
        >
          {message}
        </Text>
      ) : null}
      {action ? <View style={{ marginTop: space.xs }}>{action}</View> : null}
    </View>
  );
}
