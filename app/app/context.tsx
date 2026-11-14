import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';
import {
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from 'expo-audio';
import { ApiError } from '../src/api';
import {
  addContextNote,
  deleteContextSource,
  getContext,
  UNDERSTOOD_KEYS,
  updateUnderstood,
  uploadContextPdf,
  uploadContextVoice,
  type ContextPayload,
  type ContextSource,
  type UnderstoodKey,
} from '../src/api/context';
import { getOrCreateSessionId, resetSessionId } from '../src/session';
import { maxWidth, useTheme, type Colors } from '../src/theme';

const MAX_PDF_BYTES = 20 * 1024 * 1024;
const MAX_VOICE_SECONDS = 120;
const MAX_NOTE_CHARS = 8000;

const CATEGORY_META: Record<UnderstoodKey, { label: string; placeholder: string }> = {
  sector_focus: { label: 'Sector focus', placeholder: 'e.g. B2B SaaS, Fintech' },
  target_stage: { label: 'Target stage', placeholder: 'e.g. Seed, Series A' },
  target_round_size: { label: 'Target round size', placeholder: 'e.g. €2M - €3M' },
  geography: { label: 'Geography', placeholder: 'e.g. Nordics, UK' },
  seeking: { label: 'Seeking', placeholder: 'e.g. Lead investor' },
};

export default function ContextScreen() {
  const { colors } = useTheme();
  const s = useMemo(() => createStyles(colors), [colors]);

  const [sessionId, setSessionId] = useState('');
  const [data, setData] = useState<ContextPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [actionError, setActionError] = useState('');
  const [actionNotice, setActionNotice] = useState('');

  const [uploadingPdf, setUploadingPdf] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [uploadingVoice, setUploadingVoice] = useState(false);

  const [noteText, setNoteText] = useState('');
  const [savingNote, setSavingNote] = useState(false);

  const [addingCategory, setAddingCategory] = useState<UnderstoodKey | null>(null);
  const [newTagValue, setNewTagValue] = useState('');
  const [savingCategory, setSavingCategory] = useState<UnderstoodKey | null>(null);

  const [deletingSourceId, setDeletingSourceId] = useState<string | null>(null);

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recordingStartedAt = useRef(0);
  const recordingRef = useRef(false);
  const stoppingVoiceRef = useRef(false);
  const pdfInputRef = useRef<HTMLInputElement | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    recordingRef.current = recording;
  }, [recording]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (recordingRef.current) {
        void recorder.stop().catch(() => {});
      }
    };
  }, [recorder]);

  const loadContext = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      let id: string;
      try {
        id = await getOrCreateSessionId();
      } catch (err) {
        if (err instanceof ApiError) throw err;
        id = 'demo-session';
      }

      let payload: ContextPayload;
      try {
        payload = await getContext(id);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) throw err;
        id = await resetSessionId();
        payload = await getContext(id);
      }

      if (!mountedRef.current) return;
      setSessionId(id);
      setData(payload);
    } catch (err) {
      if (!mountedRef.current) return;
      const message =
        err instanceof Error && err.message
          ? err.message
          : 'Could not reach the backend. Check your connection and try again.';
      setLoadError(message);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadContext();
  }, [loadContext]);

  const stopAndUploadVoice = useCallback(async () => {
    if (stoppingVoiceRef.current || !sessionId) return;
    stoppingVoiceRef.current = true;
    const elapsed = Math.max(1, Math.round((Date.now() - recordingStartedAt.current) / 1000));
    setUploadingVoice(true);
    setActionError('');
    setActionNotice('');

    try {
      await recorder.stop();
      if (mountedRef.current) setRecording(false);
      const uri = recorder.uri;
      if (!uri) {
        throw new Error('Could not capture audio. Please try recording again.');
      }

      let payload: ContextPayload;
      if (Platform.OS === 'web') {
        const blob = await fetch(uri).then((res) => res.blob());
        payload = await uploadContextVoice(sessionId, blob, elapsed);
      } else {
        payload = await uploadContextVoice(
          sessionId,
          { uri, name: 'voice-note.m4a', mimeType: 'audio/m4a' },
          elapsed,
        );
      }

      if (!mountedRef.current) return;
      setData(payload);
      setActionNotice('Voice note analyzed and context updated.');
    } catch (err) {
      if (!mountedRef.current) return;
      setRecording(false);
      setActionError(
        err instanceof Error ? err.message : 'Could not analyze voice note. Please try again.',
      );
    } finally {
      stoppingVoiceRef.current = false;
      if (mountedRef.current) setUploadingVoice(false);
    }
  }, [recorder, sessionId]);

  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(() => {
      const secs = Math.floor((Date.now() - recordingStartedAt.current) / 1000);
      setRecordingSeconds(secs);
      if (secs >= MAX_VOICE_SECONDS) {
        void stopAndUploadVoice();
      }
    }, 500);
    return () => clearInterval(timer);
  }, [recording, stopAndUploadVoice]);

  async function handleToggleRecording() {
    if (uploadingVoice || !sessionId) return;
    if (recording) {
      await stopAndUploadVoice();
      return;
    }
    setActionError('');
    setActionNotice('');
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) {
        setActionError('Microphone permission is required to record a voice note.');
        return;
      }
      await recorder.prepareToRecordAsync();
      recorder.record();
      recordingStartedAt.current = Date.now();
      setRecordingSeconds(0);
      setRecording(true);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : 'Could not start recording. Check microphone access.',
      );
    }
  }

  async function submitPdfFile(file: File | { uri: string; name: string; mimeType: string }, size?: number) {
    if (!sessionId || uploadingPdf) return;
    if (size === 0) {
      setActionError('The selected PDF is empty.');
      return;
    }
    if (typeof size === 'number' && size > MAX_PDF_BYTES) {
      setActionError('PDF must be 20 MB or smaller.');
      return;
    }

    setUploadingPdf(true);
    setActionError('');
    setActionNotice('');
    try {
      const payload = await uploadContextPdf(sessionId, file);
      if (!mountedRef.current) return;
      setData(payload);
      setActionNotice('Pitch deck analyzed and context updated.');
    } catch (err) {
      if (!mountedRef.current) return;
      setActionError(
        err instanceof Error ? err.message : 'Could not analyze PDF. Please try another file.',
      );
    } finally {
      if (mountedRef.current) setUploadingPdf(false);
    }
  }

  async function handlePickPdf() {
    if (uploadingPdf || !sessionId) return;
    setActionError('');
    setActionNotice('');

    if (Platform.OS === 'web') {
      pdfInputRef.current?.click();
      return;
    }

    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: 'application/pdf',
        copyToCacheDirectory: true,
      });
      if (result.canceled) return;
      const asset = result.assets[0];
      if (!asset) return;
      const webFile = (asset as DocumentPicker.DocumentPickerAsset & { file?: File }).file;
      if (typeof File !== 'undefined' && webFile instanceof File) {
        await submitPdfFile(webFile, webFile.size);
        return;
      }
      await submitPdfFile(
        {
          uri: asset.uri,
          name: asset.name || 'pitch-deck.pdf',
          mimeType: asset.mimeType || 'application/pdf',
        },
        asset.size,
      );
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not open document picker.');
    }
  }

  function handleWebPdfChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (file.type && file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setActionError('Please choose a PDF file.');
      return;
    }
    void submitPdfFile(file, file.size);
  }

  async function handleSaveNote() {
    const text = noteText.trim();
    if (!text || savingNote || !sessionId) return;
    setSavingNote(true);
    setActionError('');
    setActionNotice('');
    try {
      const payload = await addContextNote(sessionId, text);
      if (!mountedRef.current) return;
      setData(payload);
      setNoteText('');
      setActionNotice('Note saved and context updated.');
    } catch (err) {
      if (!mountedRef.current) return;
      setActionError(err instanceof Error ? err.message : 'Could not save note. Please try again.');
    } finally {
      if (mountedRef.current) setSavingNote(false);
    }
  }

  async function handleRemoveTag(key: UnderstoodKey, tagToRemove: string) {
    if (!sessionId || !data || savingCategory) return;
    const nextList = data.what_we_understood[key].filter((item) => item !== tagToRemove);
    setSavingCategory(key);
    setActionError('');
    setActionNotice('');
    try {
      const payload = await updateUnderstood(sessionId, { [key]: nextList });
      if (!mountedRef.current) return;
      setData(payload);
    } catch (err) {
      if (!mountedRef.current) return;
      setActionError(err instanceof Error ? err.message : 'Could not update tags.');
    } finally {
      if (mountedRef.current) setSavingCategory(null);
    }
  }

  async function handleAddTag(key: UnderstoodKey) {
    const trimmed = newTagValue.trim();
    if (!trimmed || !sessionId || !data || savingCategory) return;
    const current = data.what_we_understood[key];
    const duplicate = current.some((item) => item.toLowerCase() === trimmed.toLowerCase());
    if (duplicate) {
      setAddingCategory(null);
      setNewTagValue('');
      return;
    }

    setSavingCategory(key);
    setActionError('');
    setActionNotice('');
    try {
      const payload = await updateUnderstood(sessionId, { [key]: [...current, trimmed] });
      if (!mountedRef.current) return;
      setData(payload);
      setAddingCategory(null);
      setNewTagValue('');
    } catch (err) {
      if (!mountedRef.current) return;
      setActionError(err instanceof Error ? err.message : 'Could not add tag.');
    } finally {
      if (mountedRef.current) setSavingCategory(null);
    }
  }

  async function handleDeleteSource(sourceId: string) {
    if (!sessionId || deletingSourceId) return;
    setDeletingSourceId(sourceId);
    setActionError('');
    setActionNotice('');
    try {
      const payload = await deleteContextSource(sessionId, sourceId);
      if (!mountedRef.current) return;
      setData(payload);
    } catch (err) {
      if (!mountedRef.current) return;
      setActionError(err instanceof Error ? err.message : 'Could not remove source.');
    } finally {
      if (mountedRef.current) setDeletingSourceId(null);
    }
  }

  const strength = data?.context_strength;
  const understood = data?.what_we_understood;
  const sources = data?.sources ?? [];
  const missingCategories = data ? listMissingSignals(data) : [];
  const isEmpty =
    !!data &&
    sources.length === 0 &&
    UNDERSTOOD_KEYS.every((key) => data.what_we_understood[key].length === 0) &&
    data.context_strength.signals_added === 0;

  return (
    <ScrollView
      style={s.screen}
      contentContainerStyle={s.content}
      keyboardShouldPersistTaps="handled"
    >
      <View style={s.header}>
        <Text accessibilityRole="header" style={s.title}>
          Context
        </Text>
        <Text style={s.subtitle}>
          Add your pitch deck, voice notes, or written context to calibrate your matches.
        </Text>
        {data?.is_demo ? (
          <View style={s.demoRow}>
            <Text style={s.demoNote}>
              Offline demo mode: sample context stored locally in memory.
            </Text>
            <Pressable accessibilityRole="button" onPress={() => void loadContext()}>
              <Text style={s.demoReconnect}>Reconnect</Text>
            </Pressable>
          </View>
        ) : null}
      </View>

      {loading ? <LoadingSkeleton styles={s} /> : null}

      {!loading && loadError ? (
        <View style={s.errorBox} accessibilityRole="alert">
          <Text style={s.errorTitle}>Could not load context</Text>
          <Text style={s.errorMessage}>{loadError}</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => void loadContext()}
            style={s.primaryButton}
          >
            <Text style={s.primaryButtonText}>Retry</Text>
          </Pressable>
        </View>
      ) : null}

      {!loading && !loadError && data && strength && understood ? (
        <>
          <View style={s.section}>
            <View style={s.strengthHeader}>
              <Text style={s.sectionLabel}>Context strength</Text>
              <Text style={s.strengthScore}>{strength.score}%</Text>
            </View>
            <View style={s.progressTrack}>
              <View
                style={[
                  s.progressFill,
                  { width: `${Math.max(0, Math.min(100, strength.score))}%` },
                ]}
              />
            </View>
            <View style={s.strengthMeta}>
              <Text style={s.strengthLabel}>{strength.label}</Text>
              <Text style={s.strengthCount}>
                {strength.signals_added} of {strength.signals_total} signals
              </Text>
            </View>
            {missingCategories.length > 0 ? (
              <Text style={s.missingHint}>Missing: {missingCategories.join(', ')}</Text>
            ) : null}
          </View>

          {isEmpty ? (
            <View style={s.emptyBanner}>
              <Text style={s.emptyTitle}>No context added yet</Text>
              <Text style={s.emptyBody}>
                Upload a pitch deck, record a quick voice note, or write a note below to extract
                your stage, sector, round size, and focus.
              </Text>
            </View>
          ) : null}

          <View style={s.section}>
            <Text style={s.sectionTitle}>Add context</Text>

            {actionError ? (
              <View style={s.inlineError} accessibilityRole="alert">
                <Text style={s.inlineErrorText}>{actionError}</Text>
                <Pressable accessibilityRole="button" onPress={() => setActionError('')}>
                  <Text style={s.inlineDismiss}>Dismiss</Text>
                </Pressable>
              </View>
            ) : null}

            {actionNotice ? <Text style={s.inlineNotice}>{actionNotice}</Text> : null}

            <View style={s.inputRow}>
              <View style={s.inputMeta}>
                <Text style={s.rowTitle}>Upload pitch deck (PDF)</Text>
                <Text style={s.rowSubtitle}>
                  Analyzes up to 15 pages, 20 MB maximum.
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                disabled={uploadingPdf || recording || uploadingVoice}
                onPress={() => void handlePickPdf()}
                style={[
                  s.secondaryButton,
                  (uploadingPdf || recording || uploadingVoice) && s.disabledButton,
                ]}
              >
                <Text style={s.secondaryButtonText}>
                  {uploadingPdf ? 'Analyzing PDF...' : 'Choose PDF'}
                </Text>
              </Pressable>
              {Platform.OS === 'web' ? (
                <input
                  ref={pdfInputRef}
                  type="file"
                  accept="application/pdf"
                  onChange={handleWebPdfChange}
                  style={{ display: 'none' }}
                />
              ) : null}
            </View>

            <View style={[s.inputRow, s.rowDivider]}>
              <View style={s.inputMeta}>
                <Text style={s.rowTitle}>Record voice note</Text>
                {recording ? (
                  <Text style={s.recordingStatus}>
                    Recording... {formatClock(recordingSeconds)} / 02:00
                  </Text>
                ) : uploadingVoice ? (
                  <Text style={s.rowSubtitle}>Transcribing and extracting signals...</Text>
                ) : (
                  <Text style={s.rowSubtitle}>
                    Speak your thesis, round targets, or investor criteria (up to 2 minutes).
                  </Text>
                )}
              </View>
              <Pressable
                accessibilityRole="button"
                disabled={uploadingVoice || uploadingPdf}
                onPress={() => void handleToggleRecording()}
                style={[
                  recording ? s.primaryButton : s.secondaryButton,
                  (uploadingVoice || uploadingPdf) && s.disabledButton,
                ]}
              >
                <Text style={recording ? s.primaryButtonText : s.secondaryButtonText}>
                  {uploadingVoice
                    ? 'Transcribing...'
                    : recording
                      ? 'Stop & save'
                      : 'Record'}
                </Text>
              </Pressable>
            </View>

            <View style={[s.noteBlock, s.rowDivider]}>
              <Text style={s.rowTitle}>Quick note</Text>
              <Text style={s.rowSubtitle}>
                Add round size, investor preferences, traction, or constraints.
              </Text>
              <TextInput
                value={noteText}
                onChangeText={setNoteText}
                placeholder="e.g. Raising €2.5M seed in Q1, seeking a Nordic or European B2B SaaS lead investor..."
                placeholderTextColor={colors.textFaint}
                multiline
                maxLength={MAX_NOTE_CHARS}
                accessibilityLabel="Quick note"
                style={s.noteInput}
              />
              <View style={s.noteFooter}>
                <Text style={s.charCount}>
                  {noteText.length > 0 ? `${noteText.length} / ${MAX_NOTE_CHARS}` : 'Plain text'}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  disabled={!noteText.trim() || savingNote}
                  onPress={() => void handleSaveNote()}
                  style={[
                    s.primaryButton,
                    (!noteText.trim() || savingNote) && s.disabledButton,
                  ]}
                >
                  <Text style={s.primaryButtonText}>
                    {savingNote ? 'Saving...' : 'Save note'}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>

          <View style={s.section}>
            <Text style={s.sectionTitle}>What we understood</Text>
            <Text style={s.sectionSubtitle}>
              Signals extracted for matching. Remove any tag or add your own.
            </Text>

            {UNDERSTOOD_KEYS.map((key, index) => {
              const meta = CATEGORY_META[key];
              const tags = understood[key];
              const isAdding = addingCategory === key;
              const isBusy = savingCategory === key;
              const anySaving = savingCategory !== null;

              return (
                <View key={key} style={[s.categoryRow, index === 0 && s.categoryRowFirst]}>
                  <Text style={s.categoryLabel}>{meta.label}</Text>
                  <View style={s.tagWrap}>
                    {tags.map((tag) => (
                      <View key={tag} style={s.tag}>
                        <Text style={s.tagText}>{tag}</Text>
                        <Pressable
                          accessibilityRole="button"
                          accessibilityLabel={`Remove ${tag} from ${meta.label}`}
                          disabled={anySaving}
                          hitSlop={6}
                          onPress={() => void handleRemoveTag(key, tag)}
                        >
                          <Text style={[s.tagRemove, anySaving && s.disabledText]}>×</Text>
                        </Pressable>
                      </View>
                    ))}
                    {tags.length === 0 && !isAdding ? (
                      <Text style={s.noneText}>None yet</Text>
                    ) : null}
                    {!isAdding ? (
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={`Add tag to ${meta.label}`}
                        disabled={anySaving}
                        onPress={() => {
                          setAddingCategory(key);
                          setNewTagValue('');
                        }}
                        style={[s.addTagTrigger, anySaving && s.disabledButton]}
                      >
                        <Text style={s.addTagTriggerText}>+ Add</Text>
                      </Pressable>
                    ) : null}
                  </View>

                  {isAdding ? (
                    <View style={s.addTagRow}>
                      <TextInput
                        value={newTagValue}
                        onChangeText={setNewTagValue}
                        placeholder={meta.placeholder}
                        placeholderTextColor={colors.textFaint}
                        autoFocus
                        returnKeyType="done"
                        onSubmitEditing={() => void handleAddTag(key)}
                        style={s.addTagInput}
                      />
                      <Pressable
                        accessibilityRole="button"
                        disabled={!newTagValue.trim() || isBusy}
                        onPress={() => void handleAddTag(key)}
                        style={[
                          s.primaryButtonCompact,
                          (!newTagValue.trim() || isBusy) && s.disabledButton,
                        ]}
                      >
                        <Text style={s.primaryButtonText}>{isBusy ? 'Saving...' : 'Add'}</Text>
                      </Pressable>
                      <Pressable
                        accessibilityRole="button"
                        onPress={() => {
                          setAddingCategory(null);
                          setNewTagValue('');
                        }}
                        style={s.cancelLink}
                      >
                        <Text style={s.cancelLinkText}>Cancel</Text>
                      </Pressable>
                    </View>
                  ) : null}
                </View>
              );
            })}
          </View>

          <View style={s.sectionLast}>
            <View style={s.sourcesHeader}>
              <Text style={s.sectionTitle}>Sources</Text>
              <Text style={s.sourcesCount}>
                {sources.length} {sources.length === 1 ? 'item' : 'items'}
              </Text>
            </View>

            {sources.length === 0 ? (
              <View style={s.sourcesEmpty}>
                <Text style={s.rowTitle}>No sources yet</Text>
                <Text style={s.rowSubtitle}>
                  Uploaded decks, voice notes, and quick notes appear here.
                </Text>
              </View>
            ) : (
              sources.map((source) => (
                <SourceRow
                  key={source.id}
                  source={source}
                  removing={deletingSourceId === source.id}
                  onRemove={() => void handleDeleteSource(source.id)}
                  styles={s}
                />
              ))
            )}
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}

type ContextStyles = ReturnType<typeof createStyles>;

function SourceRow({
  source,
  removing,
  onRemove,
  styles: s,
}: {
  source: ContextSource;
  removing: boolean;
  onRemove: () => void;
  styles: ContextStyles;
}) {
  const kindLabel = source.kind === 'pdf' ? 'PDF' : source.kind === 'voice' ? 'Voice' : 'Note';
  const pagesText =
    typeof source.pages === 'number' && source.pages > 0
      ? `${source.pages} ${source.pages === 1 ? 'page' : 'pages'}`
      : '';
  const durationText =
    typeof source.duration_s === 'number' && source.duration_s > 0
      ? formatDuration(source.duration_s)
      : '';
  const dateText = formatDate(source.created_at);
  const subtitleText = source.subtitle && source.subtitle !== source.title ? source.subtitle : '';
  const metaLine = [kindLabel, subtitleText, pagesText, durationText, dateText]
    .filter(Boolean)
    .join(' · ');

  return (
    <View style={s.sourceRow}>
      <View style={s.sourceMain}>
        <Text style={s.sourceTitle}>{source.title}</Text>
        {metaLine ? <Text style={s.sourceMeta}>{metaLine}</Text> : null}
        {source.transcript ? (
          <Text numberOfLines={2} style={s.sourceTranscript}>
            “{source.transcript}”
          </Text>
        ) : null}
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Remove ${source.title}`}
        disabled={removing}
        onPress={onRemove}
        style={s.removeButton}
      >
        <Text style={[s.removeButtonText, removing && s.disabledText]}>
          {removing ? 'Removing...' : 'Remove'}
        </Text>
      </Pressable>
    </View>
  );
}

function LoadingSkeleton({ styles: s }: { styles: ContextStyles }) {
  return (
    <View accessibilityLabel="Loading context" style={s.skeletonWrap}>
      <View style={s.section}>
        <View style={s.skeletonRowBetween}>
          <View style={[s.skeletonBar, { width: 120, height: 14 }]} />
          <View style={[s.skeletonBar, { width: 48, height: 22 }]} />
        </View>
        <View style={[s.skeletonBar, { width: '100%', height: 6, marginTop: 12 }]} />
        <View style={[s.skeletonRowBetween, { marginTop: 10 }]}>
          <View style={[s.skeletonBar, { width: 96, height: 12 }]} />
          <View style={[s.skeletonBar, { width: 80, height: 12 }]} />
        </View>
      </View>

      <View style={s.section}>
        <View style={[s.skeletonBar, { width: 112, height: 18, marginBottom: 16 }]} />
        <View style={[s.skeletonBar, { width: '100%', height: 48, marginBottom: 16 }]} />
        <View style={[s.skeletonBar, { width: '100%', height: 48, marginBottom: 16 }]} />
        <View style={[s.skeletonBar, { width: '100%', height: 80 }]} />
      </View>

      <View style={s.sectionLast}>
        <View style={[s.skeletonBar, { width: 152, height: 18, marginBottom: 16 }]} />
        <View style={[s.skeletonBar, { width: '75%', height: 28, marginBottom: 12 }]} />
        <View style={[s.skeletonBar, { width: '60%', height: 28 }]} />
      </View>
    </View>
  );
}

function listMissingSignals(payload: ContextPayload): string[] {
  const missing: string[] = [];
  for (const key of UNDERSTOOD_KEYS) {
    if (payload.what_we_understood[key].length === 0) {
      missing.push(CATEGORY_META[key].label.toLowerCase());
    }
  }
  if (!payload.profile?.one_liner) {
    missing.push('company summary');
  }
  return missing;
}

function formatClock(totalSeconds: number): string {
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function formatDuration(seconds: number): string {
  const rounded = Math.max(1, Math.round(seconds));
  if (rounded < 60) return `${rounded}s`;
  const mins = Math.floor(rounded / 60);
  const rem = rounded % 60;
  return rem > 0 ? `${mins}m ${rem}s` : `${mins}m`;
}

function formatDate(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function createStyles(c: Colors) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: c.bg,
    },
    content: {
      width: '100%',
      maxWidth,
      alignSelf: 'center',
      paddingHorizontal: 20,
      paddingTop: 16,
      paddingBottom: 48,
    },
    header: {
      paddingBottom: 24,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    title: {
      color: c.text,
      fontSize: 28,
      fontWeight: '700',
      letterSpacing: -0.4,
    },
    subtitle: {
      color: c.textMuted,
      fontSize: 15,
      lineHeight: 22,
      marginTop: 8,
    },
    demoRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: 8,
      marginTop: 8,
    },
    demoNote: {
      color: c.textFaint,
      fontSize: 12,
      lineHeight: 16,
    },
    demoReconnect: {
      color: c.accent,
      fontSize: 12,
      lineHeight: 16,
      fontWeight: '600',
    },
    section: {
      paddingVertical: 24,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    sectionLast: {
      paddingTop: 24,
    },
    sectionLabel: {
      color: c.textMuted,
      fontSize: 13,
      fontWeight: '600',
    },
    sectionTitle: {
      color: c.text,
      fontSize: 18,
      fontWeight: '600',
    },
    sectionSubtitle: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
      marginTop: 4,
      marginBottom: 16,
    },
    strengthHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'baseline',
    },
    strengthScore: {
      color: c.text,
      fontSize: 24,
      fontWeight: '700',
      fontVariant: ['tabular-nums'],
    },
    progressTrack: {
      height: 4,
      backgroundColor: c.surfaceAlt,
      borderRadius: 2,
      overflow: 'hidden',
      marginTop: 12,
    },
    progressFill: {
      height: '100%',
      backgroundColor: c.accent,
      borderRadius: 2,
    },
    strengthMeta: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginTop: 8,
    },
    strengthLabel: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    strengthCount: {
      color: c.textMuted,
      fontSize: 13,
      fontVariant: ['tabular-nums'],
    },
    missingHint: {
      color: c.textFaint,
      fontSize: 12,
      lineHeight: 16,
      marginTop: 8,
    },
    emptyBanner: {
      paddingVertical: 16,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
      gap: 4,
    },
    emptyTitle: {
      color: c.text,
      fontSize: 15,
      fontWeight: '600',
    },
    emptyBody: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 20,
    },
    errorBox: {
      marginTop: 24,
      padding: 16,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      backgroundColor: c.surface,
      alignItems: 'flex-start',
      gap: 8,
    },
    errorTitle: {
      color: c.text,
      fontSize: 16,
      fontWeight: '600',
    },
    errorMessage: {
      color: c.textMuted,
      fontSize: 14,
      lineHeight: 20,
    },
    inlineError: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
      padding: 12,
      marginTop: 12,
      borderWidth: 1,
      borderColor: c.danger,
      borderRadius: 8,
      backgroundColor: c.dangerSoft,
    },
    inlineErrorText: {
      flex: 1,
      color: c.danger,
      fontSize: 13,
      lineHeight: 18,
    },
    inlineDismiss: {
      color: c.danger,
      fontSize: 12,
      fontWeight: '600',
    },
    inlineNotice: {
      color: c.accent,
      fontSize: 13,
      lineHeight: 18,
      marginTop: 12,
    },
    inputRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 16,
      marginTop: 16,
    },
    rowDivider: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingTop: 16,
    },
    inputMeta: {
      flex: 1,
      gap: 4,
    },
    rowTitle: {
      color: c.text,
      fontSize: 15,
      fontWeight: '600',
    },
    rowSubtitle: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
    },
    recordingStatus: {
      color: c.danger,
      fontSize: 13,
      fontWeight: '600',
      fontVariant: ['tabular-nums'],
    },
    noteBlock: {
      marginTop: 16,
      gap: 8,
    },
    noteInput: {
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      backgroundColor: c.surface,
      color: c.text,
      fontSize: 14,
      lineHeight: 20,
      paddingHorizontal: 12,
      paddingVertical: 10,
      minHeight: 80,
      textAlignVertical: 'top',
    },
    noteFooter: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
    },
    charCount: {
      color: c.textFaint,
      fontSize: 12,
      fontVariant: ['tabular-nums'],
    },
    primaryButton: {
      backgroundColor: c.accent,
      borderRadius: 8,
      paddingHorizontal: 16,
      paddingVertical: 10,
      alignItems: 'center',
      justifyContent: 'center',
    },
    primaryButtonCompact: {
      backgroundColor: c.accent,
      borderRadius: 6,
      paddingHorizontal: 12,
      paddingVertical: 8,
      alignItems: 'center',
      justifyContent: 'center',
    },
    primaryButtonText: {
      color: c.accentText,
      fontSize: 13,
      fontWeight: '600',
    },
    secondaryButton: {
      backgroundColor: c.surface,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 8,
      paddingHorizontal: 14,
      paddingVertical: 9,
      alignItems: 'center',
      justifyContent: 'center',
    },
    secondaryButtonText: {
      color: c.text,
      fontSize: 13,
      fontWeight: '600',
    },
    disabledButton: {
      opacity: 0.45,
    },
    disabledText: {
      opacity: 0.45,
    },
    categoryRow: {
      paddingVertical: 16,
      borderTopWidth: 1,
      borderTopColor: c.border,
      gap: 8,
    },
    categoryRowFirst: {
      borderTopWidth: 1,
    },
    categoryLabel: {
      color: c.textMuted,
      fontSize: 12,
      fontWeight: '600',
      letterSpacing: 0.2,
    },
    tagWrap: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      alignItems: 'center',
      gap: 8,
    },
    tag: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surface,
      borderRadius: 6,
      paddingLeft: 10,
      paddingRight: 8,
      paddingVertical: 6,
    },
    tagText: {
      color: c.text,
      fontSize: 13,
    },
    tagRemove: {
      color: c.textMuted,
      fontSize: 15,
      lineHeight: 16,
      fontWeight: '600',
    },
    noneText: {
      color: c.textFaint,
      fontSize: 13,
    },
    addTagTrigger: {
      borderWidth: 1,
      borderColor: c.border,
      borderStyle: 'dashed',
      borderRadius: 6,
      paddingHorizontal: 10,
      paddingVertical: 6,
    },
    addTagTriggerText: {
      color: c.accent,
      fontSize: 13,
      fontWeight: '600',
    },
    addTagRow: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 8,
      marginTop: 4,
    },
    addTagInput: {
      flex: 1,
      borderWidth: 1,
      borderColor: c.accent,
      borderRadius: 6,
      backgroundColor: c.surface,
      color: c.text,
      fontSize: 13,
      paddingHorizontal: 10,
      paddingVertical: 7,
    },
    cancelLink: {
      paddingHorizontal: 8,
      paddingVertical: 8,
    },
    cancelLinkText: {
      color: c.textMuted,
      fontSize: 13,
    },
    sourcesHeader: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      marginBottom: 12,
    },
    sourcesCount: {
      color: c.textMuted,
      fontSize: 13,
      fontVariant: ['tabular-nums'],
    },
    sourcesEmpty: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: 16,
      gap: 4,
    },
    sourceRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: 16,
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: 16,
    },
    sourceMain: {
      flex: 1,
      gap: 4,
    },
    sourceTitle: {
      color: c.text,
      fontSize: 15,
      fontWeight: '600',
    },
    sourceMeta: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
      fontVariant: ['tabular-nums'],
    },
    sourceTranscript: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
      marginTop: 4,
    },
    removeButton: {
      paddingVertical: 4,
      paddingHorizontal: 4,
    },
    removeButtonText: {
      color: c.textMuted,
      fontSize: 13,
      fontWeight: '600',
    },
    skeletonWrap: {
      opacity: 0.75,
    },
    skeletonRowBetween: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
    },
    skeletonBar: {
      backgroundColor: c.surfaceAlt,
      borderRadius: 4,
    },
  });
}
