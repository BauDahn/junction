import { useEffect, useMemo, useState } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, useWindowDimensions, View } from 'react-native';
import { useRouter } from 'expo-router';
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from 'expo-audio';
import { useMode } from '../mode';
import { EVENTS_CATALOG, findEventByQuery } from '../api/events';
import { addContextNote, getContext, type ContextPayload } from '../api/context';
import { sendAudio, sendText, type Message } from '../api';
import { getOrCreateSessionId } from '../session';
import BlockView from './BlockView';
import { font, maxWidth, radius, space, tabBarHeight, useTheme } from '../theme';

type LocalItem = { id: string; kind: 'message' | 'action'; text?: string; message?: Message; eventId?: string; investorId?: string };
const investors = [
  ['eight roads', 'eight-roads-ventures', 'Eight Roads Ventures'],
  ['chalfen', 'chalfen-ventures', 'Chalfen Ventures'],
  ['northzone', 'northzone', 'Northzone'],
  ['point nine', 'point-nine', 'Point Nine'],
  ['lifeline', 'lifeline-ventures', 'Lifeline Ventures'],
];

function Mascot({ accent, ink }: { accent: string; ink: string }) {
  return <View style={{ width: 24, height: 24, alignItems: 'center', justifyContent: 'center' }}>
    <View style={{ position: 'absolute', top: 1, left: 3, width: 0, height: 0, borderLeftWidth: 4, borderRightWidth: 4, borderBottomWidth: 7, borderLeftColor: 'transparent', borderRightColor: 'transparent', borderBottomColor: ink }} />
    <View style={{ position: 'absolute', top: 1, right: 3, width: 0, height: 0, borderLeftWidth: 4, borderRightWidth: 4, borderBottomWidth: 7, borderLeftColor: 'transparent', borderRightColor: 'transparent', borderBottomColor: ink }} />
    <View style={{ width: 20, height: 18, marginTop: 5, borderRadius: radius.md, backgroundColor: ink, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-evenly' }}>
      <View style={{ width: 6, height: 6, borderRadius: radius.pill, backgroundColor: accent }} /><View style={{ width: 6, height: 6, borderRadius: radius.pill, backgroundColor: accent }} />
    </View>
  </View>;
}

export default function FloatingMascotBubble() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const { addMyEvent, addFavoriteInvestor } = useMode();
  const router = useRouter();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const [open, setOpen] = useState(false);
  const [sessionId, setSessionId] = useState('');
  const [context, setContext] = useState<ContextPayload | null>(null);
  const [draft, setDraft] = useState('');
  const [contextNote, setContextNote] = useState('');
  const [items, setItems] = useState<LocalItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const s = useMemo(() => styles(colors), [colors]);
  const refreshContext = async (id: string) => {
    try { setContext(await getContext(id)); } catch { /* Keep the last known context summary. */ }
  };
  useEffect(() => {
    let active = true;
    void getOrCreateSessionId().then((id) => {
      if (!active) return;
      setSessionId(id);
      return refreshContext(id);
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  const action = (text: string, eventId?: string, investorId?: string) => setItems((prev) => [...prev, { id: `${Date.now()}-${prev.length}`, kind: 'action', text, eventId, investorId }]);
  const attend = (id: string) => {
    const event = EVENTS_CATALOG.find((entry) => entry.id === id);
    if (!event) return;
    addMyEvent(id);
    action(`Added ${event.name} to My Events`, id);
  };
  const saveInvestor = (id: string, name: string) => { addFavoriteInvestor(id); action(`Saved ${name}`, undefined, id); };
  const transmit = async (text?: string, audio?: Blob | { uri: string; name: string; mimeType: string }) => {
    if (!sessionId || busy) return;
    const query = text?.trim() ?? '';
    setBusy(true);
    try {
      const response = audio ? await sendAudio(sessionId, audio) : await sendText(sessionId, query);
      setItems((prev) => [...prev, { id: `${Date.now()}`, kind: 'message', message: response.reply }]);
    } catch (error) {
      setItems((prev) => [...prev, { id: `${Date.now()}`, kind: 'action', text: error instanceof Error ? error.message : 'Could not reach Cala. Try again.' }]);
    } finally { setBusy(false); }
  };
  const submit = async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft('');
    const eventIntent = /\b(attend|go to|join|save event|add event|my events)\b/i.test(text);
    const event = eventIntent ? findEventByQuery(text) : undefined;
    let handledShortcut = false;
    if (event) attend(event.id);
    if (event) handledShortcut = true;
    const investorAction = /\b(?:save|bookmark|favorite|favourite)\b/i.test(text);
    if (investorAction) {
      const normalizedText = text.toLowerCase();
      const match = investors.find(([needle, , name]) => normalizedText.includes(needle) || normalizedText.includes(name.toLowerCase()));
      if (match) { saveInvestor(match[1], match[2]); handledShortcut = true; }
    }
    const isContextCommand = /^(context:|we are raising\b)/i.test(text);
    if (isContextCommand) {
      handledShortcut = true;
      try { await addContextNote(sessionId, text); await refreshContext(sessionId); action('Recommender context updated'); }
      catch { action('Could not update context. Try again.'); }
    }
    const isQuestion = text.includes('?') || /^(who|what|where|when|why|how|can|could|should|is|are|does|do|tell me)\b/i.test(text);
    if (!handledShortcut || isQuestion) await transmit(text);
  };
  const startRecording = async () => {
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) { action('Microphone access is needed to record a question.'); return; }
      await recorder.prepareToRecordAsync(); recorder.record(); setRecording(true);
    } catch { action('Could not start recording.'); }
  };
  const stopRecording = async () => {
    try {
      await recorder.stop(); setRecording(false);
      const uri = recorder.uri;
      if (uri && Platform.OS === 'web') {
        const blob = await fetch(uri).then((response) => response.blob());
        await transmit(undefined, blob);
      } else if (uri) {
        await transmit(undefined, { uri, name: 'question.m4a', mimeType: 'audio/m4a' });
      }
    } catch { setRecording(false); action('Could not send the recording.'); }
  };

  return <View pointerEvents="box-none" style={[s.anchor, { marginBottom: insets.bottom }]}>
    {open ? <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={[s.panel, { width: Math.min(380, windowWidth - 32), maxHeight: Math.min(540, windowHeight - 100) }]}>
      <View style={s.header}><Mascot accent={colors.accent} ink={colors.accent} /><View style={s.headerCopy}><Text style={s.title}>Cala assistant</Text><Text style={s.muted}>Verified Cala graph, context & event shortcuts</Text></View><Pressable accessibilityRole="button" onPress={() => setOpen(false)}><Text style={s.link}>Close</Text></Pressable></View>
      <View style={s.context}><Text style={s.contextText}>{[context?.what_we_understood.sector_focus.join(', ') || 'Sector: any', context?.what_we_understood.target_stage.join(', ') || 'Stage: any', context?.what_we_understood.geography.join(', ') || 'Region: any'].join(' · ')}</Text><TextInput value={contextNote} onChangeText={setContextNote} placeholder="Update recommender context" placeholderTextColor={colors.textMuted} style={s.contextInput} onSubmitEditing={async () => { if (!contextNote.trim()) return; try { await addContextNote(sessionId, contextNote); await refreshContext(sessionId); action('Recommender context updated'); setContextNote(''); } catch { action('Could not update context.'); } }} returnKeyType="send" /></View>
      <ScrollView style={s.content} contentContainerStyle={s.contentInner} keyboardShouldPersistTaps="handled">
        {items.map((item) => item.kind === 'action' ? <View key={item.id} style={s.actionRow}><Text style={s.body}>{item.text}</Text>{item.eventId ? <Pressable onPress={() => router.push(`/event/${item.eventId}` as never)}><Text style={s.link}>Open event</Text></Pressable> : null}{item.investorId ? <Pressable onPress={() => router.push(`/entity/${item.investorId}` as never)}><Text style={s.link}>Open dossier</Text></Pressable> : null}</View> : <View key={item.id} style={s.reply}>{item.message?.text ? <Text style={s.body}>{item.message.text}</Text> : null}{item.message?.blocks?.map((block, i) => <BlockView key={`${block.type}-${i}`} block={block} />)}{(item.message?.sources ?? []).map((source, i) => <Pressable key={`${source.url}-${i}`} onPress={() => source.url && void import('react-native').then(({ Linking }) => Linking.openURL(source.url))}><Text style={s.link}>{source.name}</Text></Pressable>)}</View>)}
      </ScrollView>
      <View style={s.composer}><TextInput value={draft} onChangeText={setDraft} placeholder="Ask Cala or update your events" placeholderTextColor={colors.textMuted} style={s.input} multiline blurOnSubmit={false} onSubmitEditing={() => void submit()} onKeyPress={(event) => { const native = event.nativeEvent as { key?: string; shiftKey?: boolean }; if (Platform.OS === 'web' && native.key === 'Enter' && !native.shiftKey) { event.preventDefault(); void submit(); } }} /><Pressable accessibilityRole="button" accessibilityLabel={recording ? 'Stop recording' : 'Record a question'} onPress={() => void (recording ? stopRecording() : startRecording())}><Text style={s.link}>{recording ? 'Stop' : 'Voice'}</Text></Pressable><Pressable accessibilityRole="button" onPress={() => void submit()} disabled={!draft.trim() || busy}><Text style={s.link}>{busy ? 'Sending' : 'Send'}</Text></Pressable></View>
    </KeyboardAvoidingView> : <Pressable accessibilityRole="button" accessibilityLabel="Ask Cala" onPress={() => { setOpen(true); void getOrCreateSessionId().then((id) => { setSessionId(id); return refreshContext(id); }).catch(() => {}); }} style={s.trigger}><Mascot accent={colors.accent} ink={colors.accentText} /></Pressable>}
  </View>;
}

const styles = (c: ReturnType<typeof useTheme>['colors']) => StyleSheet.create({
  anchor: { position: 'absolute', right: 16, bottom: tabBarHeight + 16, // más el safe area (marginBottom)
    zIndex: 100, alignItems: 'flex-end' },
  trigger: { width: 48, height: 48, borderRadius: radius.pill, backgroundColor: c.accent, borderWidth: 1, borderColor: c.border, alignItems: 'center', justifyContent: 'center' },
  panel: { height: 540, backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: radius.lg, overflow: 'hidden' },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md, borderBottomWidth: 1, borderBottomColor: c.border }, headerCopy: { flex: 1 }, title: { fontSize: font.body, fontWeight: '600', color: c.text }, muted: { fontSize: font.caption, color: c.textMuted, marginTop: space.xs },
  context: { padding: space.md, borderBottomWidth: 1, borderBottomColor: c.border }, contextText: { fontSize: font.small, color: c.text }, contextInput: { marginTop: space.sm, fontSize: 16, color: c.text, paddingVertical: space.xs },
  content: { flex: 1 }, contentInner: { padding: space.md, gap: space.md }, chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }, chip: { borderWidth: 1, borderColor: c.border, borderRadius: radius.pill, paddingHorizontal: space.md, paddingVertical: space.sm }, chipText: { fontSize: font.caption, color: c.text }, actionRow: { paddingVertical: space.md, borderBottomWidth: 1, borderBottomColor: c.border, gap: space.sm }, body: { fontSize: font.body, color: c.text, lineHeight: 22 }, reply: { gap: space.sm }, link: { fontSize: font.small, color: c.accent, fontWeight: '600' },
  composer: { flexDirection: 'row', alignItems: 'center', gap: space.sm, padding: space.md, borderTopWidth: 1, borderTopColor: c.border }, input: { flex: 1, maxHeight: 72, fontSize: 16, color: c.text, padding: space.sm },
});
