import { Text, View } from 'react-native';
import type { Card as CardData } from '../api';
import { font, space, useTheme } from '../theme';
import { Card, SourceList } from '../ui';

export default function CardView({ card }: { card: CardData }) {
  const { colors } = useTheme();
  return (
    <Card style={{ marginTop: space.md }}>
      <Text style={{ color: colors.text, fontWeight: '700', fontSize: font.lead }}>{card.title}</Text>
      {card.subtitle ? (
        <Text style={{ color: colors.accent, fontSize: font.small, marginTop: space.xs }}>
          {card.subtitle}
        </Text>
      ) : null}
      <View style={{ marginTop: space.sm }}>
        <Text style={{ color: colors.textMuted, fontSize: font.body, lineHeight: 22 }}>{card.reason}</Text>
      </View>
      <SourceList sources={card.sources} />
    </Card>
  );
}
