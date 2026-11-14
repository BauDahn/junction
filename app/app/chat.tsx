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
import { Link, useLocalSearchParams } from 'expo-router';
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
import { font, space, useTheme } from '../src/theme';
import { ScreenHeader, StateView } from '../src/ui';

type ChatMessage = Message & {
  pending?: boolean;
  error?: string;
  retryText?: string;
  retryAudio?: Blob | MobileFile;
  retryContext?: { journal_item_id: string };
};
export default function ChatScreen() {
  const { colors } = useTheme();
  const s = chatStyles(colors);
  const params = useLocalSearchParams<{ journal_item_id?: string; journal_title?: string }>();
  const [journalContext, setJournalContext] = useState<{ id: string; title: string } | null>(null);
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
    if (params.journal_item_id)
      setJournalContext({
        id: params.journal_item_id,
        title: params.journal_title || 'ítem del journal',
      });
  }, [params.journal_item_id, params.journal_title]);

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
    async (
      text?: string,
      audio?: Blob | MobileFile,
      optimistic?: ChatMessage,
      context?: { journal_item_id: string },
    ) => {
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
          : await sendText(sessionId, text ?? '', context);
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
              ? {
                  ...item,
                  pending: false,
                  error: message,
                  retryText: text,
                  retryAudio: audio,
                  retryContext: context,
                }
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
    const context = journalContext ? { journal_item_id: journalContext.id } : undefined;
    setJournalContext(null);
    await transmit(text, undefined, undefined, context);
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
          {(item.blocks?.length ? [] : (item.sources ?? [])).map((source, index) => (
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
              <Pressable
                onPress={() =>
                  void transmit(item.retryText, item.retryAudio, item, item.retryContext)
                }
              >
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
      <View style={{ paddingHorizontal: space.xl, paddingTop: space.lg }}>
        <ScreenHeader title="Chat" subtitle="Habla con Cala sobre tu startup." />
      </View>
      {journalContext ? (
        <View style={s.contextBanner}>
          <Text style={s.contextText}>Preguntando sobre: {journalContext.title}</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Quitar contexto"
            onPress={() => setJournalContext(null)}
          >
            <Text style={s.contextText}>×</Text>
          </Pressable>
        </View>
      ) : null}
      {loading ? (
        <View style={s.center}>
          <StateView kind="loading" title="Cargando conversación…" />
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
              placeholderTextColor={colors.textFaint}
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

function chatStyles(c: import('../src/theme').Colors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: c.bg },
    header: { paddingHorizontal: 22, paddingTop: 18, paddingBottom: 10 },
    eyebrow: { color: c.accent, fontSize: 11, fontWeight: '700', letterSpacing: 1.5 },
    title: { color: c.text, fontSize: 27, fontWeight: '800', marginTop: 5 },
    messages: {
      paddingHorizontal: 16,
      paddingVertical: 14,
      flexGrow: 1,
      justifyContent: 'flex-end',
    },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 10 },
    empty: {
      color: c.textMuted,
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
    userBubble: { backgroundColor: c.accent, borderBottomRightRadius: 5 },
    assistantBubble: { backgroundColor: c.surface, borderBottomLeftRadius: 5 },
    messageText: { color: c.text, fontSize: 15, lineHeight: 22 },
    transcriptLabel: { color: c.accentText, fontSize: 11, fontWeight: '700', marginBottom: 5 },
    source: { color: c.accent, textDecorationLine: 'underline', marginTop: 9 },
    pending: { color: c.accentText, fontSize: 12, marginTop: 7 },
    thinking: { color: c.textMuted, padding: 10 },
    errorText: { color: c.danger, marginTop: 8 },
    retry: {
      color: c.accentText,
      textDecorationLine: 'underline',
      marginTop: 6,
      fontWeight: '700',
    },
    muted: { color: c.textMuted },
    notice: {
      marginHorizontal: 14,
      marginBottom: 8,
      padding: 11,
      borderRadius: 12,
      backgroundColor: c.accentSoft,
    },
    contextBanner: {
      marginHorizontal: 14,
      marginBottom: 6,
      padding: 10,
      borderRadius: 10,
      backgroundColor: c.accentSoft,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    contextText: { color: c.accentText, fontSize: 13, fontWeight: '600' },
    noticeText: { color: c.accentText, textAlign: 'center' },
    noticeLink: { color: c.accent, textDecorationLine: 'underline', fontWeight: '700' },
    globalError: { color: c.danger, paddingHorizontal: 16, paddingBottom: 6 },
    composer: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      gap: 8,
      paddingHorizontal: 12,
      paddingTop: 10,
      paddingBottom: 12,
      borderTopWidth: 1,
      borderTopColor: c.border,
    },
    inputWrap: {
      flex: 1,
      minHeight: 46,
      maxHeight: 120,
      justifyContent: 'center',
      borderRadius: 15,
      backgroundColor: c.surface,
      paddingHorizontal: 13,
    },
    input: { color: c.text, fontSize: 15, paddingVertical: 11, maxHeight: 100 },
    recording: { color: c.danger, fontWeight: '700', paddingVertical: 12 },
    iconButton: {
      width: 46,
      height: 46,
      borderRadius: 15,
      backgroundColor: c.border,
      alignItems: 'center',
      justifyContent: 'center',
    },
    recordingButton: { backgroundColor: c.dangerSoft },
    sendButton: {
      width: 46,
      height: 46,
      borderRadius: 15,
      backgroundColor: c.accent,
      alignItems: 'center',
      justifyContent: 'center',
    },
    disabled: { opacity: 0.45 },
    buttonText: { color: c.accentText, fontSize: 20, fontWeight: '700' },
  });
}
