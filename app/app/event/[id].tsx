import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { getEventById } from '../../src/api/events';
import { getFeed, type FeedResponse } from '../../src/api/feed';
import MatchCard from '../../src/components/MatchCard';
import { getOrCreateSessionId } from '../../src/session';
import { useMode } from '../../src/mode';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../../src/theme';
export default function EventWorkspace() {
  const router = useRouter(); const params = useLocalSearchParams<{ id?: string | string[] }>(); const id = Array.isArray(params.id) ? params.id[0] : params.id ?? '';
  const event = getEventById(id); const { colors } = useTheme(); const { mode, myEventIds, toggleMyEvent } = useMode();
  const [response, setResponse] = useState<FeedResponse | null>(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const load = useCallback(async () => {
    if (!event || event.participantData !== 'cala') return;
    setLoading(true); setError('');
    try { const sessionId = await getOrCreateSessionId(); setResponse(await getFeed({ sessionId, mode, limit: 10, fallbackOnNetworkError: true })); }
    catch { setError('Matches could not be loaded. Check your connection and try again.'); }
    finally { setLoading(false); }
  }, [event, mode]);
  useEffect(() => { setResponse(null); void load(); }, [load]);
  const action = { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm } as const;
  const back = <Pressable accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/feed')}><Text style={{ color: colors.accent, fontSize: font.small }}>Back to Events</Text></Pressable>;
  if (!event) return <View style={{ flex: 1, backgroundColor: colors.bg, padding: pageMargin, gap: space.md }}>{back}<Text accessibilityRole="header" style={{ color: colors.text, fontSize: font.h1, fontWeight: '700' }}>Event not found</Text></View>;
  const attending = myEventIds.includes(event.id); const title = mode === 'investing' ? 'Recommended startups' : 'Recommended investors';
  return <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl }}><View style={{ width: '100%', maxWidth, backgroundColor: colors.surface }}>
    <View style={{ padding: pageMargin, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>{back}<Text accessibilityRole="header" style={{ fontSize: font.h1, fontWeight: '700', color: colors.text }}>{event.name}</Text><Text style={{ fontSize: font.body, color: colors.textMuted }}>{event.slogan}</Text><Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>{event.date} · {event.venue}, {event.city}</Text><Pressable accessibilityRole="button" onPress={() => toggleMyEvent(event.id)} style={[action, { alignSelf: 'flex-start', borderColor: attending ? colors.accent : colors.border, backgroundColor: attending ? colors.accent : colors.surface }]}><Text style={{ color: attending ? colors.accentText : colors.accent, fontSize: font.small, fontWeight: '600' }}>{attending ? 'Attending' : 'Save event'}</Text></Pressable></View>
    <View style={{ paddingTop: pageMargin }}><View style={{ paddingHorizontal: pageMargin, paddingBottom: space.md, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.xs }}><Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>{title}</Text>{event.participantData === 'cala' && !response?.is_sample ? <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>Top matches from the Cala catalog for your profile. Cala does not yet list which investors attend this event.</Text> : null}{response?.confidence_note && !response.is_sample ? <Text style={{ fontSize: font.small, color: colors.textMuted }}>{response.confidence_note}</Text> : null}</View>
      {event.participantData === 'none' ? <View style={{ margin: pageMargin, padding: space.lg, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, gap: space.xs }}><Text style={{ fontSize: font.body, color: colors.text, fontWeight: '600' }}>No participant data in Cala yet</Text><Text style={{ fontSize: font.small, color: colors.textMuted }}>We will show matches here once Cala has this event's participants.</Text></View> : null}
      {event.participantData === 'cala' && loading ? <Text style={{ padding: pageMargin, color: colors.textMuted, fontSize: font.body }}>Loading matches…</Text> : null}
      {event.participantData === 'cala' && error ? <View style={{ padding: pageMargin, gap: space.md }}><Text style={{ color: colors.textMuted, fontSize: font.body }}>{error}</Text><Pressable accessibilityRole="button" onPress={() => void load()} style={[action, { alignSelf: 'flex-start' }]}><Text style={{ color: colors.accent, fontSize: font.small }}>Retry</Text></Pressable></View> : null}
      {response?.is_sample ? <View style={{ marginHorizontal: pageMargin, marginTop: space.md, padding: space.md, borderWidth: 1, borderColor: colors.accent, borderRadius: radius.md, backgroundColor: colors.accentSoft, gap: space.xs }}><Text style={{ color: colors.accent, fontWeight: '700', fontSize: font.small }}>Sample data</Text><Text style={{ color: colors.textMuted, fontSize: font.small }}>{response.confidence_note}</Text></View> : null}
      {response?.items.map((card) => <MatchCard key={card.id} card={card} eventId={event.id} sample={response.is_sample} />)}
    </View>
  </View></ScrollView>;
}
