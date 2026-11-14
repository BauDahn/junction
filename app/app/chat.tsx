import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Linking,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Link } from 'expo-router';
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from 'expo-audio';
import { getOrCreateSessionId, resetSessionId } from '../src/session';
import {
  ApiError,
  listMessages,
  sendAudio,
  sendText,
  type Message,
  type MobileFile,
} from '../src/api';
import CardView from '../src/components/CardView';
import BlockView from '../src/components/BlockView';

type ChatMessage = Message & {
  pending?: boolean;
  error?: string;
  retryText?: string;
  retryAudio?: Blob | MobileFile;
};
export default function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recommendationsReady, setRecommendationsReady] = useState(false);
  const [error, setError] = useState('');
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const startedAt = useRef(0);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      let id = await getOrCreateSessionId();
      let history: Message[];
      try {
        history = await listMessages(id);
      } catch (e) {
        // El backend guarda las sesiones en memoria: si se reinició, la guardada ya no existe.
        if (!(e instanceof ApiError && e.status === 404)) throw e;
        id = await resetSessionId();
        history = await listMessages(id);
      }
      return { id, history };
    };
    load()
      .then(({ id, history }) => {
        if (!alive) return;
        setSessionId(id);
        setMessages(history);
        setRecommendationsReady(
          history.some((message) => message.role === 'assistant' && message.cards?.length),
        );
      })
      .catch(
        (e: unknown) =>
          alive && setError(e instanceof Error ? e.message : 'No se pudo cargar el chat.'),
      )
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(
      () => setRecordingSeconds(Math.floor((Date.now() - startedAt.current) / 1000)),
      500,
    );
    return () => clearInterval(timer);
  }, [recording]);

  const transmit = useCallback(
    async (text?: string, audio?: Blob | MobileFile, optimistic?: ChatMessage) => {
      if (!sessionId || sending) return;
      setSending(true);
      setError('');
      const pending: ChatMessage = optimistic ?? {
        id: `pending-${Date.now()}`,
        role: 'user',
        text: text ?? 'Mensaje de voz',
        created_at: new Date().toISOString(),
      };
      if (!optimistic) setMessages((current) => [...current, { ...pending, pending: true }]);
      else
        setMessages((current) =>
          current.map((item) =>
            item.id === optimistic.id ? { ...item, pending: true, error: undefined } : item,
          ),
        );
      try {
        const result = audio
          ? await sendAudio(sessionId, audio)
          : await sendText(sessionId, text ?? '');
        setMessages((current) => [
          ...current.filter((item) => item.id !== pending.id),
          result.message,
          result.reply,
        ]);
        setRecommendationsReady(result.recommendations_status === 'ready');
      } catch (e) {
        const message = e instanceof Error ? e.message : 'No se pudo enviar. Inténtalo de nuevo.';
        setMessages((current) =>
          current.map((item) =>
            item.id === pending.id
              ? { ...item, pending: false, error: message, retryText: text, retryAudio: audio }
              : item,
          ),
        );
      } finally {
        setSending(false);
      }
    },
    [sessionId, sending],
  );

  async function submitText() {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft('');
    await transmit(text);
  }

  async function toggleRecording() {
    if (recording) {
      try {
        await recorder.stop();
        setRecording(false);
        const uri = recorder.uri;
        if (!uri) throw new Error('No se pudo guardar la grabación.');
        if (Platform.OS === 'web') {
          const blob = await fetch(uri).then((response) => response.blob());
          await transmit(undefined, blob);
        } else {
          await transmit(undefined, { uri, name: 'audio.m4a', mimeType: 'audio/m4a' });
        }
      } catch (e) {
        setRecording(false);
        setError(e instanceof Error ? e.message : 'No se pudo enviar el audio.');
      }
      return;
    }
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setError('Necesitamos permiso para usar el micrófono.');
        return;
      }
      await recorder.prepareToRecordAsync();
      recorder.record();
      startedAt.current = Date.now();
      setRecordingSeconds(0);
      setRecording(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar la grabación.');
    }
  }

  useEffect(() => {
    if (recording && recordingSeconds >= 120) void toggleRecording();
  }, [recording, recordingSeconds]);

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const user = item.role === 'user';
    return (
      <View style={[s.row, user ? s.userRow : s.assistantRow]}>
        <View style={[s.bubble, user ? s.userBubble : s.assistantBubble]}>
          {item.transcript ? (
            <>
              <Text style={s.transcriptLabel}>Transcripción</Text>
              <Text style={s.messageText}>{item.transcript}</Text>
            </>
          ) : (
            <Text style={s.messageText}>{item.text}</Text>
          )}
          {item.sources?.map((source, index) => (
            <Pressable
              key={`${source.url}-${index}`}
              accessibilityRole="link"
              onPress={() => Linking.openURL(source.url)}
            >
              <Text style={s.source}>↗ {source.name}</Text>
            </Pressable>
          ))}
          {item.role === 'assistant'
            ? item.blocks?.map((block, index) => (
                <BlockView key={`${block.type}-${index}`} block={block} />
              ))
            : null}
          {item.cards?.map((card, index) => (
            <CardView key={`${card.title}-${index}`} card={card} />
          ))}
          {item.pending ? <Text style={s.pending}>Enviando…</Text> : null}
          {item.error ? (
            <View>
              <Text accessibilityRole="alert" style={s.errorText}>
                {item.error}
              </Text>
              <Pressable onPress={() => void transmit(item.retryText, item.retryAudio, item)}>
                <Text style={s.retry}>Reintentar</Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      </View>
    );
  };

  const clock = `${String(Math.floor(recordingSeconds / 60)).padStart(2, '0')}:${String(recordingSeconds % 60).padStart(2, '0')}`;
  return (
    <KeyboardAvoidingView
      style={s.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={s.header}>
        <Text style={s.eyebrow}>JUNCTION · STARTUP INTELLIGENCE</Text>
        <Text style={s.title}>Chat</Text>
      </View>
      {loading ? (
        <View style={s.center}>
          <ActivityIndicator color="#a78bfa" />
          <Text style={s.muted}>Cargando conversación…</Text>
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(item) => item.id}
          renderItem={renderMessage}
          contentContainerStyle={s.messages}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
          ListEmptyComponent={
            <Text style={s.empty}>
              Cuéntame sobre tu startup y te ayudaré a encontrar oportunidades.
            </Text>
          }
          ListFooterComponent={sending ? <Text style={s.thinking}>Pensando…</Text> : null}
        />
      )}
      {recommendationsReady ? (
        <View style={s.notice}>
          <Text style={s.noticeText}>
            Tus recomendaciones están listas.{' '}
            <Link href="/perfil" style={s.noticeLink}>
              Ver perfil
            </Link>
          </Text>
        </View>
      ) : null}
      {error ? (
        <Text accessibilityRole="alert" style={s.globalError}>
          {error}
        </Text>
      ) : null}
      <View style={s.composer}>
        <View style={s.inputWrap}>
          {recording ? (
            <Text style={s.recording}>Grabando… {clock}</Text>
          ) : (
            <TextInput
              value={draft}
              onChangeText={setDraft}
              placeholder="Escribe un mensaje…"
              placeholderTextColor="#77839c"
              multiline
              maxLength={4000}
              style={s.input}
              accessibilityLabel="Mensaje"
              onSubmitEditing={() => void submitText()}
            />
          )}
        </View>
        <Pressable
          accessibilityLabel={recording ? 'Detener y enviar audio' : 'Grabar audio'}
          accessibilityRole="button"
          style={[s.iconButton, recording && s.recordingButton]}
          onPress={() => void toggleRecording()}
        >
          <Text style={s.buttonText}>{recording ? '■' : '🎙'}</Text>
        </Pressable>
        {!recording ? (
          <Pressable
            accessibilityLabel="Enviar mensaje"
            accessibilityRole="button"
            disabled={!draft.trim() || sending}
            style={[s.sendButton, (!draft.trim() || sending) && s.disabled]}
            onPress={() => void submitText()}
          >
            <Text style={s.buttonText}>↑</Text>
          </Pressable>
        ) : null}
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b1020' },
  header: { paddingHorizontal: 22, paddingTop: 18, paddingBottom: 10 },
  eyebrow: { color: '#a78bfa', fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
  title: { color: '#f8fafc', fontSize: 27, fontWeight: '800', marginTop: 5 },
  messages: { paddingHorizontal: 16, paddingVertical: 14, flexGrow: 1, justifyContent: 'flex-end' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
  empty: {
    color: '#9aa6bf',
    textAlign: 'center',
    maxWidth: 300,
    alignSelf: 'center',
    marginBottom: 32,
    lineHeight: 22,
  },
  row: { width: '100%', marginVertical: 5 },
  userRow: { alignItems: 'flex-end' },
  assistantRow: { alignItems: 'flex-start' },
  bubble: { maxWidth: '88%', borderRadius: 18, padding: 13 },
  userBubble: { backgroundColor: '#8b5cf6', borderBottomRightRadius: 5 },
  assistantBubble: { backgroundColor: '#151c30', borderBottomLeftRadius: 5 },
  messageText: { color: '#f8fafc', fontSize: 15, lineHeight: 22 },
  transcriptLabel: { color: '#ddd6fe', fontSize: 11, fontWeight: '700', marginBottom: 5 },
  source: { color: '#c4b5fd', textDecorationLine: 'underline', marginTop: 9 },
  pending: { color: '#ede9fe', fontSize: 12, marginTop: 7 },
  thinking: { color: '#9aa6bf', padding: 10 },
  errorText: { color: '#fecaca', marginTop: 8 },
  retry: { color: '#ddd6fe', textDecorationLine: 'underline', marginTop: 6, fontWeight: '700' },
  muted: { color: '#9aa6bf' },
  notice: {
    marginHorizontal: 14,
    marginBottom: 8,
    padding: 11,
    borderRadius: 12,
    backgroundColor: '#1e1b3a',
  },
  noticeText: { color: '#ddd6fe', textAlign: 'center' },
  noticeLink: { color: '#c4b5fd', textDecorationLine: 'underline', fontWeight: '700' },
  globalError: { color: '#fecaca', paddingHorizontal: 16, paddingBottom: 6 },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    paddingTop: 10,
    paddingBottom: 12,
    borderTopWidth: 1,
    borderTopColor: '#29324b',
  },
  inputWrap: {
    flex: 1,
    minHeight: 46,
    maxHeight: 120,
    justifyContent: 'center',
    borderRadius: 15,
    backgroundColor: '#151c30',
    paddingHorizontal: 13,
  },
  input: { color: '#f8fafc', fontSize: 15, paddingVertical: 11, maxHeight: 100 },
  recording: { color: '#fecaca', fontWeight: '700', paddingVertical: 12 },
  iconButton: {
    width: 46,
    height: 46,
    borderRadius: 15,
    backgroundColor: '#29324b',
    alignItems: 'center',
    justifyContent: 'center',
  },
  recordingButton: { backgroundColor: '#7f1d1d' },
  sendButton: {
    width: 46,
    height: 46,
    borderRadius: 15,
    backgroundColor: '#8b5cf6',
    alignItems: 'center',
    justifyContent: 'center',
  },
  disabled: { opacity: 0.45 },
  buttonText: { color: 'white', fontSize: 20, fontWeight: '700' },
});
