import { useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, Text, TextInput, View } from 'react-native';
import { useRouter } from 'expo-router';
import { EVENTS_CATALOG, type CalaEvent } from '../src/api/events';
import { useMode } from '../src/mode';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../src/theme';

function EventTile({ event, attending, onToggle, onOpen, fullWidth }: { event: CalaEvent; attending: boolean; onToggle: () => void; onOpen: () => void; fullWidth: boolean }) {
  const { colors } = useTheme(); const [imageFailed, setImageFailed] = useState(false);
  return <View style={{ width: fullWidth ? '100%' : '48%', flexGrow: fullWidth ? 0 : 1, maxWidth: fullWidth ? '100%' : '49%', minHeight: 270, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: colors.surface, overflow: 'hidden' }}>
    <View style={{ height: 124, backgroundColor: colors.surfaceAlt, borderBottomWidth: 1, borderBottomColor: colors.border, position: 'relative', overflow: 'hidden' }}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={({ pressed }) => ({ position: 'absolute', inset: 0, opacity: pressed ? 0.9 : 1 })}>
        <View pointerEvents="none" style={{ position: 'absolute', inset: 0, flexDirection: 'row', gap: space.sm, padding: space.md, opacity: 0.55 }}><View style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm }} /><View style={{ flex: 1.5, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm }} /></View>
        {!imageFailed ? <Image source={{ uri: event.imageUrl }} resizeMode="cover" onError={() => setImageFailed(true)} style={{ position: 'absolute', width: '100%', height: '100%' }} /> : null}
      </Pressable>
      <View style={{ position: 'absolute', left: space.xs, bottom: space.xs, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: space.sm, paddingVertical: space.xs }}><Text numberOfLines={1} style={[{ fontSize: font.caption, color: colors.text }, tabularNums]}>{event.date}</Text></View>
      <Pressable accessibilityRole="button" accessibilityLabel={attending ? `Stop attending ${event.name}` : `Attend ${event.name}`} onPress={onToggle} style={({ pressed }) => ({ position: 'absolute', right: space.xs, top: space.xs, backgroundColor: attending ? colors.accent : colors.surface, borderColor: attending ? colors.accent : colors.border, borderWidth: 1, borderRadius: radius.sm, paddingHorizontal: space.sm, paddingVertical: space.xs, opacity: pressed ? 0.8 : 1 })}>
        <Text style={{ fontSize: font.caption, fontWeight: '600', color: attending ? colors.accentText : colors.accent }}>{attending ? 'Attending ✓' : '+ Attend'}</Text>
      </Pressable>
    </View>
    <Pressable accessibilityRole="button" accessibilityLabel={`Open ${event.name}`} onPress={onOpen} style={({ pressed }) => ({ flex: 1, padding: space.sm, justifyContent: 'space-between', gap: space.xs, opacity: pressed ? 0.9 : 1 })}>
      <View><Text numberOfLines={1} style={{ fontSize: font.body, fontWeight: '600', color: colors.text }}>{event.name}</Text><Text style={{ fontSize: font.caption, color: colors.textMuted }}>{event.city}</Text></View>
      <Text numberOfLines={2} style={{ fontSize: font.caption, color: colors.textMuted, lineHeight: 16 }}>{event.slogan}</Text>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: space.xs }}><Text numberOfLines={2} style={[{ flex: 1, fontSize: font.caption, color: colors.accent, fontWeight: '600' }, tabularNums]}>{event.investors.length} matched investors</Text><Text numberOfLines={1} style={{ flexShrink: 0, fontSize: font.caption, color: colors.text, fontWeight: '600' }}>Open event</Text></View>
    </Pressable>
  </View>;
}
export default function EventsScreen() {
  const router = useRouter(); const { colors } = useTheme(); const { myEventIds, toggleMyEvent } = useMode();
  const [showMyEvents, setShowMyEvents] = useState(true); const [query, setQuery] = useState('');
  const myEvents = useMemo(() => EVENTS_CATALOG.filter((event) => myEventIds.includes(event.id)), [myEventIds]);
  const source = showMyEvents ? myEvents : EVENTS_CATALOG;
  const filtered = source.filter((event) => `${event.name} ${event.city} ${event.id}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ alignItems: 'center', paddingBottom: space.xxl }} keyboardShouldPersistTaps="handled">
    <View style={{ width: '100%', maxWidth, backgroundColor: colors.surface, minHeight: '100%' }}>
      <View style={{ paddingHorizontal: pageMargin, paddingTop: space.lg, paddingBottom: space.md, borderBottomWidth: 1, borderBottomColor: colors.border, gap: space.md }}>
        <View accessibilityRole="tablist" style={{ flexDirection: 'row', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.xs, backgroundColor: colors.surfaceAlt }}>
          {[[true, `My events (${myEvents.length})`], [false, `Explore events (${EVENTS_CATALOG.length})`]].map(([my, label]) => <Pressable key={String(my)} accessibilityRole="tab" accessibilityState={{ selected: my === showMyEvents }} onPress={() => setShowMyEvents(my as boolean)} style={{ flex: 1, alignItems: 'center', paddingVertical: space.sm, borderRadius: radius.sm, backgroundColor: my === showMyEvents ? colors.surface : 'transparent' }}><Text style={[{ color: my === showMyEvents ? colors.accent : colors.textMuted, fontSize: font.small, fontWeight: '600' }, tabularNums]}>{label}</Text></Pressable>)}
        </View>
        <TextInput accessibilityLabel="Filter events by name or city" value={query} onChangeText={setQuery} placeholder="Filter events by name or city…" placeholderTextColor={colors.textFaint} style={{ fontSize: 16, color: colors.text, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.sm, backgroundColor: colors.surface }} />
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md, padding: pageMargin }}>
        {filtered.map((event) => <EventTile key={event.id} event={event} attending={myEventIds.includes(event.id)} onToggle={() => toggleMyEvent(event.id)} onOpen={() => router.push({ pathname: '/event/[id]', params: { id: event.id } })} fullWidth={filtered.length === 1} />)}
        {filtered.length === 0 ? <View style={{ width: '100%', paddingVertical: space.xxl, alignItems: 'center' }}><Text style={{ fontSize: font.body, color: colors.textMuted }}>{query ? 'No events match your search.' : 'Your saved events will appear here.'}</Text></View> : null}
      </View>
    </View>
  </ScrollView>;
}
