import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useMode, type MatchMode } from '../src/mode';
import { getEventById } from '../src/api/events';
import { getContext, type ContextPayload } from '../src/api/context';
import { FavoritesReportButton } from '../src/components/FavoritesReportButton';
import { getOrCreateSessionId } from '../src/session';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../src/theme';

const investors = [
  ['eight-roads-ventures', 'Eight Roads Ventures', 'Global venture capital investor'],
  ['chalfen-ventures', 'Chalfen Ventures', 'European software investor'],
  ['northzone', 'Northzone', 'European venture capital firm'],
  ['point-nine', 'Point Nine', 'European early-stage investor'],
  ['lifeline-ventures', 'Lifeline Ventures', 'Nordic early-stage investor'],
];

export default function PerfilScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const { mode, setMode, userProfile, completeOnboarding, resetOnboarding, favoriteInvestorIds, myEventIds, toggleFavoriteInvestor } = useMode();
  const s = useMemo(() => styles(colors), [colors]);
  const [name, setName] = useState(userProfile.name);
  const [organization, setOrganization] = useState(userProfile.organization);
  const [profileSaved, setProfileSaved] = useState(false);
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [loadError, setLoadError] = useState('');
  useEffect(() => { setName(userProfile.name); setOrganization(userProfile.organization); }, [userProfile.name, userProfile.organization]);
  useEffect(() => { let active = true; void getOrCreateSessionId().then(getContext).then((value) => { if (active) setContext(value); }).catch(() => { if (active) setLoadError('Context summary is unavailable. Try again later.'); }); return () => { active = false; }; }, []);
  const saveProfile = () => {
    completeOnboarding({ name: name.trim(), organization: organization.trim(), role: mode });
    setProfileSaved(true);
    setTimeout(() => setProfileSaved(false), 2500);
  };
  const roleOptions: { value: MatchMode; label: string }[] = [{ value: 'raising', label: 'Raiser' }, { value: 'investing', label: 'Investor' }];
  const value = (key: keyof NonNullable<ContextPayload['what_we_understood']>) => context?.what_we_understood[key]?.join(', ') || 'Not set';
  const summaryRows: [string, string, boolean?][] = [
    ['Sector focus', value('sector_focus')], ['Target stage', value('target_stage')], ['Target round size', value('target_round_size'), true], ['Geography', value('geography')], ['Context strength', context ? `${context.context_strength.score}%` : 'Not set', true],
  ];
  return <ScrollView style={s.page} contentContainerStyle={s.outer}>
    <View style={s.canvas}>
      <View style={s.section}><Text style={s.heading}>Personal details</Text><Text style={s.label}>Full name</Text><TextInput value={name} onChangeText={setName} style={s.input} /><Text style={s.label}>Startup or fund name</Text><TextInput value={organization} onChangeText={setOrganization} style={s.input} /><Text style={s.label}>Operating role</Text><View style={s.switch}>{roleOptions.map((option) => <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ selected: mode === option.value }} onPress={() => setMode(option.value)} style={[s.role, mode === option.value && s.roleActive]}><Text style={[s.roleText, mode === option.value && s.roleTextActive]}>{option.label}</Text></Pressable>)}</View><Pressable style={s.button} onPress={saveProfile}><Text style={s.buttonText}>{profileSaved ? 'Profile saved ✓' : 'Save profile'}</Text></Pressable><Pressable onPress={() => { resetOnboarding(); router.replace('/onboarding' as never); }} style={s.secondary}><Text style={s.link}>Re-open onboarding gate</Text></Pressable></View>
      <View style={s.section}><Text style={s.heading}>Favorite investors</Text>{favoriteInvestorIds.length ? favoriteInvestorIds.map((id) => { const investor = investors.find((entry) => entry[0] === id); const label = investor?.[1] ?? id; return <View key={id} style={s.row}><View style={s.rowCopy}><Text style={s.rowTitle}>{label}</Text><Text style={s.muted}>{investor?.[2] ?? 'Saved investor'}</Text></View><Pressable onPress={() => router.push(`/entity/${id}`)}><Text style={s.link}>Open dossier</Text></Pressable><Pressable onPress={() => toggleFavoriteInvestor(id)}><Text style={s.link}>Remove</Text></Pressable></View>; }) : <Text style={s.empty}>No saved investors yet.</Text>}
        <FavoritesReportButton />
        <Text style={[s.heading, s.subheading]}>My events</Text>{myEventIds.length ? myEventIds.map((id) => { const event = getEventById(id); if (!event) return null; return <View key={id} style={s.row}><View style={s.rowCopy}><Text style={s.rowTitle}>{event.name}</Text><Text style={[s.muted, tabularNums]}>{event.date} · {event.city}</Text></View><Pressable onPress={() => router.push(`/event/${id}` as never)}><Text style={s.link}>Open event</Text></Pressable></View>; }) : <Text style={s.empty}>No events added yet.</Text>}
      </View>
      <View style={s.section}><Text style={s.heading}>Recommender context</Text><Text style={s.label}>What we understood</Text>{summaryRows.map(([label, val, numeric]) => <View key={label} style={s.summaryRow}><Text style={s.muted}>{label}</Text><Text style={[s.summaryValue, numeric ? tabularNums : null]}>{val}</Text></View>)}{loadError ? <Text style={s.error}>{loadError}</Text> : null}<Pressable style={s.secondary} onPress={() => router.push('/context')}><Text style={s.link}>Manage full context</Text></Pressable></View>
    </View>
  </ScrollView>;
}

const styles = (c: ReturnType<typeof useTheme>['colors']) => StyleSheet.create({
  page: { flex: 1, backgroundColor: c.surface }, outer: { alignItems: 'center', paddingHorizontal: pageMargin, paddingBottom: space.xxl }, canvas: { width: '100%', maxWidth, backgroundColor: c.surface, borderLeftWidth: 1, borderRightWidth: 1, borderColor: c.border }, section: { padding: space.xl, borderBottomWidth: 1, borderBottomColor: c.border }, heading: { fontSize: font.h2, fontWeight: '600', color: c.text, marginBottom: space.lg }, label: { fontSize: font.small, color: c.textMuted, marginBottom: space.sm, marginTop: space.md }, input: { fontSize: 16, color: c.text, borderBottomWidth: 1, borderBottomColor: c.border, paddingVertical: space.sm }, switch: { flexDirection: 'row', gap: space.sm }, role: { borderWidth: 1, borderColor: c.border, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.sm }, roleActive: { backgroundColor: c.accent, borderColor: c.accent }, roleText: { fontSize: font.small, color: c.text }, roleTextActive: { color: c.accentText }, button: { marginTop: space.lg, alignSelf: 'flex-start', backgroundColor: c.accent, borderRadius: radius.md, paddingHorizontal: space.lg, paddingVertical: space.md }, buttonText: { color: c.accentText, fontSize: font.small, fontWeight: '600' }, secondary: { marginTop: space.md, alignSelf: 'flex-start', paddingVertical: space.sm }, link: { color: c.accent, fontSize: font.small, fontWeight: '600' }, subheading: { marginTop: space.xl, marginBottom: space.sm }, row: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingVertical: space.md, borderBottomWidth: 1, borderBottomColor: c.border }, rowCopy: { flex: 1 }, rowTitle: { fontSize: font.body, color: c.text, fontWeight: '600' }, muted: { fontSize: font.small, color: c.textMuted, marginTop: space.xs }, empty: { fontSize: font.body, color: c.textMuted, paddingVertical: space.md }, summaryRow: { flexDirection: 'row', justifyContent: 'space-between', gap: space.md, paddingVertical: space.md, borderBottomWidth: 1, borderBottomColor: c.border }, summaryValue: { flex: 1, textAlign: 'right', fontSize: font.small, color: c.text }, error: { color: c.textMuted, fontSize: font.small, paddingTop: space.md },
});
