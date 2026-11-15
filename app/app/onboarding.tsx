import { useState } from 'react';
import { Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useMode, type MatchMode } from '../src/mode';
import { font, maxWidth, pageMargin, radius, space, useTheme } from '../src/theme';
import Logo from '../src/ui/Logo';

export default function OnboardingScreen() {
  const { colors } = useTheme();
  const { completeOnboarding } = useMode();
  const router = useRouter();
  const [role, setRole] = useState<MatchMode>('raising');
  const [name, setName] = useState('Alex Lindqvist');
  const [organization, setOrganization] = useState('Nordleaf');
  const inputStyle = { fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.md, backgroundColor: colors.surface } as const;
  return (
    <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: pageMargin, backgroundColor: colors.bg }} keyboardShouldPersistTaps="handled">
      <View style={{ width: '100%', maxWidth: 480, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: space.xl, gap: space.lg }}>
        <View style={{ gap: space.sm }}>
          <Logo size={40} />
          <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '600', color: colors.text }}>Meet the right investors at the right event.</Text>
          <Text style={{ fontSize: font.body, color: colors.textMuted, lineHeight: 22 }}>Select how you operate to calibrate your event deal flow and Cala graph.</Text>
        </View>
        <View style={{ gap: space.sm }}>
          <Text style={{ fontSize: font.small, fontWeight: '600', color: colors.text }}>Your role</Text>
          {([
            ['raising', 'Raiser', 'I am raising capital for a startup and preparing investor outreach at events.'],
            ['investing', 'Investor', 'I am scouting verified startups, rounds, and co-investors across events.'],
          ] as [MatchMode, string, string][]).map(([value, label, description]) => {
            const selected = role === value;
            return <Pressable key={value} accessibilityRole="radio" accessibilityState={{ selected }} onPress={() => setRole(value)} style={{ borderWidth: 1, borderColor: selected ? colors.accent : colors.border, backgroundColor: selected ? colors.accentSoft : colors.surface, borderRadius: radius.md, padding: space.md, gap: space.xs }}>
              <Text style={{ color: colors.text, fontSize: font.body, fontWeight: '600' }}>{label}</Text><Text style={{ color: colors.textMuted, fontSize: font.small, lineHeight: 19 }}>{description}</Text>
            </Pressable>;
          })}
        </View>
        <View style={{ gap: space.md }}>
          <View style={{ gap: space.xs }}><Text style={{ color: colors.text, fontSize: font.small, fontWeight: '600' }}>Full name</Text><TextInput accessibilityLabel="Full name" value={name} onChangeText={setName} style={inputStyle} autoCapitalize="words" /></View>
          <View style={{ gap: space.xs }}><Text style={{ color: colors.text, fontSize: font.small, fontWeight: '600' }}>Startup or fund name</Text><TextInput accessibilityLabel="Startup or fund name" value={organization} onChangeText={setOrganization} style={inputStyle} autoCapitalize="words" /></View>
        </View>
        <Pressable accessibilityRole="button" onPress={() => { completeOnboarding({ name: name.trim() || 'Alex Lindqvist', organization: organization.trim() || 'Nordleaf', role }); router.replace('/feed'); }} style={({ pressed }) => ({ alignItems: 'center', backgroundColor: colors.accent, borderRadius: radius.md, paddingVertical: space.md, opacity: pressed ? 0.8 : 1 })}>
          <Text style={{ color: colors.accentText, fontSize: font.body, fontWeight: '600' }}>Continue to events</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
