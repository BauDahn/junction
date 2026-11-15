import { useEffect, useState } from 'react';
import { Platform, Pressable, ScrollView, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useMode, type MatchMode } from '../src/mode';
import { font, space, useTheme } from '../src/theme';
import Logo from '../src/ui/Logo';

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const roles: { value: MatchMode; label: string; description: string }[] = [
  { value: 'raising', label: 'Raiser', description: 'Build investor outreach for your startup.' },
  { value: 'investing', label: 'Investor', description: 'Discover startups and co-investors.' },
];
const RADIUS = 6;
const TOP_BAR = 56;

export default function OnboardingScreen() {
  const { colors } = useTheme();
  const { loginWithCredentials, registerWithCredentials, authLoading, sessionExpired } = useMode();
  const router = useRouter();
  const params = useLocalSearchParams<{ tab?: string }>();
  const { width } = useWindowDimensions();
  const desktop = width >= 900;
  const [tab, setTab] = useState<'register' | 'login'>(params.tab === 'login' ? 'login' : 'register');
  const [role, setRole] = useState<MatchMode>('raising');
  const [name, setName] = useState('');
  const [company, setCompany] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [focused, setFocused] = useState('');

  useEffect(() => {
    if (sessionExpired) { setTab('login'); setError('Your session expired. Sign in again.'); }
  }, [sessionExpired]);

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

  const switchTab = (next: 'register' | 'login') => { setTab(next); setError(''); };

  const field = (key: string, label: string, value: string, setValue: (next: string) => void, placeholder: string, extra: Record<string, unknown> = {}) => (
    <View style={{ gap: space.xs, minWidth: 0, flex: 1 }}>
      <Text style={{ color: colors.text, fontSize: font.caption, fontWeight: '600' }}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={setValue}
        onFocus={() => setFocused(key)}
        onBlur={() => setFocused((current) => (current === key ? '' : current))}
        placeholder={placeholder}
        placeholderTextColor={colors.textFaint}
        style={[{ minHeight: 44, fontSize: 16, color: colors.text, backgroundColor: colors.surface, borderWidth: 1, borderRadius: RADIUS, paddingHorizontal: space.md, paddingVertical: space.sm, borderColor: focused === key ? colors.accent : colors.border }, Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : null]}
        {...extra}
      />
    </View>
  );

  const pair = (children: React.ReactNode) => <View style={{ flexDirection: desktop ? 'row' : 'column', gap: space.lg }}>{children}</View>;

  const topBar = (
    <View style={{ height: TOP_BAR, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: desktop ? 40 : space.xl, borderBottomWidth: 1, borderColor: colors.border }}>
      <Logo size={22} />
      <View accessibilityRole="tablist" style={{ flexDirection: 'row', alignItems: 'stretch', gap: space.xl, height: '100%' }}>
        {(['register', 'login'] as const).map((value) => (
          <Pressable key={value} accessibilityRole="tab" accessibilityState={{ selected: tab === value }} onPress={() => switchTab(value)} style={{ justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: tab === value ? colors.accent : 'transparent', marginBottom: -1 }}>
            <Text style={{ fontSize: font.small, fontWeight: '600', color: tab === value ? colors.accent : colors.textMuted }}>{value === 'register' ? 'Create account' : 'Sign in'}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );

  const intro = (
    <View style={{ flex: desktop ? 42 : undefined, gap: space.xl, minWidth: 0 }}>
      <View style={{ gap: space.md }}>
        <Text accessibilityRole="header" style={{ fontSize: desktop ? 42 : 32, lineHeight: desktop ? 46 : 36, fontWeight: '800', letterSpacing: desktop ? -1.3 : -0.9, color: colors.text }}>
          Stop networking by luck. Meet who matters.
        </Text>
        <Text style={{ fontSize: font.lead, lineHeight: 24, color: colors.textMuted }}>
          {tab === 'register' ? 'The investors and startups worth your time at the event, with sources.' : 'Welcome back. Pick up where you left off.'}
        </Text>
      </View>
      {tab === 'register' ? (
        <View style={{ gap: space.sm }}>
          <Text style={{ color: colors.text, fontSize: font.caption, fontWeight: '600' }}>Your role</Text>
          <View accessibilityRole="radiogroup" style={{ flexDirection: desktop ? 'column' : 'row', gap: space.sm }}>
            {roles.map((option) => {
              const active = role === option.value;
              return (
                <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ selected: active }} onPress={() => setRole(option.value)} style={{ flex: desktop ? undefined : 1, minWidth: 0, borderWidth: 1, borderRadius: RADIUS, borderColor: active ? colors.accent : colors.border, paddingVertical: space.md, paddingHorizontal: space.lg, gap: 2 }}>
                  <Text style={{ color: active ? colors.accent : colors.text, fontSize: font.body, fontWeight: '700' }}>{option.label}</Text>
                  <Text style={{ color: colors.textMuted, fontSize: font.small, lineHeight: 18 }}>{option.description}</Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={{ color: colors.textMuted, fontSize: font.caption }}>Your role is permanent for this account.</Text>
        </View>
      ) : null}
    </View>
  );

  const form = (
    <View style={{ flex: desktop ? 58 : undefined, gap: space.lg, minWidth: 0 }}>
      {tab === 'register' ? pair(<>
        {field('name', 'Full name', name, setName, 'Your full name', { autoCapitalize: 'words' })}
        {field('company', 'Startup or fund name', company, setCompany, 'Your startup or fund', { autoCapitalize: 'words' })}
      </>) : null}
      {field('email', 'Email', email, setEmail, 'you@company.com', { keyboardType: 'email-address', autoCapitalize: 'none', autoCorrect: false })}
      {field('password', tab === 'register' ? 'Password (min. 8 characters)' : 'Password', password, setPassword, tab === 'register' ? 'At least 8 characters' : 'Enter your password', { secureTextEntry: true, autoCapitalize: 'none', onSubmitEditing: () => void submit() })}
      {error ? <Text accessibilityRole="alert" style={{ color: colors.danger, fontSize: font.small }}>{error}</Text> : null}
      <View style={{ gap: space.md, alignItems: desktop ? 'flex-start' : 'stretch' }}>
        <Pressable accessibilityRole="button" disabled={authLoading} onPress={() => void submit()} style={({ pressed }) => ({ minHeight: 44, minWidth: desktop ? 200 : undefined, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.xl, backgroundColor: colors.accent, borderRadius: RADIUS, opacity: authLoading ? 0.55 : pressed ? 0.9 : 1 })}>
          <Text style={{ color: colors.accentText, fontSize: font.body, fontWeight: '700' }}>{authLoading ? (tab === 'register' ? 'Creating account...' : 'Signing in...') : (tab === 'register' ? 'Create account' : 'Sign in')}</Text>
        </Pressable>
        <Pressable accessibilityRole="link" onPress={() => switchTab(tab === 'register' ? 'login' : 'register')} style={{ minHeight: 32, justifyContent: 'center' }}>
          <Text style={{ color: colors.textMuted, fontSize: font.small }}>
            {tab === 'register' ? 'Already have an account? ' : 'New to calado? '}
            <Text style={{ color: colors.accent, fontWeight: '600' }}>{tab === 'register' ? 'Sign in' : 'Create account'}</Text>
          </Text>
        </Pressable>
      </View>
    </View>
  );

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.surface }} contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
      <View style={[{ flex: 1, backgroundColor: colors.surface }, Platform.OS === 'web' ? ({ minHeight: '100vh' } as object) : null]}>
        {topBar}
        <View style={[{ flex: 1, width: '100%', maxWidth: 1080, alignSelf: 'center', flexDirection: desktop ? 'row' : 'column', alignItems: desktop ? 'center' : 'stretch', gap: desktop ? 72 : space.xxl, paddingHorizontal: desktop ? 40 : space.xl, paddingVertical: desktop ? space.xxl : space.xl }, desktop && Platform.OS === 'web' ? ({ minHeight: `calc(100vh - ${TOP_BAR}px)` } as object) : null]}>
          {intro}
          {form}
        </View>
      </View>
    </ScrollView>
  );
}
