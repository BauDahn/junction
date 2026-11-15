import { Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { FeedCard } from '../api/feed';
import { useMode } from '../mode';
import { font, space, tabularNums, useTheme } from '../theme';
import { ActionButton, Card, GRID_RADIUS } from '../ui/Shell';

/** One match as a bordered card: name and score, why it fits, sources, actions. */
export default function MatchCard({ card, eventId, sample = false }: { card: FeedCard; eventId?: string; sample?: boolean }) {
  const router = useRouter();
  const { colors } = useTheme();
  const { favoriteInvestorIds, toggleFavoriteInvestor, user, mode } = useMode();
  const saved = favoriteInvestorIds.includes(card.id);
  const openDossier = () => router.push({ pathname: '/entity/[id]', params: { id: card.id, ...(eventId ? { eventId } : {}), session_id: user?.session_id ?? '', mode } });
  const rule = { borderTopWidth: 1, borderColor: colors.border } as const;
  return (
    <Card style={{ flex: 1, padding: space.xl, gap: space.md }}>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: space.md }}>
        <Pressable accessibilityRole="link" onPress={() => openDossier()} style={{ flex: 1 }}>
          <Text style={{ fontSize: font.lead, fontWeight: '800', letterSpacing: -0.2, color: colors.text }}>{card.name}</Text>
        </Pressable>
        {!sample ? (
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={[{ color: colors.accent, fontWeight: '800', fontSize: font.h2, lineHeight: 24 }, tabularNums]}>{card.score}</Text>
            <Text style={{ fontSize: font.caption, color: colors.textMuted }}>match</Text>
          </View>
        ) : null}
      </View>
      <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>{card.one_liner}</Text>
      {card.tags.length ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs }}>
          {card.tags.slice(0, 4).map((tag) => (
            <View key={tag} style={{ borderWidth: 1, borderColor: colors.border, borderRadius: GRID_RADIUS, paddingHorizontal: space.sm, paddingVertical: 2 }}>
              <Text style={{ color: colors.textMuted, fontSize: font.caption }}>{tag}</Text>
            </View>
          ))}
        </View>
      ) : null}
      <View style={[rule, { paddingTop: space.sm, gap: space.xs }]}>
        <Text style={{ fontSize: font.caption, fontWeight: '700', color: colors.text }}>Why it fits</Text>
        {card.why_match.slice(0, 3).map((why, i) => <Text key={i} numberOfLines={1} style={{ color: colors.text, fontSize: font.small }}>{why}</Text>)}
      </View>
      {!sample && card.confidence < 0.5 ? <Text style={{ fontSize: font.caption, color: colors.textMuted }}>Partial data</Text> : null}
      {card.sources.length ? <Pressable accessibilityRole="link" accessibilityLabel={`${card.sources.length} sources, open dossier`} onPress={openDossier} style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}><Text style={{ color: colors.textMuted, fontSize: font.caption }}>{card.sources.length} sources</Text></Pressable> : null}
      <View style={[rule, { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: space.md }]}>
        <ActionButton label={saved ? 'Saved' : 'Save'} onPress={() => toggleFavoriteInvestor(card.id)} selected={saved} />
        <Pressable accessibilityRole="link" onPress={() => openDossier()} style={{ minHeight: 40, justifyContent: 'center' }}>
          <Text style={{ color: colors.accent, fontSize: font.small, fontWeight: '700' }}>View dossier →</Text>
        </Pressable>
      </View>
    </Card>
  );
}
