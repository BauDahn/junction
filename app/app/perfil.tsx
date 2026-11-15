import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import Feather from '@expo/vector-icons/Feather';
import { useRouter } from 'expo-router';
import { getEventById } from '../src/api/events';
import { getEntityDetail } from '../src/api/entities';
import RawContextVoiceCard from '../src/components/RawContextVoiceCard';
import { FavoritesReportButton } from '../src/components/FavoritesReportButton';
import { useMode } from '../src/mode';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../src/theme';
import Logo from '../src/ui/Logo';

export default function PerfilScreen() {
  const { colors, preference, setPreference } = useTheme();
  const router = useRouter();
  const { mode, user, userProfile, completeOnboarding, favoriteInvestorIds, myEventIds, toggleFavoriteInvestor, logout } = useMode();
  const [name, setName] = useState(userProfile.name);
  const [company, setCompany] = useState(userProfile.organization);
  const [saved, setSaved] = useState(false);
  const [resolvedInvestors, setResolvedInvestors] = useState<Record<string, { name: string; subtitle: string }>>({});

  useEffect(() => {
    let active = true;
    void Promise.all(favoriteInvestorIds.map(async (id) => {
      try {
        const detail = await getEntityDetail(id, mode, user?.session_id);
        return detail ? [id, { name: detail.name, subtitle: detail.description || 'Saved investor' }] as const : null;
      } catch { return null; }
    })).then((entries) => {
      if (active) setResolvedInvestors(Object.fromEntries(entries.filter((entry): entry is NonNullable<typeof entry> => entry !== null)));
    });
    return () => { active = false; };
  }, [favoriteInvestorIds, mode, user?.session_id]);

  const investorFallbackName = (id: string) => id.replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

  useEffect(() => {
    setName(userProfile.name || user?.name || '');
    setCompany(userProfile.organization || user?.company || '');
  }, [user?.name, user?.company, userProfile.name, userProfile.organization]);

  const roleLabel = user?.role === 'investor' || mode === 'investing' ? 'Investor' : 'Raiser';
  const styles = StyleSheet.create({
    page: { flex: 1, backgroundColor: colors.bg },
    outer: { alignItems: 'center', paddingHorizontal: pageMargin, paddingBottom: 112 },
    canvas: { width: '100%', maxWidth, gap: space.md }, title: { fontSize: 34, lineHeight: 40, fontWeight: '800', letterSpacing: -1, color: colors.text, marginTop: space.lg, marginBottom: space.xs },
    section: { padding: space.xl, backgroundColor: colors.surface, borderRadius: radius.lg, gap: space.md },
    heading: { fontSize: font.h2, fontWeight: '800', letterSpacing: -0.3, color: colors.text },
    label: { fontSize: font.small, color: colors.textMuted },
    input: { fontSize: 16, color: colors.text, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.md },
    actionRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.sm },
    primaryButton: { minHeight: 44, justifyContent: 'center', backgroundColor: colors.accent, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.md },
    secondaryButton: { minHeight: 44, justifyContent: 'center', backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.md },
    primaryButtonText: { color: colors.accentText, fontWeight: '600' },
    buttonText: { color: colors.text, fontWeight: '600' },
    linkButton: { minHeight: 44, justifyContent: 'center' },
    link: { color: colors.accent, fontSize: font.small, fontWeight: '600' },
    row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space.md, paddingVertical: space.md, borderBottomWidth: 1, borderColor: colors.border },
    rowCopy: { flex: 1, minWidth: 120 },
    rowTitle: { color: colors.text, fontWeight: '600' },
    muted: { color: colors.textMuted, fontSize: font.small, marginTop: space.xs },
    empty: { color: colors.textMuted },
    themeOption: { backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingHorizontal: space.lg, paddingVertical: space.sm + 2 },
    themeOptionActive: { backgroundColor: colors.accent },
    themeText: { fontSize: font.small, fontWeight: '600', color: colors.text },
    themeTextActive: { color: colors.accentText },
    eventDate: { color: colors.textMuted, fontSize: font.small },
  });

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.outer}>
      <View style={styles.canvas}>
        <View style={{ alignItems: 'center', paddingTop: space.lg }}><Logo size={26} /></View>
        <Text accessibilityRole="header" style={styles.title}>Your <Text style={{ color: colors.accent }}>profile</Text>.</Text>
        <View style={styles.section}>
          <Text style={styles.heading}>Account</Text>
          <Text style={styles.label}>Full name</Text>
          <TextInput accessibilityLabel="Full name" value={name} onChangeText={setName} placeholder="Full name" placeholderTextColor={colors.textFaint} style={styles.input} />
          <Text style={styles.label}>Startup or fund name</Text>
          <TextInput accessibilityLabel="Startup or fund name" value={company} onChangeText={setCompany} placeholder="Startup or fund name" placeholderTextColor={colors.textFaint} style={styles.input} />
          <Text style={styles.label}>Email</Text>
          <Text style={{ color: colors.text }}>{user?.email || 'Not signed in'}</Text>
          <View style={styles.actionRow}>
            <Pressable accessibilityRole="button" onPress={() => {
              completeOnboarding({ name: name.trim(), organization: company.trim(), role: mode });
              setSaved(true);
              setTimeout(() => setSaved(false), 2500);
            }} style={styles.primaryButton}><Text style={styles.primaryButtonText}>{saved ? 'Profile saved' : 'Save profile'}</Text></Pressable>
            <Pressable accessibilityRole="button" onPress={async () => { await logout(); router.replace('/onboarding' as never); }} style={styles.secondaryButton}><Text style={styles.buttonText}>Sign out</Text></Pressable>
          </View>
        </View>

        <View style={styles.section}><Text style={styles.heading}>Context</Text><RawContextVoiceCard /></View>
        <View style={styles.section}><Text style={styles.heading}>Appearance</Text><View style={{ flexDirection: 'row', gap: space.sm }}>{([['system', 'System'], ['light', 'Light'], ['dark', 'Dark']] as const).map(([value, label]) => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ selected: preference === value }} onPress={() => setPreference(value)} style={[styles.themeOption, preference === value && styles.themeOptionActive]}><Text style={[styles.themeText, preference === value && styles.themeTextActive]}>{label}</Text></Pressable>)}</View></View>
        <View style={styles.section}>
          <Text style={styles.heading}>{mode === 'investing' ? 'Favorite startups' : 'Favorite investors'}</Text>
          {favoriteInvestorIds.length ? favoriteInvestorIds.map((id) => {
            const investor = resolvedInvestors[id];
            return (
              <View key={id} style={styles.row}>
                <View style={styles.rowCopy}><Text style={styles.rowTitle}>{investor?.name ?? investorFallbackName(id)}</Text><Text style={styles.muted}>{investor?.subtitle ?? 'Saved investor'}</Text></View>
                <Pressable accessibilityRole="button" style={styles.linkButton} onPress={() => router.push({ pathname: '/entity/[id]', params: { id, session_id: user?.session_id ?? '', mode } })}><Text style={styles.link}>Open dossier</Text></Pressable>
                <Pressable accessibilityRole="button" style={styles.linkButton} onPress={() => toggleFavoriteInvestor(id)}><Text style={styles.link}>Remove</Text></Pressable>
              </View>
            );
          }) : <Text style={styles.empty}>{mode === 'investing' ? 'No saved startups yet.' : 'No saved investors yet.'}</Text>}
          <FavoritesReportButton />
          <Text style={[styles.heading, { marginTop: space.lg }]}>My events</Text>
          {myEventIds.length ? myEventIds.map((id) => {
            const event = getEventById(id);
            if (!event) return null;
            return (
              <View key={id} style={styles.row}>
                <View style={styles.rowCopy}><Text style={styles.rowTitle}>{event.name}</Text><Text style={[styles.eventDate, tabularNums]}>{event.date} · {event.city}</Text></View>
                <Pressable accessibilityRole="button" style={styles.linkButton} onPress={() => router.push(`/event/${id}` as never)}><Text style={styles.link}>Open event</Text></Pressable>
              </View>
            );
          }) : <Text style={styles.empty}>No events added yet.</Text>}
        </View>
      </View>
    </ScrollView>
  );
}
