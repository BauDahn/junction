import { Feather } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View } from 'react-native';
import { ModeProvider, useMode } from '../src/mode';
import { font, tabBarHeight, ThemeProvider, useTheme } from '../src/theme';
import FloatingMascotBubble from '../src/components/FloatingMascotBubble';
import OnboardingScreen from './onboarding';

export default function RootLayout() {
  return <ThemeProvider mode="system"><ModeProvider><ThemedTabs /></ModeProvider></ThemeProvider>;
}

function ThemedTabs() {
  const { colors, mode } = useTheme();
  const { onboarded, hydrated } = useMode();
  if (!hydrated) return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  if (!onboarded) return <><StatusBar style={mode === 'dark' ? 'light' : 'dark'} /><OnboardingScreen /></>;
  return <>
    <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
    <Tabs screenOptions={{ headerStyle: { backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.border, elevation: 0, shadowOpacity: 0 }, headerShadowVisible: false, headerTintColor: colors.text, headerTitleAlign: 'left', headerTitleStyle: { fontSize: font.lead, fontWeight: '600', color: colors.text }, tabBarStyle: { height: tabBarHeight, paddingTop: 6, paddingBottom: 6, backgroundColor: colors.surface, borderTopColor: colors.border, borderTopWidth: 1, elevation: 0, shadowOpacity: 0 }, tabBarActiveTintColor: colors.secondary, tabBarInactiveTintColor: colors.textMuted, tabBarLabelStyle: { fontSize: 11, fontWeight: '600', lineHeight: 14 }, sceneStyle: { backgroundColor: colors.bg } }}>
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
