import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { getJob, verifyDeck, verifySample, type Claim, type JobStatus } from '../src/api';
import { verdictLabels } from '../src/verdict';
import { dark, useTheme } from '../src/theme';
import { Badge, Button, Card, Screen, ScreenHeader, StateView, VerdictBadge } from '../src/ui';

const stages: Record<JobStatus['status'], string> = {
  queued: 'En cola',
  extracting: 'Extrayendo afirmaciones',
  checking: 'Consultando Cala',
  judging: 'Evaluando',
  done: 'Verificación lista',
  error: 'Error',
};
const labels: Record<Claim['verdict'], string> = {
  ...verdictLabels,
  not_checked: 'No verificada',
  error: 'Error',
};

export default function DeckScreen() {
  const { colors: theme } = useTheme();
  const s = deckStyles(theme);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<Claim['verdict'] | 'all'>('all');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mounted = useRef(true);
  useEffect(
    () => () => {
      mounted.current = false;
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );
  const poll = (id: string) => {
    timer.current = setTimeout(async () => {
      try {
        const next = await getJob(id);
        if (!mounted.current) return;
        setJob(next);
        if (next.status === 'done' || next.status === 'error') setBusy(false);
        else poll(id);
      } catch (e) {
        if (mounted.current) {
          setError(e instanceof Error ? e.message : 'No se pudo consultar el progreso.');
          setBusy(false);
        }
      }
    }, 2000);
  };
  const begin = async (create: () => Promise<{ job_id: string }>) => {
    setBusy(true);
    setError('');
    setJob(null);
    try {
      const { job_id } = await create();
      const initial = await getJob(job_id);
      if (!mounted.current) return;
      setJob(initial);
      if (initial.status === 'done' || initial.status === 'error') setBusy(false);
      else poll(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo iniciar la verificación.');
      setBusy(false);
    }
  };
  const choose = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: 'application/pdf',
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    if (!asset) return;
    const file = PlatformWebFile(asset) ?? {
      uri: asset.uri,
      name: asset.name,
      mimeType: asset.mimeType || 'application/pdf',
    };
    await begin(() => verifyDeck(file));
  };
  const report = job?.report;
  const visibleClaims =
    report?.claims.filter((c) => filter === 'all' || c.verdict === filter) ?? [];
  return (
    <Screen>
      <ScreenHeader
        title="Verifica tu deck"
        subtitle="Contrasta cada afirmación con información de Cala y revisa las fuentes."
      />
      <Text style={s.intro}>
        Contrasta cada afirmación con información de Cala y revisa las fuentes.
      </Text>
      {!job || job.status === 'error' ? (
        <View style={s.actions}>
          <Action title="Subir PDF" onPress={choose} disabled={busy} />
          <Action
            title="Probar con deck de ejemplo"
            secondary
            onPress={() => begin(verifySample)}
            disabled={busy}
          />
        </View>
      ) : null}
      {busy && job ? (
        <View style={s.card}>
          <ActivityIndicator color={theme.accent} />
          <Text style={s.white}>{stages[job.status]}</Text>
          <Text style={s.muted}>
            {job.progress.done}/{job.progress.total} afirmaciones
            {job.elapsed_s != null ? ` · ${job.elapsed_s}s` : ''}
          </Text>
        </View>
      ) : null}
      {error ? (
        <Text accessibilityRole="alert" style={s.error}>
          {error}
        </Text>
      ) : null}
      {job?.status === 'error' ? (
        <View>
          <Text style={s.error}>{job.error || 'No se pudo verificar el deck.'}</Text>
          <Action
            title="Verificar otro"
            onPress={() => {
              setJob(null);
              setError('');
            }}
          />
        </View>
      ) : null}
      {report ? (
        <>
          <View style={s.hero}>
            <Text style={s.eyebrow}>RESULTADO</Text>
            <Text style={s.startup}>{report.startup_name}</Text>
            <Text style={s.score}>
              {report.trust_score}
              <Text style={s.scoreUnit}>/100</Text>
            </Text>
            <Text style={s.muted}>Índice de confianza</Text>
          </View>
          <Text style={s.sectionTitle}>Resumen</Text>
          <View style={s.summary}>
            {(
              [
                'confirmed',
                'partially_confirmed',
                'contradicted',
                'no_data',
                'not_checked',
              ] as const
            ).map((k) => (
              <View key={k} style={s.count}>
                <Text
                  style={[
                    s.countNumber,
                    {
                      color:
                        theme[
                          k === 'confirmed'
                            ? 'confirmed'
                            : k === 'partially_confirmed'
                              ? 'partial'
                              : k === 'contradicted'
                                ? 'contradicted'
                                : 'neutral'
                        ],
                    },
                  ]}
                >
                  {report.summary[k]}
                </Text>
                <Text style={s.countLabel}>{labels[k]}</Text>
              </View>
            ))}
          </View>
          <Text style={s.sectionTitle}>Afirmaciones</Text>
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={s.chips}
          >
            <Chip active={filter === 'all'} title="Todas" onPress={() => setFilter('all')} />
            {(
              [
                'confirmed',
                'partially_confirmed',
                'contradicted',
                'no_data',
                'not_checked',
                'error',
              ] as const
            ).map((k) => (
              <Chip key={k} active={filter === k} title={labels[k]} onPress={() => setFilter(k)} />
            ))}
          </ScrollView>
          {visibleClaims.length ? (
            visibleClaims.map((claim, i) => <ClaimCard key={claim.id || i} claim={claim} />)
          ) : (
            <Text style={s.muted}>No hay afirmaciones en este filtro.</Text>
          )}
          <View style={{ marginTop: 12 }}>
            <Action
              title="Verificar otro"
              onPress={() => {
                setJob(null);
                setFilter('all');
              }}
            />
          </View>
        </>
      ) : null}
    </Screen>
  );
}
function PlatformWebFile(asset: DocumentPicker.DocumentPickerAsset): File | null {
  return typeof File !== 'undefined' &&
    (asset as DocumentPicker.DocumentPickerAsset & { file?: File }).file instanceof File
    ? (asset as DocumentPicker.DocumentPickerAsset & { file?: File }).file!
    : null;
}
const s = deckStyles(dark);
function Action({
  title,
  onPress,
  secondary,
  disabled,
}: {
  title: string;
  onPress: () => void;
  secondary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[s.button, secondary && s.secondary, disabled && { opacity: 0.55 }]}
    >
      <Text style={[s.buttonText, secondary && s.secondaryText]}>{title}</Text>
    </Pressable>
  );
}
function Chip({ title, onPress, active }: { title: string; onPress: () => void; active: boolean }) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      onPress={onPress}
      style={[s.chip, active && s.chipActive]}
    >
      <Text style={[s.chipText, active && { color: dark.accentText }]}>{title}</Text>
    </Pressable>
  );
}
function ClaimCard({ claim }: { claim: Claim }) {
  return (
    <View style={s.claim}>
      <View style={s.claimTop}>
        <Text style={s.category}>{claim.category}</Text>
        <VerdictBadge verdict={claim.verdict} />
      </View>
      <Text style={s.quote}>“{claim.quote}”</Text>
      <Text style={s.page}>Página {claim.page}</Text>
      <Text style={s.explanation}>{claim.explanation}</Text>
      {claim.sources?.length ? (
        <View style={s.sources}>
          <Text style={s.sourceHeading}>Fuentes</Text>
          {claim.sources.map((src, i) => (
            <Text
              key={`${src.url}-${i}`}
              accessibilityRole="link"
              onPress={() => Linking.openURL(src.url)}
              style={s.link}
            >
              ↗ {src.name}
            </Text>
          ))}
        </View>
      ) : (
        <Text style={s.sourceHeading}>Fuentes: ninguna disponible</Text>
      )}
    </View>
  );
}
function deckStyles(c: import('../src/theme').Colors) {
  return StyleSheet.create({
    screen: { flex: 1, backgroundColor: c.bg },
    content: { padding: 22, paddingBottom: 40, maxWidth: 820, width: '100%', alignSelf: 'center' },
    eyebrow: {
      color: c.accent,
      fontSize: 11,
      fontWeight: '700',
      letterSpacing: 1.5,
      marginBottom: 10,
    },
    title: { color: c.text, fontSize: 32, fontWeight: '800' },
    intro: { color: c.textMuted, fontSize: 15, lineHeight: 22, marginTop: 8, marginBottom: 22 },
    actions: { gap: 10, marginBottom: 18 },
    button: {
      backgroundColor: c.accent,
      paddingVertical: 14,
      paddingHorizontal: 18,
      borderRadius: 12,
      alignItems: 'center',
      marginTop: 8,
    },
    secondary: { backgroundColor: c.surface, borderWidth: 1, borderColor: c.border },
    buttonText: { color: c.accentText, fontWeight: '700', fontSize: 15 },
    secondaryText: { color: dark.accentText },
    card: {
      backgroundColor: c.surface,
      borderColor: c.border,
      borderWidth: 1,
      borderRadius: 16,
      padding: 20,
      alignItems: 'center',
      gap: 10,
      marginBottom: 16,
    },
    white: { color: c.text, fontSize: 16, fontWeight: '700' },
    muted: { color: c.textMuted, fontSize: 14 },
    error: {
      color: c.danger,
      backgroundColor: c.dangerSoft,
      borderRadius: 12,
      padding: 14,
      marginVertical: 10,
    },
    hero: {
      backgroundColor: c.surface,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 20,
      padding: 22,
      marginTop: 8,
    },
    startup: { color: c.text, fontSize: 22, fontWeight: '700' },
    score: { color: c.accent, fontSize: 64, fontWeight: '800', lineHeight: 72, marginTop: 10 },
    scoreUnit: { fontSize: 20, color: c.textMuted, fontWeight: '600' },
    sectionTitle: {
      color: c.text,
      fontWeight: '700',
      fontSize: 20,
      marginTop: 25,
      marginBottom: 12,
    },
    summary: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
    count: {
      flexGrow: 1,
      minWidth: 92,
      backgroundColor: c.surface,
      borderRadius: 12,
      padding: 12,
      borderWidth: 1,
      borderColor: c.border,
    },
    countNumber: { fontSize: 23, fontWeight: '800' },
    countLabel: { color: c.textMuted, fontSize: 11, marginTop: 3 },
    chips: { gap: 8, paddingBottom: 12 },
    chip: {
      paddingHorizontal: 13,
      paddingVertical: 8,
      borderRadius: 18,
      backgroundColor: c.surface,
      borderWidth: 1,
      borderColor: c.border,
    },
    chipActive: { backgroundColor: c.accent, borderColor: c.accent },
    chipText: { color: c.textMuted, fontSize: 12, fontWeight: '600' },
    claim: {
      backgroundColor: c.surface,
      borderWidth: 1,
      borderColor: c.border,
      borderRadius: 16,
      padding: 16,
      marginTop: 10,
    },
    claimTop: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 10,
    },
    category: {
      color: c.accent,
      fontSize: 12,
      fontWeight: '700',
      textTransform: 'uppercase',
      flexShrink: 1,
    },
    badge: {
      fontSize: 11,
      fontWeight: '700',
      borderWidth: 1,
      borderRadius: 14,
      paddingHorizontal: 9,
      paddingVertical: 5,
      overflow: 'hidden',
    },
    quote: { color: c.text, fontSize: 16, fontWeight: '600', lineHeight: 24, marginTop: 14 },
    page: { color: c.textMuted, fontSize: 12, marginTop: 6 },
    explanation: { color: c.textMuted, fontSize: 14, lineHeight: 21, marginTop: 12 },
    sources: { borderTopColor: c.border, borderTopWidth: 1, marginTop: 14, paddingTop: 12, gap: 8 },
    sourceHeading: { color: c.textMuted, fontSize: 12, fontWeight: '700', marginTop: 12 },
    link: { color: c.accent, fontSize: 13, textDecorationLine: 'underline' },
  });
}
