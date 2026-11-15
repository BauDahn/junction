import { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import { EVENTS_CATALOG, type CalaEvent } from '../src/api/events';
import { useMode } from '../src/mode';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../src/theme';
import Logo from '../src/ui/Logo';

function EventTile({ event, attending, onToggle, onOpen, fullWidth }: { event: CalaEvent; attending: boolean; onToggle: () => void; onOpen: () => void; fullWidth: boolean }) {
  const { colors } = useTheme();
  const [imageFailed, setImageFailed] = useState(false);
  const hasData = event.participantData === 'cala';
  return (
    <View style={{ width: fullWidth ? '100%' : '48%', flexGrow: fullWidth ? 0 : 1, maxWidth: fullWidth ? '100%' : '49%', backgroundColor: colors.surface, borderRadius: radius.lg, padding: space.sm, gap: space.md }}>
      <View style={{ height: 150, borderRadius: radius.md + 4, backgroundColor: colors.accentSoft, overflow: 'hidden' }}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={({ pressed }) => ({ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, opacity: pressed ? 0.9 : 1 })}>
          {!imageFailed ? <Image source={{ uri: event.imageUrl }} resizeMode="cover" onError={() => setImageFailed(true)} style={{ position: 'absolute', width: '100%', height: '100%' }} /> : null}
        </Pressable>
        <View pointerEvents="none" style={{ position: 'absolute', left: space.sm, bottom: space.sm, backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs + 1 }}>
          <Text numberOfLines={1} style={[{ fontSize: font.caption, fontWeight: '600', color: colors.text }, tabularNums]}>{event.date}</Text>
        </View>
        <Pressable accessibilityRole="button" accessibilityLabel={attending ? `Stop attending ${event.name}` : `Attend ${event.name}`} onPress={onToggle} style={({ pressed }) => ({ position: 'absolute', right: space.sm, top: space.sm, backgroundColor: attending ? colors.accent : colors.surface, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.xs + 2, flexDirection: 'row', alignItems: 'center', gap: space.xs, opacity: pressed ? 0.85 : 1 })}>
          <Feather name={attending ? 'check' : 'plus'} size={14} color={attending ? colors.accentText : colors.accent} />
          <Text style={{ fontSize: font.caption, fontWeight: '700', color: attending ? colors.accentText : colors.accent }}>{attending ? 'Attending' : 'Attend'}</Text>
        </Pressable>
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={({ pressed }) => ({ flex: 1, paddingHorizontal: space.sm, paddingBottom: space.sm, gap: space.sm, opacity: pressed ? 0.9 : 1 })}>
        <View style={{ gap: 2 }}>
          <Text numberOfLines={1} style={{ fontSize: font.lead, fontWeight: '700', color: colors.text, letterSpacing: -0.2 }}>{event.name}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs }}>
            <Feather name="map-pin" size={12} color={colors.textMuted} />
            <Text style={{ fontSize: font.caption, color: colors.textMuted }}>{event.city}</Text>
          </View>
        </View>
        <Text numberOfLines={2} style={{ fontSize: font.small, color: colors.textMuted, lineHeight: 18 }}>{event.slogan}</Text>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: space.sm, marginTop: 'auto' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.xs, flexShrink: 1 }}>
            <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: hasData ? colors.accent : colors.textFaint }} />
            <Text numberOfLines={2} style={[{ flexShrink: 1, fontSize: font.caption, fontWeight: '600', color: hasData ? colors.accent : colors.textMuted }, tabularNums]}>{hasData ? 'Cala participant data' : 'No participant data yet'}</Text>
          </View>
          <View style={{ width: 30, height: 30, borderRadius: 15, backgroundColor: colors.accentSoft, alignItems: 'center', justifyContent: 'center' }}>
            <Feather name="arrow-right" size={16} color={colors.accent} />
          </View>
        </View>
      </Pressable>
    </View>
  );
}

export function EventsList({ scope }: { scope: 'mine' | 'explore' }) {
  const router = useRouter();
  const { colors } = useTheme();
  const { myEventIds, toggleMyEvent, userProfile } = useMode();
  const [query, setQuery] = useState('');
  const myEvents = useMemo(() => EVENTS_CATALOG.filter((event) => myEventIds.includes(event.id)), [myEventIds]);
  const source = scope === 'mine' ? myEvents : EVENTS_CATALOG;
  const filtered = source.filter((event) => `${event.name} ${event.city} ${event.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  const firstName = userProfile.name.trim().split(/\s+/)[0] || '';
  const subtitle = scope === 'mine' ? 'Open an event to see who is worth meeting there.' : 'Save the events you are attending and calado finds the investors in the room.';
  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl * 2 }} keyboardShouldPersistTaps="handled">
      <View style={{ width: '100%', maxWidth, minHeight: '100%' }}>
        <View style={{ alignItems: 'center', paddingTop: space.xl, paddingBottom: space.sm }}><Logo size={26} /></View>
        <View style={{ paddingHorizontal: pageMargin, paddingTop: space.xl, paddingBottom: space.lg, gap: space.sm }}>
          <Text accessibilityRole="header" style={{ fontSize: 34, lineHeight: 40, fontWeight: '800', letterSpacing: -1, color: colors.text }}>
            {scope === 'mine' ? <>Good to see you{firstName ? ', ' : ''}<Text style={{ color: colors.accent }}>{firstName}</Text>.</> : <>Find your next <Text style={{ color: colors.accent }}>room</Text>.</>}
          </Text>
          <Text style={{ fontSize: font.body, lineHeight: 22, color: colors.textMuted, maxWidth: 440 }}>{subtitle}</Text>
        </View>
        <View style={{ paddingHorizontal: pageMargin, paddingBottom: space.lg }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm, backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: space.lg }}>
            <Feather name="search" size={18} color={colors.textMuted} />
            <TextInput accessibilityLabel="Filter events by name or city" value={query} onChangeText={setQuery} placeholder="Search by name or city" placeholderTextColor={colors.textFaint} style={{ flex: 1, fontSize: 16, color: colors.text, paddingVertical: space.md + 2, outlineStyle: 'none' } as never} />
          </View>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md, paddingHorizontal: pageMargin }}>
          {filtered.map((event) => <EventTile key={event.id} event={event} attending={myEventIds.includes(event.id)} onToggle={() => toggleMyEvent(event.id)} onOpen={() => router.push({ pathname: '/event/[id]', params: { id: event.id } })} fullWidth={filtered.length === 1} />)}
          {filtered.length === 0 ? <View style={{ width: '100%', paddingVertical: space.xxl, alignItems: 'center' }}><Text style={{ fontSize: font.body, color: colors.textMuted }}>{query ? 'No events match your search.' : scope === 'mine' ? 'You are not attending any events yet.' : 'No events are available right now.'}</Text></View> : null}
        </View>
      </View>
    </ScrollView>
  );
}

export default function EventsScreen() {
  return <EventsList scope="mine" />;
}
