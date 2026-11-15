import { Tabs, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { Platform, Pressable, Text, View } from 'react-native';
import { ModeProvider, useMode } from '../src/mode';
import { font, radius, space, ThemeProvider, useTheme } from '../src/theme';
import OnboardingScreen from './onboarding';
import FloatingMascotBubble from '../src/components/FloatingMascotBubble';

export default function RootLayout() {
  return <ThemeProvider mode="light"><ModeProvider><ThemedTabs /></ModeProvider></ThemeProvider>;
}
function ProfileButton() {
  const router = useRouter(); const { colors } = useTheme();
  const { userProfile } = useMode();
  const initial = (userProfile.name.trim()[0] || 'P').toUpperCase();
  return <Pressable accessibilityRole="button" accessibilityLabel="Open profile" onPress={() => router.push('/perfil')} style={{ width: 34, height: 34, alignItems: 'center', justifyContent: 'center', borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border }}><Text style={{ color: colors.textMuted, fontSize: font.small }}>{initial}</Text></Pressable>;
}
function ThemedTabs() {
  const { colors, mode } = useTheme(); const { onboarded, hydrated } = useMode();
  if (!hydrated) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  if (!onboarded) return <><StatusBar style={mode === 'dark' ? 'light' : 'dark'} /><OnboardingScreen /></>;
  return <>
    <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
    <Tabs screenOptions={{ headerStyle: { backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border, elevation: 0, shadowOpacity: 0 }, headerShadowVisible: false, headerTintColor: colors.text, headerTitleAlign: 'left', headerTitleStyle: { fontSize: font.lead, fontWeight: '600', color: colors.text }, headerRight: () => <View style={{ paddingRight: space.lg }}><ProfileButton /></View>, tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border, borderTopWidth: 1, elevation: 0, shadowOpacity: 0 }, tabBarActiveTintColor: colors.accent, tabBarInactiveTintColor: colors.textMuted, tabBarLabelStyle: { fontSize: font.caption, fontWeight: '600' }, sceneStyle: { backgroundColor: colors.bg } }}>
      <Tabs.Screen name="index" options={{ href: null, headerShown: false }} />
      <Tabs.Screen name="feed" options={{ title: 'Events' }} />
      <Tabs.Screen name="context" options={{ title: 'Context' }} />
      <Tabs.Screen name="chat" options={{ href: null, title: 'Ask' }} />
      <Tabs.Screen name="onboarding" options={{ href: null, headerShown: false }} />
      <Tabs.Screen name="perfil" options={{ href: null, title: 'Profile' }} />
      <Tabs.Screen name="event/[id]" options={{ href: null, title: 'Event details' }} />
      <Tabs.Screen name="entity/[id]" options={{ href: null, title: 'Investor dossier' }} />
    </Tabs>
    <FloatingMascotBubble />
  </>;
}
