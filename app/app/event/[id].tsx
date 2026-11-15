import { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { useFocusEffect, useLocalSearchParams, useRouter } from 'expo-router';
import { getEventById } from '../../src/api/events';
import { getFeed, type FeedResponse } from '../../src/api/feed';
import MatchCard from '../../src/components/MatchCard';
import { getOrCreateSessionId } from '../../src/session';
import { onContextChanged } from '../../src/contextEvents';
import { useMode } from '../../src/mode';
import { font, space, tabularNums, useTheme } from '../../src/theme';
import { ActionButton, CardGrid, GRID_RADIUS, Page, PageHeader, useDesktop } from '../../src/ui/Shell';

export default function EventWorkspace() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id ?? '';
  const event = getEventById(id);
  const { colors } = useTheme();
  const desktop = useDesktop();
  const { width } = useWindowDimensions();
  const { mode, myEventIds, toggleMyEvent } = useMode();
  const [response, setResponse] = useState<FeedResponse | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const load = useCallback(async (silent = false) => {
    if (!event || event.participantData !== 'cala') return;
    if (!silent) { setLoading(true); setError(''); }
    try { const sessionId = await getOrCreateSessionId(); setResponse(await getFeed({ sessionId, mode, limit: 10, fallbackOnNetworkError: true })); }
    catch { if (!silent) setError('Matches could not be loaded. Check your connection and try again.'); }
    finally { if (!silent) setLoading(false); }
  }, [event, mode]);
  useEffect(() => { setResponse(null); void load(); }, [load]);
  const firstFocus = useRef(true);
  useFocusEffect(useCallback(() => {
    if (firstFocus.current) { firstFocus.current = false; return; }
    void load(true);
  }, [load]));
  useEffect(() => onContextChanged(() => { void load(true); }), [load]);
  const back = (
    <Pressable accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/feed')} style={{ minHeight: 40, justifyContent: 'center', alignSelf: 'flex-start' }}>
      <Text style={{ color: colors.accent, fontSize: font.small, fontWeight: '600' }}>← Back to events</Text>
    </Pressable>
  );
  if (!event) {
    return (
      <Page>
        {back}
        <PageHeader title="Event not found" />
      </Page>
    );
  }
  const attending = myEventIds.includes(event.id);
  const title = mode === 'investing' ? 'Recommended startups' : 'Recommended investors';
  const hasData = event.participantData === 'cala';
  const columns = width >= 1100 ? 3 : desktop ? 2 : 1;
  const notice = (heading: string, body: string, accent = false) => (
    <View style={{ padding: space.lg, borderWidth: 1, borderRadius: GRID_RADIUS, borderColor: accent ? colors.accent : colors.border, backgroundColor: accent ? colors.accentSoft : 'transparent', gap: space.xs, maxWidth: 640 }}>
      <Text style={{ fontSize: font.body, fontWeight: '700', color: accent ? colors.accent : colors.text }}>{heading}</Text>
      <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>{body}</Text>
    </View>
  );
  return (
    <Page>
      {back}
      <View style={{ height: desktop ? 240 : 160, borderRadius: GRID_RADIUS, overflow: 'hidden', backgroundColor: colors.accentSoft, marginTop: space.sm, marginBottom: space.xl }}>
        <Image source={{ uri: event.imageUrl }} resizeMode="cover" accessibilityIgnoresInvertColors style={{ position: 'absolute', width: '100%', height: '100%' }} />
      </View>
      <PageHeader title={event.name} subtitle={event.slogan}>
        <Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>{event.date} · {event.venue}, {event.city}</Text>
        <ActionButton label={attending ? 'Attending ✓' : 'Save event'} onPress={() => toggleMyEvent(event.id)} selected={attending} primary={attending} />
      </PageHeader>
      <View style={{ gap: space.xs, marginBottom: space.xl, paddingTop: space.xl, borderTopWidth: 1, borderColor: colors.border }}>
        <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '800', letterSpacing: -0.3, color: colors.text }}>{title}</Text>
        {hasData && !response?.is_sample ? <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19, maxWidth: 640 }}>Top matches from the Cala catalog for your profile. Cala does not yet list which investors attend this event.</Text> : null}
        {response?.confidence_note && !response.is_sample ? <Text style={{ fontSize: font.small, color: colors.textMuted, maxWidth: 640 }}>{response.confidence_note}</Text> : null}
      </View>
      {!hasData ? notice('No participant data in Cala yet', "We will show matches here once Cala has this event's participants.") : null}
      {hasData && loading ? <Text style={[{ color: colors.textMuted, fontSize: font.body }, tabularNums]}>Loading matches…</Text> : null}
      {hasData && error ? (
        <View style={{ gap: space.md }}>
          <Text style={{ color: colors.textMuted, fontSize: font.body }}>{error}</Text>
          <ActionButton label="Retry" onPress={() => void load()} />
        </View>
      ) : null}
      {response?.is_sample ? notice('Sample data', response.confidence_note ?? '', true) : null}
      {response?.items.length ? (
        <View style={{ marginTop: response.is_sample ? space.xl : 0 }}>
          <CardGrid columns={columns}>
            {response.items.map((card) => <MatchCard key={card.id} card={card} eventId={event.id} sample={response.is_sample} />)}
          </CardGrid>
        </View>
      ) : null}
    </Page>
  );
}
