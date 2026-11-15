import { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import type { Source } from '../../src/api';
import { ApiError } from '../../src/api';
import { fetchEntityDetail, type EntityDetail } from '../../src/api/entities';
import { useMode } from '../../src/mode';
import { getOrCreateSessionId } from '../../src/session';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../../src/theme';

function host(url: string) { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; } }

function Sources({ sources }: { sources: Source[] }) {
  const { colors } = useTheme();
  if (!sources.length) return null;
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.xs }}>{sources.map((source, i) => <Pressable key={`${source.url}-${i}`} accessibilityRole="link" accessibilityLabel={`Source: ${source.name}, ${host(source.url)}`} onPress={() => void Linking.openURL(source.url).catch(() => {})}><Text style={{ color: colors.accent, fontSize: font.caption, textDecorationLine: 'underline' }}>{source.name} · {host(source.url)}</Text></Pressable>)}</View>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  return <View style={{ paddingVertical: space.xl, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}><Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>{title}</Text>{children}</View>;
}

function Skeleton() {
  const { colors } = useTheme();
  const opacity = useRef(new Animated.Value(0.45)).current;
  useEffect(() => {
    const animation = Animated.loop(Animated.sequence([Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }), Animated.timing(opacity, { toValue: 0.45, duration: 700, useNativeDriver: true })]));
    animation.start(); return () => animation.stop();
  }, [opacity]);
  const bar = (width: `${number}%`, height = 14) => <Animated.View style={{ width, height, borderRadius: radius.sm, backgroundColor: colors.surfaceAlt, opacity }} />;
  return <View accessibilityLabel="Loading entity details" style={{ gap: space.xl, paddingVertical: space.xl }}><View style={{ gap: space.md }}>{bar('65%', 28)}{bar('35%')}{bar('42%')}</View>{[0, 1, 2].map((section) => <View key={section} style={{ gap: space.md }}><View style={{ width: '32%', height: 18, borderRadius: radius.sm, backgroundColor: colors.surfaceAlt }} />{bar('90%')}{bar('72%')}</View>)}</View>;
}

export default function EntityDossier() {
  const router = useRouter();
  const params = useLocalSearchParams<{ id?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id ?? '';
  const { mode, user, favoriteInvestorIds, toggleFavoriteInvestor } = useMode();
  const { colors } = useTheme();
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [isSample, setIsSample] = useState(false);
  const [error, setError] = useState('');
  const [notFound, setNotFound] = useState(false);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError(''); setNotFound(false); setDetail(null);
    try {
      const sid = user?.session_id ?? await getOrCreateSessionId();
      const result = await fetchEntityDetail(id, mode, sid);
      setDetail(result.detail); setIsSample(result.isSample); setNotFound(!result.detail);
    } catch (caught) {
      const status = caught instanceof ApiError ? caught.status : 0;
      setError(status === 504 ? 'Cala did not answer in time.' : status === 401 ? 'Sign in to see this page.' : status === 404 ? 'Cala has no data for this company.' : status === 429 ? 'Too many requests, try again in a minute.' : status === 503 ? 'Cala is unavailable right now.' : status === 422 ? 'This link is not a valid company id.' : caught instanceof Error ? caught.message : 'Entity details could not be loaded.');
    } finally { setLoading(false); }
  }, [id, mode, user?.session_id]);
  useEffect(() => { void load(); }, [load]);
  const currentDetail = detail?.id === id ? detail : null;
  const saved = currentDetail ? favoriteInvestorIds.includes(currentDetail.id) : false;
  const actionStyle = { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm } as const;
  const back = <Pressable accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/feed')}><Text style={{ color: colors.accent, fontSize: font.small }}>Back</Text></Pressable>;
  const retry = <Pressable accessibilityRole="button" onPress={() => void load()} style={[actionStyle, { alignSelf: 'flex-start' }]}><Text style={{ color: colors.accent, fontSize: font.small, fontWeight: '600' }}>Retry</Text></Pressable>;
  const signIn = <Pressable accessibilityRole="button" onPress={() => router.push({ pathname: '/onboarding', params: { tab: 'login' } })} style={[actionStyle, { alignSelf: 'flex-start' }]}><Text style={{ color: colors.accent, fontSize: font.small, fontWeight: '600' }}>Sign in</Text></Pressable>;
  const hasContent = Boolean(currentDetail && (currentDetail.description || currentDetail.facts.length || currentDetail.rounds.length || currentDetail.people.length || currentDetail.portfolio.length || currentDetail.why_match.length));
  return <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl }}><View style={{ width: '100%', maxWidth, paddingHorizontal: pageMargin, backgroundColor: colors.surface }}>
    <View style={{ paddingVertical: space.xl, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>{back}
      {loading ? <Skeleton /> : null}
      {error ? <><Text style={{ color: colors.text, fontSize: font.body, lineHeight: 22 }}>{error}</Text>{!user && error === 'Sign in to see this page.' ? signIn : retry}</> : null}
      {notFound ? <Text style={{ color: colors.textMuted, fontSize: font.body }}>Not found in the graph or in Cala</Text> : null}
      {currentDetail ? <><View style={{ flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: space.md }}><Text accessibilityRole="header" style={{ flex: 1, fontSize: font.h1, lineHeight: 34, color: colors.text, fontWeight: '700' }}>{currentDetail.name}</Text><Text style={{ color: colors.textMuted, fontSize: font.small, paddingTop: space.xs }}>{currentDetail.type === 'investor' ? 'Investor' : 'Startup'}</Text></View>
        {currentDetail.score !== undefined || currentDetail.confidence !== undefined ? <Text style={[{ color: colors.accent, fontSize: font.small, fontWeight: '600' }, tabularNums]}>{currentDetail.score !== undefined ? `Match ${currentDetail.score}` : ''}{currentDetail.confidence !== undefined ? ` · ${Math.round(currentDetail.confidence * 100)}% confidence` : ''}</Text> : null}
        <Pressable accessibilityRole="button" accessibilityState={{ selected: saved }} onPress={() => toggleFavoriteInvestor(currentDetail.id)} style={[actionStyle, { alignSelf: 'flex-start', borderColor: saved ? colors.accent : colors.border }]}><Text style={{ fontSize: font.small, color: colors.accent, fontWeight: '600' }}>{saved ? 'Saved' : 'Save'}</Text></Pressable>
      </> : null}
    </View>
    {isSample && currentDetail ? <View style={{ marginTop: space.md, padding: space.md, borderWidth: 1, borderColor: colors.accent, borderRadius: radius.md, backgroundColor: colors.accentSoft }}><Text style={{ color: colors.accent, fontWeight: '700', fontSize: font.small }}>Sample data</Text></View> : null}
    {currentDetail ? <>
      {currentDetail.description ? <Section title="About"><Text style={{ color: colors.text, fontSize: font.body, lineHeight: 23 }}>{currentDetail.description}</Text></Section> : null}
      {currentDetail.facts.length ? <Section title="Key facts">{currentDetail.facts.map((fact, i) => <View key={`${fact.label}-${i}`} style={{ gap: space.xs }}><Text style={{ color: colors.textMuted, fontSize: font.caption, textTransform: 'uppercase', letterSpacing: 0.5 }}>{fact.label}</Text><Text style={{ color: colors.text, fontSize: font.body, lineHeight: 22 }}>{fact.value}</Text><Sources sources={fact.sources} /></View>)}</Section> : null}
      {currentDetail.rounds.length ? <Section title="Funding rounds">{(() => {
        const others = (round: EntityDetail['rounds'][number]) => round.investors.filter((name) => name !== currentDetail.name && !round.leads.includes(name));
        const bare = currentDetail.rounds.filter((round) => !round.round_type && !round.amount && !round.date && !round.leads.length && !others(round).length);
        const rich = currentDetail.rounds.filter((round) => !bare.includes(round));
        const bareSources = bare.flatMap((round) => round.sources).filter((s, i, all) => all.findIndex((o) => o.url === s.url) === i);
        const muted = { color: colors.textMuted, fontSize: font.small, lineHeight: 20 } as const;
        return <>{rich.map((round, i) => <View key={`${round.round_type}-${round.date}-${i}`} style={{ gap: space.xs }}><Text style={[{ fontSize: font.body, fontWeight: '600', color: colors.text }, tabularNums]}>{[round.round_type, round.amount, round.date].filter(Boolean).join(' · ') || 'Funding round'}</Text>{round.leads.length ? <Text style={muted}>Lead: {round.leads.join(', ')}</Text> : null}{others(round).length ? <Text style={muted}>Co-investors: {others(round).join(', ')}</Text> : null}<Sources sources={round.sources} /></View>)}{bare.length ? <View style={{ gap: space.xs }}><Text style={muted}>{bare.length} {bare.length === 1 ? 'round' : 'rounds'} on record in Cala, without public details</Text><Sources sources={bareSources} /></View> : null}</>;
      })()}</Section> : null}
      {currentDetail.people.length ? <Section title="People">{currentDetail.people.map((person) => <Pressable key={person.id} accessibilityRole="link" onPress={() => router.push({ pathname: '/entity/[id]', params: { id: person.id, session_id: user?.session_id ?? '', mode } })} style={{ gap: space.xs }}><Text style={{ color: colors.accent, fontSize: font.body, fontWeight: '600', textDecorationLine: 'underline' }}>{person.name}</Text><Text style={{ color: colors.textMuted, fontSize: font.small }}>{person.role}{person.since ? ` · Since ${person.since}` : ''}</Text></Pressable>)}</Section> : null}
      {currentDetail.portfolio.length ? <Section title="Portfolio">{currentDetail.portfolio.map((company) => <Pressable key={company.id} accessibilityRole="link" onPress={() => router.push({ pathname: '/entity/[id]', params: { id: company.id, session_id: user?.session_id ?? '', mode } })}><Text style={{ color: colors.accent, fontSize: font.body, textDecorationLine: 'underline' }}>{company.name}</Text></Pressable>)}</Section> : null}
      {currentDetail.why_match.length ? <Section title="Why it matches">{currentDetail.why_match.map((item, i) => <View key={`${item.signal}-${i}`} style={{ gap: space.xs }}><Text style={{ fontSize: font.body, color: colors.text, lineHeight: 22 }}>{item.text}</Text><Sources sources={item.sources} /></View>)}</Section> : null}
      {!hasContent ? <Text style={{ paddingVertical: space.xl, color: colors.textMuted, fontSize: font.body }}>Not available in Cala</Text> : null}
    </> : null}
  </View></ScrollView>;
}
