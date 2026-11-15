import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { useMode, type MatchMode } from '../src/mode';
import { font, pageMargin, radius, space, useTheme } from '../src/theme';

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const roles: { value: MatchMode; label: string; description: string }[] = [
  { value: 'raising', label: 'Raiser', description: 'Build investor outreach for your startup.' },
  { value: 'investing', label: 'Investor', description: 'Discover startups and co-investors.' },
];

export default function OnboardingScreen() {
  const { colors } = useTheme();
  const { loginWithCredentials, registerWithCredentials, authLoading } = useMode();
  const router = useRouter();
  const [tab, setTab] = useState<'register' | 'login'>('register');
  const [role, setRole] = useState<MatchMode>('raising');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const styles = StyleSheet.create({
    page: { flexGrow: 1, justifyContent: 'center', alignItems: 'center', padding: pageMargin, backgroundColor: colors.bg },
    panel: { width: '100%', maxWidth: 480, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.lg, padding: space.xl, gap: space.lg },
    headingGroup: { gap: space.sm },
    heading: { fontSize: font.h1, fontWeight: '700', color: colors.text },
    body: { fontSize: font.body, color: colors.textMuted, lineHeight: 22 },
    tabs: { flexDirection: 'row', borderBottomWidth: 1, borderColor: colors.border },
    tab: { flex: 1, minWidth: 0, minHeight: 44, padding: space.md, borderColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
    tabText: { fontWeight: '600' },
    formGroup: { gap: space.md },
    field: { gap: space.xs, minWidth: 0 },
    label: { color: colors.text, fontSize: font.small, fontWeight: '600' },
    input: { minHeight: 44, fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.md, backgroundColor: colors.surface },
    roleGroup: { gap: space.xs },
    roleMeta: { fontSize: font.small, color: colors.textMuted },
    roleOptions: { flexDirection: 'row', gap: space.sm, flexWrap: 'wrap' },
    roleOption: { flex: 1, minWidth: 120, minHeight: 44, padding: space.md, borderWidth: 1, borderRadius: radius.md, gap: space.xs, justifyContent: 'center' },
    roleTitle: { color: colors.text, fontWeight: '600' },
    roleDescription: { color: colors.textMuted, fontSize: font.small, lineHeight: 18 },
    error: { color: colors.danger, fontSize: font.small },
    primaryButton: { minHeight: 44, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent, borderRadius: radius.md, paddingVertical: space.md },
    primaryButtonText: { color: colors.accentText, fontSize: font.body, fontWeight: '600' },
  });

  async function submit() {
    setError('');
    if (!emailRe.test(email.trim())) { setError('Enter a valid email address.'); return; }
    if (tab === 'register' && (!name.trim() || !company.trim())) { setError('Enter your name and startup or fund name.'); return; }
    if (tab === 'register' && password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (tab === 'login' && !password) { setError('Enter your password.'); return; }
    try {
      if (tab === 'register') {
        await registerWithCredentials({ email: email.trim(), password, name: name.trim(), company: company.trim(), role: role === 'investing' ? 'investor' : 'raiser' });
      } else {
        await loginWithCredentials({ email: email.trim(), password });
      }
      router.replace('/feed');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not sign in. Please try again.');
    }
  }

  const field = (label: string, value: string, setValue: (next: string) => void, placeholder: string, extra: Record<string, unknown> = {}) => (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      <TextInput accessibilityLabel={label} value={value} onChangeText={setValue} placeholder={placeholder} placeholderTextColor={colors.textFaint} style={styles.input} {...extra} />
    </View>
  );

  return (
    <ScrollView contentContainerStyle={styles.page} keyboardShouldPersistTaps="handled">
      <View style={styles.panel}>
        <View style={styles.headingGroup}>
          <Text accessibilityRole="header" style={styles.heading}>Welcome to Cala Match</Text>
          <Text style={styles.body}>Create an account or sign in to continue.</Text>
        </View>
        <View style={styles.tabs}>
          {(['register', 'login'] as const).map((value) => (
            <Pressable key={value} accessibilityRole="tab" accessibilityState={{ selected: tab === value }} onPress={() => { setTab(value); setError(''); }} style={[styles.tab, { borderBottomWidth: tab === value ? 2 : 0 }]}>
              <Text style={[styles.tabText, { color: tab === value ? colors.accent : colors.textMuted }]}>{value === 'register' ? 'Create account' : 'Sign in'}</Text>
            </Pressable>
          ))}
        </View>
        {tab === 'register' ? (
          <>
            <View style={styles.roleGroup}>
              <Text style={styles.label}>Your role</Text>
              <Text style={styles.roleMeta}>Your role is permanent for this account.</Text>
              <View style={styles.roleOptions}>
                {roles.map((option) => (
                  <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ selected: role === option.value }} onPress={() => setRole(option.value)} style={[styles.roleOption, { borderColor: role === option.value ? colors.accent : colors.border, backgroundColor: role === option.value ? colors.accentSoft : colors.surface }]}>
                    <Text style={styles.roleTitle}>{option.label}</Text>
                    <Text style={styles.roleDescription}>{option.description}</Text>
                  </Pressable>
                ))}
              </View>
            </View>
            <View style={styles.formGroup}>
              {field('Full name', name, setName, 'Your full name', { autoCapitalize: 'words' })}
              {field('Startup or fund name', company, setCompany, 'Your startup or fund', { autoCapitalize: 'words' })}
            </View>
          </>
        ) : null}
        <View style={styles.formGroup}>
          {field('Email', email, setEmail, 'you@company.com', { keyboardType: 'email-address', autoCapitalize: 'none', autoCorrect: false })}
          {field(tab === 'register' ? 'Password (min. 8 characters)' : 'Password', password, setPassword, tab === 'register' ? 'At least 8 characters' : 'Enter your password', { secureTextEntry: true, autoCapitalize: 'none', onSubmitEditing: () => void submit() })}
        </View>
        {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        <Pressable accessibilityRole="button" disabled={authLoading} onPress={() => void submit()} style={[styles.primaryButton, { opacity: authLoading ? 0.55 : 1 }]}>
          <Text style={styles.primaryButtonText}>{authLoading ? (tab === 'register' ? 'Creating account...' : 'Signing in...') : (tab === 'register' ? 'Create account' : 'Sign in')}</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
