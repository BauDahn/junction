import { useEffect, useMemo, useState } from 'react';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import type { Source } from '../../src/api';
import { fetchEntityDetail, type EntityDetail } from '../../src/api/entities';
import { getEventById } from '../../src/api/events';
import { useMode } from '../../src/mode';
import { getOrCreateSessionId } from '../../src/session';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../../src/theme';

function host(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return url; }
}

function Sources({ sources }: { sources: Source[] }) {
  const { colors } = useTheme();
  if (!sources.length) return null;
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.xs }}>{sources.map((source, index) => <Pressable key={`${source.url}-${index}`} accessibilityRole="link" onPress={() => void Linking.openURL(source.url).catch(() => {})}><Text style={[{ fontSize: font.caption, color: colors.accent, textDecorationLine: 'underline' }, tabularNums]}>{source.name}{source.url ? ` · ${host(source.url)}` : ''}{source.date ? ` (${source.date})` : ''}</Text></Pressable>)}</View>;
}
function SectionRow({ title, children }: { title: string; children: React.ReactNode }) {
  const { colors } = useTheme();
  return <View style={{ paddingVertical: space.lg, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.xs }}><Text style={{ fontSize: font.small, color: colors.textMuted, fontWeight: '600' }}>{title}</Text>{children}</View>;
}
export default function InvestorDossier() {
  const router = useRouter(); const params = useLocalSearchParams<{ id?: string | string[]; eventId?: string | string[] }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id ?? ''; const eventId = Array.isArray(params.eventId) ? params.eventId[0] : params.eventId;
  const { mode, favoriteInvestorIds, toggleFavoriteInvestor } = useMode(); const { colors } = useTheme();
  const [detail, setDetail] = useState<EntityDetail | null>(null); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  useEffect(() => { let active = true; setLoading(true); setError(''); void (async () => {
    try { const sid = await getOrCreateSessionId(); const result = await fetchEntityDetail(id, mode, sid); if (active) setDetail(result.detail); }
    catch { if (active) setError('Investor details could not be loaded. Check your connection and try again.'); }
    finally { if (active) setLoading(false); }
  })(); return () => { active = false; }; }, [id, mode]);
  const event = useMemo(() => eventId ? getEventById(eventId) : undefined, [eventId]);
  const saved = detail ? favoriteInvestorIds.includes(detail.id) : false;
  const sourceAction = { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm } as const;
  return <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl }}>
    <View style={{ width: '100%', maxWidth, paddingHorizontal: pageMargin, backgroundColor: colors.surface }}>
      <View style={{ paddingVertical: space.lg, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>
        <Pressable accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/feed')}><Text style={{ color: colors.accent, fontSize: font.small }}>← Back</Text></Pressable>
        {loading ? <Text style={{ fontSize: font.body, color: colors.textMuted }}>Loading investor dossier…</Text> : null}
        {error ? <Text style={{ fontSize: font.body, color: colors.textMuted }}>{error}</Text> : null}
        {detail ? <>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.md }}><Text accessibilityRole="header" style={{ flex: 1, fontSize: font.h1, color: colors.text, fontWeight: '700' }}>{detail.name}</Text><Text style={[{ color: colors.accent, fontSize: font.small, fontWeight: '600' }, tabularNums]}>Match {Math.round(detail.score ?? 0)}</Text></View>
          <Pressable accessibilityRole="button" onPress={() => toggleFavoriteInvestor(detail.id)} style={[sourceAction, { alignSelf: 'flex-start', borderColor: saved ? colors.accent : colors.border }]}><Text style={{ fontSize: font.small, color: colors.accent }}>{saved ? '★ Saved investor' : '☆ Save to favorites'}</Text></Pressable>
        </> : null}
      </View>
      {detail ? <>
        <View style={{ paddingTop: space.lg, borderBottomWidth: 1, borderBottomColor: colors.border }}>
          <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>Cala verified profile</Text>
          <SectionRow title="Company / Fund"><Text style={{ fontSize: font.body, color: colors.text, fontWeight: '600' }}>{detail.name}</Text>{detail.description ? <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 20 }}>{detail.description}</Text> : null}<Sources sources={detail.facts.flatMap((fact) => fact.sources).slice(0, 2)} /></SectionRow>
          <SectionRow title="Industry & sectors">{detail.facts.filter((fact) => /sector|industry/i.test(fact.label)).map((fact, index) => <View key={`${fact.label}-${index}`}><Text style={{ fontSize: font.body, color: colors.text }}>{fact.value}</Text><Sources sources={fact.sources} /></View>)}</SectionRow>
          <SectionRow title="Key match factors">{detail.why_match.map((item, index) => <View key={`${item.signal}-${index}`} style={{ gap: space.xs }}><Text style={{ fontSize: font.small, color: colors.text }}>{item.text}</Text><Sources sources={item.sources} /></View>)}</SectionRow>
          <SectionRow title="Fund stage, HQ & ticket">{detail.facts.filter((fact) => /stage|headquarters|ticket|round size/i.test(fact.label)).map((fact, index) => <View key={`${fact.label}-${index}`}><Text style={[{ fontSize: font.small, color: colors.text }, tabularNums]}>{fact.label}: {fact.value}</Text><Sources sources={fact.sources} /></View>)}</SectionRow>
        </View>
        <View style={{ paddingTop: space.lg }}>
          <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>How to get investment</Text>
          <SectionRow title="Previous investments & syndicate leads">
            {detail.rounds.length ? detail.rounds.map((round, index) => { const leads = new Set(round.leads.map((name) => name.toLowerCase())); const coInvestors = round.investors.filter((name) => !leads.has(name.toLowerCase())); return <View key={`${round.round_type}-${round.date}-${index}`} style={{ gap: space.xs, marginBottom: space.md }}>
              <Text style={[{ fontSize: font.body, fontWeight: '600', color: colors.text }, tabularNums]}>{round.round_type || 'Funding round'}{round.amount ? ` · ${round.amount}` : ''}{round.date ? ` · ${round.date}` : ''}</Text>
              {round.leads.length ? <Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>Lead: {round.leads.join(', ')}</Text> : null}
              {coInvestors.length ? <Text style={{ fontSize: font.small, color: colors.textMuted }}>Co-investors: {coInvestors.join(', ')}</Text> : null}<Sources sources={round.sources} />
            </View>; }) : <Text style={{ fontSize: font.small, color: colors.textMuted }}>No sourced funding rounds are available.</Text>}
            {detail.portfolio.map((company) => <View key={company.id} style={{ paddingVertical: space.xs }}><Pressable accessibilityRole="link" onPress={() => router.push(`/entity/${company.id}`)}><Text style={{ fontSize: font.small, color: colors.accent }}>{company.name}</Text></Pressable><Sources sources={detail.rounds.flatMap((round) => round.sources).slice(0, 2)} /></View>)}
          </SectionRow>
          <SectionRow title="Suggested schedule window & deal cadence">
            <Text style={{ fontSize: font.small, color: colors.text, lineHeight: 20 }}>Suggested schedule window: {event?.scheduleWindows[0] ?? 'Day 1 · 10:00–12:00 Investor meetings'}</Text>
            {detail.facts.filter((fact) => /rounds in the last 24 months/i.test(fact.label)).map((fact, index) => <View key={`${fact.label}-${index}`}><Text style={[{ fontSize: font.small, color: colors.text }, tabularNums]}>{fact.label}: {fact.value}</Text><Sources sources={fact.sources} /></View>)}
          </SectionRow>
          <SectionRow title="Key Cala signals & decision-makers to approach">
            {detail.people.map((person) => <View key={person.id}><Text style={{ fontSize: font.small, color: colors.text }}>{person.name} · {person.role}{person.since ? ` · Since ${person.since}` : ''}</Text><Sources sources={detail.why_match.flatMap((item) => item.sources).slice(0, 2)} /></View>)}
            {detail.why_match.map((item, index) => <View key={`signal-${item.signal}-${index}`} style={{ gap: space.xs }}><Text style={{ fontSize: font.small, color: colors.text }}>{item.text}</Text><Sources sources={item.sources} /></View>)}
          </SectionRow>
        </View>
      </> : null}
    </View>
  </ScrollView>;
}
