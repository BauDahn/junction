import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { RecordingPresets, requestRecordingPermissionsAsync, useAudioRecorder } from 'expo-audio';
import Feather from '@expo/vector-icons/Feather';
import { ApiError } from '../api';
import { appendRawContext, getRawContext, putRawContext, transcribePreview } from '../api/auth';
import { getOrCreateSessionId } from '../session';
import { font, radius, space, tabularNums, useTheme } from '../theme';

const MAX_PDF_BYTES = 20 * 1024 * 1024;
type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult?: ((event: any) => void) | null;
  onerror?: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

type Preview = { transcript: string; text: string };
type UploadFile = File | DocumentPicker.DocumentPickerAsset;

export default function RawContextVoiceCard() {
  const { colors } = useTheme();
  const [rawText, setRawText] = useState('');
  const [savedRawText, setSavedRawText] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busy, setBusy] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [speechActive, setSpeechActive] = useState(false);
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recognitionRef = useRef<Recognition | null>(null);
  const recordingStartedAt = useRef(0);
  const recordingActiveRef = useRef(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const dirtyRef = useRef(false);
  const loadedOnceRef = useRef(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setLoadError('');
    try {
      const data = await getRawContext();
      setRawText(data.text);
      setSavedRawText(data.text);
      dirtyRef.current = false;
    } catch (loadFailure) {
      setLoadError(loadFailure instanceof Error ? loadFailure.message : 'Could not load context.');
    } finally {
      loadedOnceRef.current = true;
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useFocusEffect(useCallback(() => {
    if (!dirtyRef.current && loadedOnceRef.current) void load(true);
  }, [load]));

  const stopRecording = useCallback(async () => {
    if (!recordingActiveRef.current) return;
    recordingActiveRef.current = false;
    setRecording(false);
    const elapsed = Math.min(120, Math.max(1, Math.floor((Date.now() - recordingStartedAt.current) / 1000)));
    try { recognitionRef.current?.stop(); } catch { /* Recognition may have stopped already. */ }
    recognitionRef.current = null;
    setSpeechActive(false);
    setBusy('transcribe');
    setError('');
    try {
      await recorder.stop();
      const uri = recorder.uri;
      if (!uri) throw new Error('Could not access the recording.');
      const audio = Platform.OS === 'web'
        ? await fetch(uri).then((response) => response.blob())
        : { uri, name: 'voice-note.m4a', mimeType: 'audio/m4a' };
      setPreview(await transcribePreview(audio, elapsed));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Audio transcription failed. Please try again.');
    } finally {
      setBusy('');
    }
  }, [recorder]);

  useEffect(() => {
    if (!recording) return;
    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - recordingStartedAt.current) / 1000);
      setSeconds(elapsed);
      if (elapsed >= 120) void stopRecording();
    }, 500);
    return () => clearInterval(timer);
  }, [recording, stopRecording]);

  const startRecording = async () => {
    setError('');
    setNotice('');
    setPreview(null);
    setLiveTranscript('');
    setSpeechActive(false);
    try {
      const permission = await requestRecordingPermissionsAsync();
      if (!permission.granted) throw new Error('Microphone permission is required to record.');
      await recorder.prepareToRecordAsync();
      recorder.record();
      recordingStartedAt.current = Date.now();
      recordingActiveRef.current = true;
      setSeconds(0);
      setRecording(true);
      if (Platform.OS !== 'web') return;
      const speechWindow = globalThis as unknown as SpeechWindow;
      const SpeechRecognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
      if (!SpeechRecognition) return;
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.onresult = (event) => {
        let finalText = '';
        let interimText = '';
        for (let index = 0; index < event.results.length; index += 1) {
          const result = event.results[index];
          const transcript = result[0]?.transcript || '';
          if (result.isFinal) finalText += transcript;
          else interimText += transcript;
        }
        setLiveTranscript(`${finalText}${interimText}`.trim());
      };
      recognition.onerror = () => setSpeechActive(false);
      recognitionRef.current = recognition;
      try {
        recognition.start();
        setSpeechActive(true);
      } catch {
        recognitionRef.current = null;
        setSpeechActive(false);
      }
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not start recording.');
      setRecording(false);
    }
  };

  useEffect(() => () => {
    try { recognitionRef.current?.stop(); } catch { /* Recognition may have stopped already. */ }
    if (recordingActiveRef.current) void recorder.stop().catch(() => {});
  }, [recorder]);

  const saveContext = async () => {
    setBusy('save');
    setError('');
    try {
      const result = await putRawContext(rawText);
      setRawText(result.text);
      setSavedRawText(result.text);
      dirtyRef.current = false;
      setNotice('Context saved and profile updated');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not save context.');
    } finally { setBusy(''); }
  };

  const uploadPdf = async (file: UploadFile) => {
    if ((file.size ?? 0) === 0) { setError('The PDF is empty.'); return; }
    if ((file.size ?? 0) > MAX_PDF_BYTES) { setError('PDF must be 20 MB or smaller.'); return; }
    setBusy('pdf');
    setError('');
    setNotice('');
    try {
      const sessionId = await getOrCreateSessionId();
      const form = new FormData();
      if ('uri' in file) form.append('file', { uri: file.uri, name: file.name, type: file.mimeType || 'application/pdf' } as any);
      else form.append('file', file);
      const baseUrl = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
      const response = await fetch(`${baseUrl}/api/sessions/${encodeURIComponent(sessionId)}/context/pdf`, { method: 'POST', body: form });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new ApiError(body?.error?.code || 'upload_error', body?.error?.message || body?.detail || 'Could not analyze this PDF.', response.status);
      }
      await load(true);
      setNotice('Pitch deck analyzed and added to context');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Could not upload the PDF.');
    } finally { setBusy(''); }
  };

  const pickPdf = async () => {
    setError('');
    if (Platform.OS === 'web') { inputRef.current?.click(); return; }
    const result = await DocumentPicker.getDocumentAsync({ type: 'application/pdf', copyToCacheDirectory: true });
    if (!result.canceled && result.assets[0]) await uploadPdf(result.assets[0]);
  };

  const styles = StyleSheet.create({
    container: { gap: space.md, minWidth: 0 },
    skeleton: { height: 100, backgroundColor: colors.surfaceAlt, borderRadius: radius.md },
    errorText: { color: colors.danger, fontSize: font.small },
    textInput: { minHeight: 180, textAlignVertical: 'top', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.md, color: colors.text, backgroundColor: colors.surface, fontSize: font.body, lineHeight: 22 },
    row: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: space.sm },
    actions: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
    button: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: space.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, minHeight: 44 },
    buttonText: { color: colors.text, fontSize: font.small },
    primaryButton: { backgroundColor: colors.accent, borderColor: colors.accent },
    primaryButtonText: { color: colors.accentText, fontWeight: '600' },
    mutedText: { color: colors.textMuted, fontSize: font.small },
    liveBox: { gap: space.xs, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.md, backgroundColor: colors.surfaceAlt },
    previewBox: { gap: space.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: space.md, backgroundColor: colors.surfaceAlt },
    title: { color: colors.text, fontWeight: '600' },
    body: { color: colors.text, lineHeight: 22 },
    heard: { color: colors.textMuted, fontSize: font.small },
    timer: { color: colors.textMuted, fontSize: font.small },
    notice: { color: colors.confirmed, fontSize: font.small },
  });
  const buttonBase = [styles.button];

  return (
    <View style={styles.container}>
      {loading ? <View accessibilityLabel="Loading context" style={styles.skeleton} /> : loadError ? (
        <View style={styles.container}>
          <Text style={styles.errorText}>{loadError}</Text>
          <Pressable accessibilityRole="button" onPress={() => void load()} style={buttonBase}><Text style={styles.buttonText}>Retry</Text></Pressable>
        </View>
      ) : (
        <>
          <TextInput accessibilityLabel="Matching context" multiline maxLength={8000} value={rawText} onChangeText={(text) => { setRawText(text); dirtyRef.current = text !== savedRawText; }} placeholder="Tell us about your startup, goals, and what you are looking for." placeholderTextColor={colors.textFaint} style={styles.textInput} />
          <View style={styles.row}>
            <Text style={[{ color: colors.textFaint, fontSize: font.caption }, tabularNums]}>{rawText.length} / 8000</Text>
            <Pressable accessibilityRole="button" disabled={!!busy || rawText.length > 8000} onPress={() => void saveContext()} style={[styles.button, styles.primaryButton, { opacity: busy || rawText.length > 8000 ? 0.5 : 1 }]}>
              <Text style={styles.primaryButtonText}>{busy === 'save' ? 'Saving...' : 'Save context'}</Text>
            </Pressable>
          </View>
        </>
      )}

      <View style={styles.actions}>
        <Pressable accessibilityRole="button" disabled={!!busy || recording} onPress={() => void pickPdf()} style={[styles.button, { flexGrow: 1 }]}>
          <Feather name="file-text" size={16} color={colors.text} /><Text style={styles.buttonText}>Upload pitch deck (PDF)</Text>
        </Pressable>
        <Pressable accessibilityRole="button" disabled={!!busy} onPress={() => recording ? void stopRecording() : void startRecording()} style={[styles.button, { flexGrow: 1, backgroundColor: recording ? colors.dangerSoft : colors.surface, borderColor: recording ? colors.danger : colors.border }]}>
          <Feather name={recording ? 'square' : 'mic'} size={16} color={recording ? colors.danger : colors.text} /><Text style={[styles.buttonText, recording ? { color: colors.danger } : null]}>{recording ? 'Stop recording' : 'Record voice note'}</Text>
        </Pressable>
      </View>
      {Platform.OS === 'web' ? <input ref={inputRef} type="file" accept="application/pdf" style={{ display: 'none' }} onChange={(event) => { const file = event.target.files?.[0]; if (file) void uploadPdf(file); event.currentTarget.value = ''; }} /> : null}

      {recording ? (
        <>
          {speechActive ? (
            <View style={styles.liveBox}><Text style={styles.title}>Live preview (browser)</Text><Text style={styles.body}>{liveTranscript || 'Listening... speak into your microphone.'}</Text></View>
          ) : <Text style={styles.mutedText}>Recording audio...</Text>}
          <Text style={[styles.timer, tabularNums]}>{String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')} / 02:00</Text>
        </>
      ) : null}
      {busy === 'transcribe' ? <Text style={styles.mutedText}>Transcribing audio...</Text> : null}
      {busy === 'pdf' ? <Text style={styles.mutedText}>Analyzing pitch deck...</Text> : null}
      {preview && !recording ? (
        <View style={styles.previewBox}>
          <Text style={styles.title}>Voice transcription preview</Text>
          <Text style={styles.body}>{preview.text || preview.transcript}</Text>
          {preview.transcript && preview.text && preview.transcript !== preview.text ? <Text style={styles.heard}>Heard: {preview.transcript}</Text> : null}
          <View style={styles.actions}>
            <Pressable accessibilityRole="button" disabled={!!busy} onPress={async () => {
              setBusy('append'); setError('');
              try {
                const saved = await appendRawContext(preview.text || preview.transcript);
                setRawText(saved.text); setSavedRawText(saved.text); dirtyRef.current = false;
                setPreview(null); setNotice('Voice note added to context');
              } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not add voice note.'); }
              finally { setBusy(''); }
            }} style={[styles.button, styles.primaryButton]}><Text style={styles.primaryButtonText}>{busy === 'append' ? 'Adding...' : 'Add to context'}</Text></Pressable>
            <Pressable accessibilityRole="button" disabled={busy === 'append'} onPress={() => setPreview(null)} style={styles.button}><Text style={styles.buttonText}>Discard</Text></Pressable>
          </View>
        </View>
      ) : null}
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}
      {error ? <Text accessibilityRole="alert" style={styles.errorText}>{error}</Text> : null}
    </View>
  );
}
