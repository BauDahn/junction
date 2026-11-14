import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import type { Source } from '../api';
import { font, radius, space, useTheme } from '../theme';

function host(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

/** Lista de fuentes enlazadas (dominio visible). Todo dato de Cala lleva la suya. */
export function SourceList({ sources }: { sources: Source[] }) {
  const { colors } = useTheme();
  if (!sources.length) return null;
  return (
    <View style={{ gap: space.xs, marginTop: space.md }}>
      <Text
        style={{ color: colors.textFaint, fontSize: font.caption, fontWeight: '700', letterSpacing: 1 }}
      >
        FUENTES
      </Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
        {sources.map((s, i) => (
          <Pressable
            key={`${s.url}-${i}`}
            accessibilityRole="link"
            accessibilityLabel={`Fuente: ${s.name}`}
            onPress={() => Linking.openURL(s.url)}
            style={{
              borderWidth: 1,
              borderColor: colors.border,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.pill,
              paddingHorizontal: 10,
              paddingVertical: 4,
            }}
          >
            <Text style={{ color: colors.accent, fontSize: font.small }}>
              ↗ {s.name}
              <Text style={{ color: colors.textFaint }}> · {host(s.url)}</Text>
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

/**
 * Tabla de datos de Cala tal cual (filas de texto) con sus fuentes debajo.
 * Se desplaza en horizontal si no cabe (móvil).
 */
export default function SourceTable({
  columns,
  rows,
  sources = [],
  caption,
  minColWidth = 120,
}: {
  columns: string[];
  rows: (string | number | null | undefined)[][];
  sources?: Source[];
  caption?: string;
  minColWidth?: number;
}) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        backgroundColor: colors.surface,
        borderColor: colors.border,
        borderWidth: 1,
        borderRadius: radius.lg,
        overflow: 'hidden',
      }}
    >
      {caption ? (
        <Text
          style={{
            color: colors.text,
            fontSize: font.body,
            fontWeight: '700',
            padding: space.lg,
            paddingBottom: space.md,
          }}
        >
          {caption}
        </Text>
      ) : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ flexGrow: 1 }}>
          <View style={{ flexDirection: 'row', backgroundColor: colors.surfaceAlt }}>
            {columns.map((c) => (
              <Text
                key={c}
                style={{
                  flex: 1,
                  minWidth: minColWidth,
                  color: colors.textMuted,
                  fontSize: font.caption,
                  fontWeight: '700',
                  letterSpacing: 0.6,
                  paddingHorizontal: space.lg,
                  paddingVertical: space.sm,
                }}
              >
                {c.toUpperCase()}
              </Text>
            ))}
          </View>
          {rows.map((row, r) => (
            <View
              key={r}
              style={{ flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.border }}
            >
              {columns.map((_, c) => (
                <Text
                  key={c}
                  selectable
                  style={{
                    flex: 1,
                    minWidth: minColWidth,
                    color: c === 0 ? colors.text : colors.textMuted,
                    fontWeight: c === 0 ? '600' : '400',
                    fontSize: font.body,
                    lineHeight: 22,
                    paddingHorizontal: space.lg,
                    paddingVertical: space.md,
                  }}
                >
                  {row[c] == null || row[c] === '' ? '—' : String(row[c])}
                </Text>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
      {sources.length ? (
        <View style={{ padding: space.lg, paddingTop: 0 }}>
          <SourceList sources={sources} />
        </View>
      ) : null}
    </View>
  );
}
