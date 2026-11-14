import { Tabs } from 'expo-router';
import { ThemeProvider, useTheme } from '../src/theme';

export default function RootLayout() {
  return (
    <ThemeProvider mode="system">
      <ThemedTabs />
    </ThemeProvider>
  );
}

function ThemedTabs() {
  const { colors } = useTheme();
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Tabs.Screen name="index" options={{ href: null }} />
      <Tabs.Screen name="chat" options={{ title: 'Chat' }} />
      <Tabs.Screen name="journal" options={{ title: 'Journal' }} />
      <Tabs.Screen name="perfil" options={{ title: 'Perfil' }} />
      <Tabs.Screen name="deck" options={{ title: 'Deck', headerShown: false }} />
      <Tabs.Screen name="estado" options={{ title: 'Estado' }} />
    </Tabs>
  );
}
