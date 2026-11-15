import { Linking, Pressable, Text, View } from 'react-native';
import { useRouter } from 'expo-router';
import type { FeedCard } from '../api/feed';
import { useMode } from '../mode';
import { font, pageMargin, radius, space, tabularNums, useTheme } from '../theme';

function host(url: string) { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } }
export default function MatchCard({ card, eventId, sample = false }: { card: FeedCard; eventId?: string; sample?: boolean }) {
  const router = useRouter(); const { colors } = useTheme(); const { favoriteInvestorIds, toggleFavoriteInvestor } = useMode();
  const saved = favoriteInvestorIds.includes(card.id);
  const openDossier = () => router.push(eventId ? { pathname: '/entity/[id]', params: { id: card.id, eventId } } : { pathname: '/entity/[id]', params: { id: card.id } });
  const action = { backgroundColor: colors.accentSoft, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs + 2 } as const;
  return <View style={{ marginHorizontal: pageMargin, marginTop: space.md, padding: space.lg, borderRadius: radius.lg, backgroundColor: colors.surface, gap: space.md }}>
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: space.sm }}>
      <Pressable accessibilityRole="link" onPress={() => openDossier()} style={{ flex: 1 }}><Text style={{ fontSize: font.lead, fontWeight: '600', color: colors.text }}>{card.name}</Text></Pressable>
      {!sample ? <View style={{ alignItems: 'center', backgroundColor: colors.accentSoft, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs }}><Text style={[{ color: colors.accent, fontWeight: '700', fontSize: font.small }, tabularNums]}>{card.score}</Text><Text style={{ fontSize: font.caption, color: colors.textMuted }}>match</Text></View> : null}
    </View>
    <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>{card.one_liner}</Text>
    {card.tags.length ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.xs }}>{card.tags.slice(0, 4).map((tag) => <View key={tag} style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.sm + 2, paddingVertical: 3 }}><Text style={{ color: colors.textMuted, fontSize: font.caption }}>{tag}</Text></View>)}</View> : null}
    <View style={{ gap: space.xs }}><Text style={{ fontSize: font.caption, fontWeight: '700', color: colors.text }}>Why it fits</Text>{card.why_match.slice(0, 3).map((why, i) => <Text key={i} numberOfLines={1} style={{ color: colors.text, fontSize: font.small }}>{why}</Text>)}</View>
    {!sample && card.confidence < 0.5 ? <View style={{ alignSelf: 'flex-start', backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.sm + 2, paddingVertical: space.xs }}><Text style={{ fontSize: font.caption, color: colors.textMuted }}>Partial data</Text></View> : null}
    {card.sources.length ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>{card.sources.slice(0, 3).map((source, i) => <Pressable key={`${source.url}-${i}`} accessibilityRole="link" onPress={() => void Linking.openURL(source.url).catch(() => {})}><Text style={{ color: colors.accent, textDecorationLine: 'underline', fontSize: font.caption }}>{source.name} · {host(source.url)}</Text></Pressable>)}</View> : null}
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingTop: space.xs }}><Pressable accessibilityRole="button" onPress={() => toggleFavoriteInvestor(card.id)} style={action}><Text style={{ color: colors.accent, fontSize: font.small }}>{saved ? 'Saved' : 'Save'}</Text></Pressable><Pressable accessibilityRole="link" onPress={() => openDossier()}><Text style={{ color: colors.accent, fontSize: font.small, fontWeight: '600' }}>View dossier</Text></Pressable></View>
  </View>;
}
