import { useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { useEffect } from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { EVENTS_CATALOG, buildOutreachBrief, getEventById } from '../../src/api/events';
import { getContext, type ContextPayload } from '../../src/api/context';
import { getOrCreateSessionId } from '../../src/session';
import { useMode } from '../../src/mode';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../../src/theme';

export default function EventWorkspace() {
  const router = useRouter(); const params = useLocalSearchParams<{ id?: string | string[] }>(); const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const event = getEventById(id ?? '') ?? EVENTS_CATALOG[0]; const { colors } = useTheme(); const { userProfile, myEventIds, toggleMyEvent, favoriteInvestorIds, toggleFavoriteInvestor } = useMode();
  const [template, setTemplate] = useState<'cold' | 'followup'>('cold'); const [copied, setCopied] = useState(false);
  const [context, setContext] = useState<ContextPayload | null>(null);
  useEffect(() => {
    let active = true;
    void getOrCreateSessionId().then(getContext).then((value) => { if (active) setContext(value); }).catch(() => {});
    return () => { active = false; };
  }, []);
  const understood = context?.what_we_understood;
  const sector = understood?.sector_focus.join(', ') || 'ClimateTech';
  const stage = understood?.target_stage.join(', ') || 'Seed';
  const roundSize = understood?.target_round_size.join(', ') || '€2.0M–€3.0M';
  const brief = useMemo(() => buildOutreachBrief(event, template, userProfile.organization || 'Nordleaf', sector, stage, roundSize, userProfile.name), [event, template, userProfile, sector, stage, roundSize]);
  const attending = myEventIds.includes(event.id);
  const copy = async () => {
    try {
      const clipboard = (globalThis as unknown as { navigator?: { clipboard?: { writeText?: (text: string) => Promise<void> } } }).navigator?.clipboard;
      if (clipboard?.writeText) { await clipboard.writeText(brief); setCopied(true); setTimeout(() => setCopied(false), 2200); }
    } catch { setCopied(false); }
  };
  const actionStyle = { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm } as const;
  return <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl }}>
    <View style={{ width: '100%', maxWidth, backgroundColor: colors.surface }}>
      <View style={{ padding: pageMargin, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>
        <Pressable accessibilityRole="button" onPress={() => router.canGoBack() ? router.back() : router.replace('/feed')}><Text style={{ color: colors.accent, fontSize: font.small }}>← Back to Events</Text></Pressable>
        <Text accessibilityRole="header" style={{ fontSize: font.h1, fontWeight: '700', color: colors.text }}>{event.name}</Text>
        <Text style={{ fontSize: font.body, color: colors.textMuted }}>{event.slogan}</Text>
        <Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>{event.date} · {event.venue}, {event.city}</Text>
        <Pressable accessibilityRole="button" onPress={() => toggleMyEvent(event.id)} style={[actionStyle, { alignSelf: 'flex-start', borderColor: attending ? colors.accent : colors.border, backgroundColor: attending ? colors.accent : colors.surface }]}><Text style={{ color: attending ? colors.accentText : colors.accent, fontSize: font.small, fontWeight: '600' }}>{attending ? 'Attending ✓' : '+ Save to my events'}</Text></Pressable>
      </View>
      <View style={{ padding: pageMargin, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>
        <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>Startup outreach brief</Text>
        <Text style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>Grounded in your recommender context and Cala verified investor records for this event.</Text>
        <View style={{ flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' }}>
          {([['cold', 'Cold event intro'], ['followup', 'Post-session follow-up']] as const).map(([value, label]) => <Pressable key={value} accessibilityRole="button" accessibilityState={{ selected: template === value }} onPress={() => setTemplate(value)} style={[actionStyle, { backgroundColor: template === value ? colors.accentSoft : colors.surface, borderColor: template === value ? colors.accent : colors.border }]}><Text style={{ fontSize: font.small, color: template === value ? colors.accent : colors.textMuted }}>{label}</Text></Pressable>)}
          <Pressable accessibilityRole="button" onPress={() => void copy()} style={[actionStyle, { backgroundColor: colors.accent, borderColor: colors.accent }]}><Text style={{ fontSize: font.small, color: colors.accentText, fontWeight: '600' }}>{copied ? 'Copied to clipboard ✓' : 'Copy brief'}</Text></Pressable>
        </View>
        <View style={{ borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.lg, backgroundColor: colors.surfaceAlt, gap: space.md }}>
          <Text selectable style={{ fontSize: font.body, color: colors.text, lineHeight: 24 }}>{brief}</Text>
          <Text style={{ fontSize: font.caption, color: colors.textMuted, lineHeight: 17 }}>Cala records referenced: {event.investors[0]?.name} · {event.investors[0]?.notable_round}. Event schedule windows are suggestions, not Cala sourced facts.</Text>
        </View>
      </View>
      <View style={{ paddingTop: pageMargin }}>
        <View style={{ paddingHorizontal: pageMargin, paddingBottom: space.md, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.xs }}><Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '700', color: colors.text }}>Recommended investors at this event</Text><Text style={{ fontSize: font.small, color: colors.textMuted }}>Matches are based on verified Cala investor records.</Text></View>
        {event.investors.map((investor) => {
          const saved = favoriteInvestorIds.includes(investor.id);
          return <Pressable key={investor.id} accessibilityRole="button" onPress={() => router.push(`/entity/${investor.id}?eventId=${event.id}`)} style={({ pressed }) => ({ paddingVertical: space.lg, paddingHorizontal: pageMargin, borderBottomWidth: 1, borderBottomColor: colors.border, backgroundColor: pressed ? colors.surfaceAlt : colors.surface, gap: space.xs })}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: space.md }}><Text style={{ flex: 1, fontSize: font.lead, fontWeight: '600', color: colors.text }}>{investor.name}</Text><Text style={[{ fontSize: font.small, color: colors.accent, fontWeight: '600' }, tabularNums]}>Match {investor.score}</Text></View>
            <Text style={{ fontSize: font.small, color: colors.textMuted }}>{investor.one_liner}</Text><Text style={{ fontSize: font.small, color: colors.text, lineHeight: 20 }}>{investor.why_match}</Text>
            <Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>{investor.notable_round}</Text>
            <Pressable accessibilityRole="button" onPress={(pressEvent) => { pressEvent.stopPropagation(); toggleFavoriteInvestor(investor.id); }} style={{ alignSelf: 'flex-start', paddingVertical: space.xs }}><Text style={{ fontSize: font.small, color: colors.accent, fontWeight: '600' }}>{saved ? '★ Saved' : '☆ Save'}</Text></Pressable>
          </Pressable>;
        })}
      </View>
    </View>
  </ScrollView>;
}
