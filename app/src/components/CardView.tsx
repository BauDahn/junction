import { Linking, Pressable, Text, View } from 'react-native';
import type { Card as CardData } from '../api';
import { font, space, useTheme } from '../theme';

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

/** Flat, hairline-separated recommendation row with clickable Cala sources. */
export default function CardView({ card }: { card: CardData }) {
  const { colors } = useTheme();
  return (
    <View
      style={{
        borderTopWidth: 1,
        borderTopColor: colors.border,
        paddingVertical: space.lg,
        gap: space.xs,
      }}
    >
      <Text style={{ color: colors.text, fontWeight: '600', fontSize: font.body }}>
        {card.title}
      </Text>
      {card.subtitle ? (
        <Text style={{ color: colors.textMuted, fontSize: font.small }}>{card.subtitle}</Text>
      ) : null}
      <Text
        style={{
          color: colors.textMuted,
          fontSize: font.body,
          lineHeight: 22,
          marginTop: space.xs,
        }}
      >
        {card.reason}
      </Text>
      {card.sources?.length ? (
        <View style={{ marginTop: space.sm, gap: space.xs }}>
          <Text
            style={{
              color: colors.textFaint,
              fontSize: 11,
              fontWeight: '600',
              letterSpacing: 0.6,
            }}
          >
            SOURCES
          </Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md }}>
            {card.sources.map((source, index) => (
              <Pressable
                key={`${source.url}-${index}`}
                accessibilityRole="link"
                accessibilityLabel={`Source: ${source.name}`}
                onPress={() => {
                  if (source.url) void Linking.openURL(source.url);
                }}
              >
                <Text style={{ color: colors.accent, fontSize: font.small }}>
                  <Text style={{ textDecorationLine: 'underline' }}>{source.name}</Text>
                  {source.url ? (
                    <Text style={{ color: colors.textFaint }}> · {host(source.url)}</Text>
                  ) : null}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}
    </View>
  );
}
