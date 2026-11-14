import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { maxWidth, useTheme, type Colors } from '../src/theme';
import { Button, StateView } from '../src/ui';

type ChatMessage = Message & {
  pending?: boolean;
  error?: string;
  retryText?: string;
  retryAudio?: Blob | MobileFile;
  retryContext?: { journal_item_id: string };
};

const SUGGESTIONS = [
  "Who led Amenitiz's Series B?",
  'Finnish seed fintech rounds in 2025',
  'Check investors matching B2B SaaS in Nordics',
];

const BACKEND_ERROR = 'Could not reach the backend. Check your connection and try again.';

function formatError(error: unknown, fallback = BACKEND_ERROR): string {
  if (error instanceof ApiError) {
    if (error.status === 503) return 'Voice transcription is unavailable right now.';
    if (error.status >= 500) return 'The server could not complete this request. Try again.';
    if (error.status === 413) return 'Message or audio exceeds the maximum allowed size.';
    if (error.status === 422) return 'Could not process the audio. Try speaking clearly or typing instead.';
    if (error.status === 415) return 'Unsupported audio format.';
    return error.message || fallback;
  }
  if (error instanceof Error) {
    const lower = error.message.toLowerCase();
    if (
      lower.includes('fetch') ||
      lower.includes('network') ||
      lower.includes('connect') ||
      lower.includes('timeout') ||
      lower.includes('abort')
    ) {
      return BACKEND_ERROR;
    }
    return error.message || fallback;
  }
  return fallback;
}

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export default function ChatScreen() {
  const { colors } = useTheme();
  const s = useMemo(() => chatStyles(colors), [colors]);
  const params = useLocalSearchParams<{ journal_item_id?: string; journal_title?: string }>();
  const [attachedContext, setAttachedContext] = useState<{ id: string; title: string } | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState('');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recommendationsReady, setRecommendationsReady] = useState(false);
  const [error, setError] = useState('');
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const listRef = useRef<FlatList<ChatMessage>>(null);
  const startedAt = useRef(0);
  const stoppingRecording = useRef(false);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (params.journal_item_id) {
      setAttachedContext({
        id: params.journal_item_id,
        title: params.journal_title || 'attached item',
      });
    }
  }, [params.journal_item_id, params.journal_title]);

  const loadConversation = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      let id = await getOrCreateSessionId();
      let history: Message[];
      try {
        history = await listMessages(id);
      } catch (e) {
        if (!(e instanceof ApiError && e.status === 404)) throw e;
        id = await resetSessionId();
        history = await listMessages(id);
      }
      if (!mounted.current) return;
      setSessionId(id);
      setMessages(history);
      setRecommendationsReady(
        history.some((message) => message.role === 'assistant' && Boolean(message.cards?.length)),
      );
    } catch (e: unknown) {
      if (!mounted.current) return;
      setLoadError(formatError(e, BACKEND_ERROR));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConversation();
  }, [loadConversation]);

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
        text: text ?? 'Voice message',
        created_at: new Date().toISOString(),
      };
      if (!optimistic) {
        setMessages((current) => [...current, { ...pending, pending: true }]);
      } else {
        setMessages((current) =>
          current.map((item) =>
            item.id === optimistic.id ? { ...item, pending: true, error: undefined } : item,
          ),
        );
      }
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
        const message = formatError(e, BACKEND_ERROR);
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

  async function submitText(override?: string) {
    const text = (override ?? draft).trim();
    if (!text || sending || !sessionId) return;
    if (!override) setDraft('');
    const context = attachedContext ? { journal_item_id: attachedContext.id } : undefined;
    setAttachedContext(null);
    await transmit(text, undefined, undefined, context);
  }

  async function toggleRecording() {
    if (recording) {
      if (stoppingRecording.current) return;
      stoppingRecording.current = true;
      try {
        await recorder.stop();
        setRecording(false);
        const uri = recorder.uri;
        if (!uri) throw new Error('Recording could not be saved.');
        if (Platform.OS === 'web') {
          const blob = await fetch(uri).then((response) => response.blob());
          await transmit(undefined, blob);
        } else {
          await transmit(undefined, { uri, name: 'audio.m4a', mimeType: 'audio/m4a' });
        }
      } catch (e) {
        setRecording(false);
        setError(formatError(e, 'Could not send audio.'));
      } finally {
        stoppingRecording.current = false;
      }
      return;
    }
    if (!sessionId || sending) return;
    setError('');
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setError('Microphone permission is required to record voice messages.');
        return;
      }
      await recorder.prepareToRecordAsync();
      recorder.record();
      startedAt.current = Date.now();
      setRecordingSeconds(0);
      setRecording(true);
    } catch (e) {
      setError(formatError(e, 'Could not start recording.'));
    }
  }

  useEffect(() => {
    if (recording && recordingSeconds >= 120) void toggleRecording();
  }, [recording, recordingSeconds]);

  const renderMessage = ({ item }: { item: ChatMessage }) => {
    const user = item.role === 'user';
    if (user) {
      return (
        <View style={s.userRow}>
          <View style={s.userBubble}>
            {item.transcript ? (
              <>
                <Text style={s.transcriptLabel}>TRANSCRIPT</Text>
                <Text style={s.userText}>{item.transcript}</Text>
              </>
            ) : (
              <Text style={s.userText}>{item.text}</Text>
            )}
            {item.pending ? <Text style={s.pending}>Sending…</Text> : null}
          </View>
          {item.error ? (
            <View style={s.retryRow}>
              <Text accessibilityRole="alert" style={s.errorText}>
                {item.error}
              </Text>
              <Pressable
                accessibilityRole="button"
                onPress={() =>
                  void transmit(item.retryText, item.retryAudio, item, item.retryContext)
                }
              >
                <Text style={s.retry}>Retry</Text>
              </Pressable>
            </View>
          ) : null}
        </View>
      );
    }

    const standaloneSources = item.blocks?.length ? [] : (item.sources ?? []);
    return (
      <View style={s.assistantRow}>
        {item.text ? <Text style={s.assistantText}>{item.text}</Text> : null}
        {standaloneSources.length ? (
          <View style={s.sourceList}>
            <Text style={s.sourceHeading}>SOURCES</Text>
            {standaloneSources.map((source, index) => (
              <Pressable
                key={`${source.url}-${index}`}
                accessibilityRole="link"
                accessibilityLabel={`Source: ${source.name}`}
                onPress={() => {
                  if (source.url) void Linking.openURL(source.url);
                }}
              >
                <Text style={s.sourceLine}>
                  <Text style={s.sourceLink}>{source.name}</Text>
                  {source.url ? <Text style={s.sourceDomain}> · {host(source.url)}</Text> : null}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : null}
        {item.blocks?.map((block, index) => (
          <BlockView key={`${block.type}-${index}`} block={block} />
        ))}
        {item.cards?.map((card, index) => (
          <CardView key={`${card.title}-${index}`} card={card} />
        ))}
      </View>
    );
  };

  const clock = `${String(Math.floor(recordingSeconds / 60)).padStart(2, '0')}:${String(recordingSeconds % 60).padStart(2, '0')}`;
  const canSend = Boolean(draft.trim()) && !sending && Boolean(sessionId);
  const canRecord = Boolean(sessionId) && (!sending || recording);

  return (
    <KeyboardAvoidingView
      style={s.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={s.frame}>
        <View style={s.header}>
          <Text accessibilityRole="header" style={s.title}>
            Ask Cala
          </Text>
          <Text style={s.subtitle}>Every fact and figure is grounded in Cala sources.</Text>
        </View>

        {attachedContext ? (
          <View style={s.contextBar}>
            <Text style={s.contextText} numberOfLines={1}>
              Context: {attachedContext.title}
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Remove context"
              onPress={() => setAttachedContext(null)}
            >
              <Text style={s.contextClear}>Clear</Text>
            </Pressable>
          </View>
        ) : null}

        {loading ? (
          <View style={s.stateWrap}>
            <StateView kind="loading" title="Loading conversation…" />
          </View>
        ) : loadError && !sessionId ? (
          <View style={s.stateWrap}>
            <StateView
              kind="error"
              title="Could not load conversation"
              message={loadError}
              action={
                <Button
                  label="Try again"
                  variant="secondary"
                  onPress={() => void loadConversation()}
                />
              }
            />
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(item) => item.id}
            renderItem={renderMessage}
            contentContainerStyle={[s.messages, !messages.length && s.messagesEmpty]}
            onContentSizeChange={() => {
              if (messages.length) listRef.current?.scrollToEnd({ animated: true });
            }}
            ListEmptyComponent={
              <View style={s.emptyWrap}>
                <Text style={s.emptyTitle}>Ask about investors, rounds, or claims</Text>
                <Text style={s.emptyBody}>
                  Answers pull structured records and citations directly from Cala.
                </Text>
                <View style={s.suggestions}>
                  <Text style={s.suggestionsLabel}>SUGGESTIONS</Text>
                  {SUGGESTIONS.map((prompt) => (
                    <Pressable
                      key={prompt}
                      accessibilityRole="button"
                      disabled={sending || !sessionId}
                      style={({ pressed }) => [
                        s.suggestionRow,
                        pressed && { opacity: 0.75 },
                      ]}
                      onPress={() => void submitText(prompt)}
                    >
                      <Text style={s.suggestionText}>{prompt}</Text>
                      <Text style={s.suggestionAction}>Ask</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            }
            ListFooterComponent={
              sending ? (
                <View style={s.thinkingRow}>
                  <ActivityIndicator size="small" color={colors.textMuted} />
                  <Text style={s.thinkingText}>Checking Cala sources…</Text>
                </View>
              ) : null
            }
          />
        )}

        {recommendationsReady ? (
          <View style={s.notice}>
            <Text style={s.noticeText}>Recommendations updated.</Text>
            <Link href="/perfil" style={s.noticeLink}>
              View profile
            </Link>
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
              <Text style={s.recording}>Recording {clock}</Text>
            ) : (
              <TextInput
                value={draft}
                onChangeText={setDraft}
                placeholder="Ask about investors, rounds, or claims…"
                placeholderTextColor={colors.textFaint}
                multiline
                maxLength={4000}
                editable={Boolean(sessionId) && !loading}
                style={s.input}
                accessibilityLabel="Message"
                onSubmitEditing={() => void submitText()}
                onKeyPress={(event) => {
                  const native = event.nativeEvent as { key?: string; shiftKey?: boolean };
                  if (Platform.OS === 'web' && native.key === 'Enter' && !native.shiftKey) {
                    event.preventDefault();
                    void submitText();
                  }
                }}
              />
            )}
          </View>

          <Pressable
            accessibilityLabel={recording ? 'Stop and send recording' : 'Record voice message'}
            accessibilityRole="button"
            disabled={!canRecord}
            style={[
              s.voiceButton,
              recording && s.recordingButton,
              !canRecord && s.disabled,
            ]}
            onPress={() => void toggleRecording()}
          >
            <Text style={[s.voiceButtonText, recording && s.recordingButtonText]}>
              {recording ? 'Stop' : 'Voice'}
            </Text>
          </Pressable>

          {!recording ? (
            <Pressable
              accessibilityLabel="Send message"
              accessibilityRole="button"
              disabled={!canSend}
              style={[s.sendButton, !canSend && s.disabled]}
              onPress={() => void submitText()}
            >
              <Text style={s.sendButtonText}>Send</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

function chatStyles(c: Colors) {
  return StyleSheet.create({
    container: {
      flex: 1,
      backgroundColor: c.bg,
    },
    frame: {
      flex: 1,
      width: '100%',
      maxWidth,
      alignSelf: 'center',
    },
    header: {
      paddingHorizontal: 20,
      paddingTop: 16,
      paddingBottom: 16,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
      gap: 4,
    },
    title: {
      color: c.text,
      fontSize: 22,
      fontWeight: '700',
    },
    subtitle: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
    },
    contextBar: {
      marginHorizontal: 20,
      marginTop: 8,
      paddingVertical: 8,
      paddingHorizontal: 12,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      backgroundColor: c.surface,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
    },
    contextText: {
      color: c.textMuted,
      fontSize: 13,
      flexShrink: 1,
    },
    contextClear: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    stateWrap: {
      flex: 1,
      paddingHorizontal: 20,
      paddingTop: 24,
    },
    messages: {
      paddingHorizontal: 20,
      paddingVertical: 16,
      flexGrow: 1,
    },
    messagesEmpty: {
      justifyContent: 'flex-end',
    },
    emptyWrap: {
      gap: 16,
      paddingBottom: 8,
    },
    emptyTitle: {
      color: c.text,
      fontSize: 17,
      fontWeight: '600',
    },
    emptyBody: {
      color: c.textMuted,
      fontSize: 14,
      lineHeight: 20,
      marginTop: -8,
    },
    suggestions: {
      gap: 8,
    },
    suggestionsLabel: {
      color: c.textFaint,
      fontSize: 11,
      fontWeight: '600',
      letterSpacing: 0.6,
    },
    suggestionRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 12,
      paddingHorizontal: 16,
      paddingVertical: 12,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      backgroundColor: c.surface,
    },
    suggestionText: {
      color: c.text,
      fontSize: 14,
      lineHeight: 20,
      flex: 1,
    },
    suggestionAction: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    userRow: {
      alignItems: 'flex-end',
      marginBottom: 16,
      gap: 6,
    },
    userBubble: {
      maxWidth: '85%',
      backgroundColor: c.accent,
      borderRadius: 12,
      paddingHorizontal: 16,
      paddingVertical: 12,
    },
    userText: {
      color: c.accentText,
      fontSize: 15,
      lineHeight: 22,
    },
    transcriptLabel: {
      color: c.accentText,
      opacity: 0.85,
      fontSize: 11,
      fontWeight: '600',
      letterSpacing: 0.5,
      marginBottom: 4,
    },
    pending: {
      color: c.accentText,
      opacity: 0.8,
      fontSize: 12,
      marginTop: 6,
    },
    retryRow: {
      maxWidth: '85%',
      alignItems: 'flex-end',
      gap: 4,
    },
    errorText: {
      color: c.danger,
      fontSize: 13,
      lineHeight: 18,
      textAlign: 'right',
    },
    retry: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    assistantRow: {
      width: '100%',
      marginBottom: 24,
      gap: 8,
    },
    assistantText: {
      color: c.text,
      fontSize: 15,
      lineHeight: 22,
    },
    sourceList: {
      gap: 4,
      marginTop: 4,
    },
    sourceHeading: {
      color: c.textFaint,
      fontSize: 11,
      fontWeight: '600',
      letterSpacing: 0.6,
    },
    sourceLine: {
      fontSize: 13,
      lineHeight: 18,
    },
    sourceLink: {
      color: c.accent,
      textDecorationLine: 'underline',
    },
    sourceDomain: {
      color: c.textFaint,
      fontSize: 12,
    },
    thinkingRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      paddingVertical: 8,
    },
    thinkingText: {
      color: c.textMuted,
      fontSize: 13,
    },
    notice: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      backgroundColor: c.surface,
      paddingHorizontal: 20,
      paddingVertical: 10,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    noticeText: {
      color: c.textMuted,
      fontSize: 13,
    },
    noticeLink: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    globalError: {
      color: c.danger,
      fontSize: 13,
      lineHeight: 18,
      paddingHorizontal: 20,
      paddingVertical: 8,
    },
    composer: {
      flexDirection: 'row',
      alignItems: 'flex-end',
      gap: 8,
      paddingHorizontal: 20,
      paddingVertical: 12,
      borderTopWidth: 1,
      borderTopColor: c.border,
      backgroundColor: c.bg,
    },
    inputWrap: {
      flex: 1,
      minHeight: 44,
      maxHeight: 120,
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      backgroundColor: c.surface,
      paddingHorizontal: 12,
    },
    input: {
      color: c.text,
      fontSize: 16,
      lineHeight: 22,
      paddingVertical: 10,
      maxHeight: 100,
    },
    recording: {
      color: c.danger,
      fontSize: 14,
      fontWeight: '600',
      paddingVertical: 10,
      fontVariant: ['tabular-nums'],
    },
    voiceButton: {
      height: 44,
      paddingHorizontal: 14,
      borderRadius: 8,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface,
      alignItems: 'center',
      justifyContent: 'center',
    },
    voiceButtonText: {
      color: c.text,
      fontSize: 14,
      fontWeight: '600',
    },
    recordingButton: {
      borderColor: c.danger,
      backgroundColor: c.surface,
    },
    recordingButtonText: {
      color: c.danger,
    },
    sendButton: {
      height: 44,
      paddingHorizontal: 16,
      borderRadius: 8,
      backgroundColor: c.accent,
      alignItems: 'center',
      justifyContent: 'center',
    },
    sendButtonText: {
      color: c.accentText,
      fontSize: 14,
      fontWeight: '600',
    },
    disabled: {
      opacity: 0.45,
    },
  });
}
