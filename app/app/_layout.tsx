import { Feather } from '@expo/vector-icons';
import { Tabs, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { useEffect } from 'react';
import { ModeProvider, useMode } from '../src/mode';
import { font, tabBarHeight, ThemeProvider, useTheme } from '../src/theme';
import FloatingMascotBubble from '../src/components/FloatingMascotBubble';
import OnboardingScreen from './onboarding';
import Logo from '../src/ui/Logo';

export default function RootLayout() {
  return <ThemeProvider><ModeProvider><ThemedTabs /></ModeProvider></ThemeProvider>;
}

function ThemedTabs() {
  const { colors, mode } = useTheme();
  const { onboarded, hydrated, sessionExpired } = useMode();
  const router = useRouter();
  useEffect(() => {
    if (sessionExpired) router.replace({ pathname: '/onboarding', params: { tab: 'login' } });
  }, [router, sessionExpired]);
  if (!hydrated) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  if (!onboarded) return <><StatusBar style={mode === 'dark' ? 'light' : 'dark'} /><OnboardingScreen /></>;
  return <>
    <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
    <Tabs screenOptions={{ headerShown: false, tabBarStyle: { height: tabBarHeight, paddingTop: 6, paddingBottom: 6, backgroundColor: colors.surface, borderTopWidth: 0, elevation: 0, shadowOpacity: 0 }, tabBarActiveTintColor: colors.secondary, tabBarInactiveTintColor: colors.textMuted, tabBarLabelStyle: { fontSize: 11, fontWeight: '600', lineHeight: 14 }, sceneStyle: { backgroundColor: colors.bg } }}>
      <Tabs.Screen name="index" options={{ href: null, headerShown: false }} />
      <Tabs.Screen name="feed" options={{ title: 'My events', tabBarLabel: 'My events', tabBarIcon: ({ color, size }) => <Feather name="calendar" color={color} size={size} /> }} />
      <Tabs.Screen name="explore" options={{ title: 'Explore events', tabBarLabel: 'Explore events', tabBarIcon: ({ color, size }) => <Feather name="compass" color={color} size={size} /> }} />
      <Tabs.Screen name="context" options={{ href: null, title: 'Context' }} />
      <Tabs.Screen name="chat" options={{ href: null, title: 'Ask' }} />
      <Tabs.Screen name="onboarding" options={{ href: null, headerShown: false }} />
      <Tabs.Screen name="perfil" options={{ title: 'Profile', tabBarLabel: 'Profile', tabBarIcon: ({ color, size }) => <Feather name="user" color={color} size={size} /> }} />
      <Tabs.Screen name="event/[id]" options={{ href: null, title: 'Event details' }} />
      <Tabs.Screen name="entity/[id]" options={{ href: null, title: 'Investor dossier' }} />
    </Tabs>
    <FloatingMascotBubble />
  </>;
}
