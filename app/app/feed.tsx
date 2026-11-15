import { useMemo, useState } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { EVENTS_CATALOG, type CalaEvent } from '../src/api/events';
import { useMode } from '../src/mode';
import { font, space, tabularNums, useTheme } from '../src/theme';
import { ActionButton, Card, CardGrid, Input, Page, PageHeader, useDesktop } from '../src/ui/Shell';

function EventCard({ event, attending, onToggle, onOpen }: { event: CalaEvent; attending: boolean; onToggle: () => void; onOpen: () => void }) {
  const { colors } = useTheme();
  const [imageFailed, setImageFailed] = useState(false);
  const hasData = event.participantData === 'cala';
  return (
    <Card style={{ flex: 1 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={({ pressed }) => ({ height: 160, backgroundColor: colors.accentSoft, opacity: pressed ? 0.92 : 1 })}>
        {!imageFailed ? <Image source={{ uri: event.imageUrl }} resizeMode="cover" onError={() => setImageFailed(true)} style={{ position: 'absolute', width: '100%', height: '100%' }} /> : null}
      </Pressable>
      <View style={{ padding: space.xl, gap: space.md, flex: 1 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={{ gap: space.xs }}>
          <Text numberOfLines={1} style={{ fontSize: font.h2, fontWeight: '800', letterSpacing: -0.3, color: colors.text }}>{event.name}</Text>
          <Text style={[{ fontSize: font.small, color: colors.textMuted }, tabularNums]}>{event.date} · {event.city}</Text>
        </Pressable>
        <Text numberOfLines={2} style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 19 }}>{event.slogan}</Text>
        <Text style={{ fontSize: font.caption, fontWeight: '600', color: hasData ? colors.accent : colors.textMuted }}>{hasData ? 'Cala participant data' : 'No participant data yet'}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.md, marginTop: 'auto' }}>
          <ActionButton label={attending ? 'Attending ✓' : '+ Attend'} onPress={onToggle} selected={attending} primary={attending} />
          <Pressable accessibilityRole="link" onPress={onOpen} style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs, minHeight: 40 }}>
            <Text style={{ fontSize: font.small, fontWeight: '700', color: colors.text }}>Open event</Text>
            <Feather name="arrow-right" size={14} color={colors.text} />
          </Pressable>
        </View>
      </View>
    </Card>
  );
}

export function EventsList({ scope }: { scope: 'mine' | 'explore' }) {
  const router = useRouter();
  const { colors } = useTheme();
  const desktop = useDesktop();
  const { myEventIds, toggleMyEvent, userProfile } = useMode();
  const [query, setQuery] = useState('');
  const myEvents = useMemo(() => EVENTS_CATALOG.filter((event) => myEventIds.includes(event.id)), [myEventIds]);
  const source = scope === 'mine' ? myEvents : EVENTS_CATALOG;
  const filtered = source.filter((event) => `${event.name} ${event.city} ${event.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  const firstName = userProfile.name.trim().split(/\s+/)[0] || '';
  return (
    <Page>
      <PageHeader
        title={scope === 'mine' ? 'Good to see you,' : 'Find your next'}
        accent={scope === 'mine' ? firstName || undefined : 'room'}
        subtitle={scope === 'mine' ? 'Open an event to see who is worth meeting there.' : 'Save the events you are attending and calado finds the investors in the room.'}
      />
      <View style={{ maxWidth: 440, marginBottom: space.xl }}>
        <Input accessibilityLabel="Filter events by name or city" value={query} onChangeText={setQuery} placeholder="Search by name or city" />
      </View>
      {filtered.length ? (
        <CardGrid columns={desktop ? 3 : 1}>
          {filtered.map((event) => (
            <EventCard key={event.id} event={event} attending={myEventIds.includes(event.id)} onToggle={() => toggleMyEvent(event.id)} onOpen={() => router.push({ pathname: '/event/[id]', params: { id: event.id } })} />
          ))}
        </CardGrid>
      ) : (
        <Text style={{ fontSize: font.body, color: colors.textMuted }}>{query ? 'No events match your search.' : scope === 'mine' ? 'You are not attending any events yet.' : 'No events are available right now.'}</Text>
      )}
    </Page>
  );
}

export default function EventsScreen() {
  return <EventsList scope="mine" />;
}
