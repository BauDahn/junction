import { Tabs } from 'expo-router';

export default function RootLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: '#0b1020' },
        headerTintColor: '#f8fafc',
        tabBarStyle: { backgroundColor: '#11182b', borderTopColor: '#29324b' },
        tabBarActiveTintColor: '#a78bfa',
        tabBarInactiveTintColor: '#9aa6bf',
        sceneStyle: { backgroundColor: '#0b1020' },
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
