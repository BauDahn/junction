import { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter, type Href } from 'expo-router';
import { ApiError, type Source } from '../../src/api';
import {
  fetchEntityDetail,
  type EntityDetail,
  type EntityMode,
  type EntityRound,
} from '../../src/api/entities';
import { getOrCreateSessionId, resetSessionId } from '../../src/session';
import { maxWidth, useTheme, type Colors } from '../../src/theme';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const SIGNAL_LABELS: Record<string, string> = {
  sector: 'Sector',
  stage: 'Stage',
  region: 'Region',
  ticket: 'Ticket size',
  activity: 'Activity',
  closeness: 'Network proximity',
};

function formatSignalLabel(signal: string): string {
  const key = signal.trim().toLowerCase();
  if (SIGNAL_LABELS[key]) return SIGNAL_LABELS[key];
  if (!key) return 'Signal';
  return key.charAt(0).toUpperCase() + key.slice(1).replace(/_/g, ' ');
}

function formatFactValue(value: string | number): string {
  if (typeof value === 'number') {
    return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100);
  }
  return value;
}

function formatLoadedAt(raw: string): string {
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return raw;
  const month = MONTHS[parsed.getUTCMonth()];
  const day = parsed.getUTCDate();
  const year = parsed.getUTCFullYear();
  return `${month} ${day}, ${year}`;
}

function formatHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

function formatRoundMeta(round: EntityRound): string {
  return [round.amount, round.date].filter(Boolean).join(' · ');
}

function SourceLinks({ sources, styles }: { sources: Source[]; styles: ReturnType<typeof makeStyles> }) {
  if (!sources.length) return null;
  return (
    <View style={styles.sourcesRow}>
      {sources.map((source, index) => {
        const host = formatHost(source.url);
        const showHost = Boolean(host) && !source.name.toLowerCase().includes(host.toLowerCase());
        const meta = [source.date, showHost ? host : ''].filter(Boolean).join(' · ');
        const canOpen = /^https?:\/\//i.test(source.url);

        if (!canOpen) {
          return (
            <Text key={`${source.name}-${index}`} style={styles.sourcePlain}>
              {source.name}
              {meta ? ` · ${meta}` : ''}
            </Text>
          );
        }

        return (
          <Pressable
            key={`${source.url}-${index}`}
            accessibilityRole="link"
            accessibilityLabel={`Source: ${source.name}`}
            onPress={() => {
              void Linking.openURL(source.url).catch(() => {});
            }}
            style={({ pressed }) => [styles.sourceLinkPressable, pressed && styles.pressed]}
          >
            <Text style={styles.sourceLinkText}>
              {source.name}
              {meta ? <Text style={styles.sourceMeta}> · {meta}</Text> : null}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function DetailSkeleton({ styles }: { styles: ReturnType<typeof makeStyles> }) {
  return (
    <View accessibilityLabel="Loading entity details" style={styles.skeletonContainer}>
      <View style={[styles.skeletonBar, { width: 72, height: 12 }]} />
      <View style={[styles.skeletonBar, { width: '64%', height: 28, marginTop: 8 }]} />
      <View style={[styles.skeletonBar, { width: '92%', height: 14, marginTop: 16 }]} />
      <View style={[styles.skeletonBar, { width: '74%', height: 14, marginTop: 8 }]} />

      <View style={styles.section}>
        <View style={[styles.skeletonBar, { width: 128, height: 16, marginBottom: 16 }]} />
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: 88, height: 12 }]} />
          <View style={[styles.skeletonBar, { width: '88%', height: 14, marginTop: 8 }]} />
        </View>
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: 76, height: 12 }]} />
          <View style={[styles.skeletonBar, { width: '76%', height: 14, marginTop: 8 }]} />
        </View>
      </View>

      <View style={styles.section}>
        <View style={[styles.skeletonBar, { width: 96, height: 16, marginBottom: 16 }]} />
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: '55%', height: 14 }]} />
        </View>
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: '68%', height: 14 }]} />
        </View>
      </View>
    </View>
  );
}

export default function EntityDetailScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const styles = makeStyles(colors);

  const params = useLocalSearchParams<{ id?: string | string[]; mode?: string | string[] }>();
  const entityId = Array.isArray(params.id) ? (params.id[0] ?? '') : (params.id ?? '');
  const rawMode = Array.isArray(params.mode) ? params.mode[0] : params.mode;
  const mode: EntityMode = rawMode === 'investing' ? 'investing' : 'raising';

  const [detail, setDetail] = useState<EntityDetail | null>(null);
  const [isSample, setIsSample] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadKey, setReloadKey] = useState(0);

  const handleBack = useCallback(() => {
    if (router.canGoBack()) {
      router.back();
    } else {
      router.replace('/feed' as Href);
    }
  }, [router]);

  const openEntity = useCallback(
    (targetId: string) => {
      if (!targetId) return;
      router.push({
        pathname: '/entity/[id]',
        params: { id: targetId, mode },
      } as Href);
    },
    [mode, router],
  );

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError('');
      setDetail(null);
      setIsSample(false);

      if (!entityId.trim()) {
        if (active) setLoading(false);
        return;
      }

      let sessionId: string | null = null;
      try {
        sessionId = await getOrCreateSessionId();
      } catch {
        sessionId = null;
      }

      try {
        const result = await fetchEntityDetail(entityId, mode, sessionId);
        if (!active) return;
        setDetail(result.detail);
        setIsSample(result.isSample);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.code === 'session_not_found') {
          try {
            const refreshedId = await resetSessionId().catch(() => null);
            const retryResult = await fetchEntityDetail(entityId, mode, refreshedId);
            if (!active) return;
            setDetail(retryResult.detail);
            setIsSample(retryResult.isSample);
            return;
          } catch (retryErr: unknown) {
            if (!active) return;
            setError(
              retryErr instanceof Error
                ? retryErr.message
                : 'Could not reach the backend. Check your connection and try again.',
            );
            return;
          }
        }

        if (!active) return;
        setError(
          err instanceof Error
            ? err.message
            : 'Could not reach the backend. Check your connection and try again.',
        );
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => {
      active = false;
    };
  }, [entityId, mode, reloadKey]);

  const hasContent = Boolean(
    detail &&
      (detail.description ||
        detail.why_match.length > 0 ||
        detail.facts.length > 0 ||
        detail.rounds.length > 0 ||
        detail.portfolio.length > 0 ||
        detail.people.length > 0),
  );

  return (
    <ScrollView style={styles.screen} contentContainerStyle={styles.scrollContent}>
      <View style={styles.container}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Back"
          onPress={handleBack}
          style={({ pressed }) => [styles.backButton, pressed && styles.pressed]}
        >
          <Text style={styles.backText}>← Back</Text>
        </Pressable>

        {loading ? <DetailSkeleton styles={styles} /> : null}

        {!loading && error ? (
          <View accessibilityRole="alert" style={styles.stateBlock}>
            <Text style={styles.stateTitle}>Could not load entity</Text>
            <Text style={styles.stateBody}>{error}</Text>
            <View style={styles.stateActions}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setReloadKey((k) => k + 1)}
                style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.primaryButtonText}>Retry</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={handleBack}
                style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.secondaryButtonText}>Back to feed</Text>
              </Pressable>
            </View>
          </View>
        ) : null}

        {!loading && !error && !detail ? (
          <View style={styles.stateBlock}>
            <Text style={styles.stateTitle}>No verified entity data found</Text>
            <Text style={styles.stateBody}>
              Cala does not have sourced records for this entity yet.
            </Text>
            <View style={styles.stateActions}>
              <Pressable
                accessibilityRole="button"
                onPress={() => router.replace('/feed' as Href)}
                style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}
              >
                <Text style={styles.secondaryButtonText}>Back to feed</Text>
              </Pressable>
            </View>
          </View>
        ) : null}

        {!loading && !error && detail ? (
          <>
            <View style={styles.header}>
              <View style={styles.headerTopRow}>
                <View style={styles.headerIdentity}>
                  <Text style={styles.typeLabel}>
                    {detail.type === 'investor' ? 'Investor' : 'Startup'}
                  </Text>
                  <Text accessibilityRole="header" selectable style={styles.entityName}>
                    {detail.name}
                  </Text>
                </View>

                {detail.score !== undefined ? (
                  <View style={styles.scoreBlock}>
                    <Text style={styles.scoreLabel}>Match</Text>
                    <Text style={styles.scoreValue}>{Math.round(detail.score)}</Text>
                    {detail.confidence !== undefined && detail.confidence < 0.5 ? (
                      <Text style={styles.partialData}>Partial data</Text>
                    ) : null}
                  </View>
                ) : null}
              </View>

              {detail.description ? (
                <Text selectable style={styles.description}>
                  {detail.description}
                </Text>
              ) : null}

              {isSample ? (
                <Text style={styles.sampleNotice}>
                  Showing sample data while the backend is offline.
                </Text>
              ) : null}
            </View>

            {!hasContent ? (
              <View style={styles.section}>
                <Text style={styles.emptyInlineTitle}>No verified entity data found</Text>
                <Text style={styles.emptyInlineBody}>
                  Cala has not returned sourced facts, rounds, or relationships for this record yet.
                </Text>
              </View>
            ) : null}

            {detail.why_match.length > 0 ? (
              <View style={styles.section}>
                <Text accessibilityRole="header" style={styles.sectionTitle}>
                  Why it matches
                </Text>
                {detail.why_match.map((item, index) => (
                  <View
                    key={`${item.signal}-${index}`}
                    style={[styles.rowBlock, index === 0 && styles.firstRowBlock]}
                  >
                    <Text style={styles.signalLabel}>{formatSignalLabel(item.signal)}</Text>
                    <Text selectable style={styles.rowText}>
                      {item.text}
                    </Text>
                    <SourceLinks sources={item.sources} styles={styles} />
                  </View>
                ))}
              </View>
            ) : null}

            {detail.facts.length > 0 ? (
              <View style={styles.section}>
                <Text accessibilityRole="header" style={styles.sectionTitle}>
                  Key facts
                </Text>
                {detail.facts.map((fact, index) => (
                  <View
                    key={`${fact.label}-${index}`}
                    style={[styles.rowBlock, index === 0 && styles.firstRowBlock]}
                  >
                    <View style={styles.factTopRow}>
                      <Text style={styles.factLabel}>{fact.label}</Text>
                      <Text selectable style={styles.factValue}>
                        {formatFactValue(fact.value)}
                      </Text>
                    </View>
                    <SourceLinks sources={fact.sources} styles={styles} />
                  </View>
                ))}
              </View>
            ) : null}

            {detail.rounds.length > 0 ? (
              <View style={styles.section}>
                <Text accessibilityRole="header" style={styles.sectionTitle}>
                  Funding rounds
                </Text>
                {detail.rounds.map((round, index) => {
                  const meta = formatRoundMeta(round);
                  const leadSet = new Set(round.leads.map((l) => l.trim().toLowerCase()));
                  const coInvestors = round.investors.filter(
                    (inv) => !leadSet.has(inv.trim().toLowerCase()),
                  );
                  return (
                    <View
                      key={`${round.round_type ?? 'round'}-${round.date ?? index}-${index}`}
                      style={[styles.rowBlock, index === 0 && styles.firstRowBlock]}
                    >
                      <View style={styles.roundTopRow}>
                        <Text style={styles.roundType}>
                          {round.round_type || 'Funding round'}
                        </Text>
                        {meta ? <Text style={styles.roundMeta}>{meta}</Text> : null}
                      </View>

                      {round.leads.length > 0 ? (
                        <Text style={styles.roundInvestors}>
                          <Text style={styles.roundLeadLabel}>Lead: </Text>
                          {round.leads.join(', ')}
                        </Text>
                      ) : null}

                      {coInvestors.length > 0 ? (
                        <Text style={styles.roundCoInvestors}>
                          {round.leads.length > 0 ? 'Co-investors: ' : 'Investors: '}
                          {coInvestors.join(', ')}
                        </Text>
                      ) : null}

                      <SourceLinks sources={round.sources} styles={styles} />
                    </View>
                  );
                })}
              </View>
            ) : null}

            {detail.portfolio.length > 0 ? (
              <View style={styles.section}>
                <Text accessibilityRole="header" style={styles.sectionTitle}>
                  Portfolio
                </Text>
                {detail.portfolio.map((item, index) => (
                  <Pressable
                    key={`${item.id}-${index}`}
                    accessibilityRole="button"
                    onPress={() => openEntity(item.id)}
                    style={({ pressed }) => [
                      styles.navRow,
                      index === 0 && styles.firstRowBlock,
                      pressed && styles.pressed,
                    ]}
                  >
                    <Text style={styles.navRowTitle}>{item.name}</Text>
                    <Text style={styles.navChevron}>›</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}

            {detail.people.length > 0 ? (
              <View style={styles.section}>
                <Text accessibilityRole="header" style={styles.sectionTitle}>
                  People
                </Text>
                {detail.people.map((person, index) => (
                  <Pressable
                    key={`${person.id}-${index}`}
                    accessibilityRole="button"
                    onPress={() => openEntity(person.id)}
                    style={({ pressed }) => [
                      styles.navRow,
                      index === 0 && styles.firstRowBlock,
                      pressed && styles.pressed,
                    ]}
                  >
                    <View style={styles.personTextGroup}>
                      <Text style={styles.navRowTitle}>{person.name}</Text>
                      <Text style={styles.personMeta}>
                        {person.role}
                        {person.since ? ` · Since ${person.since}` : ''}
                      </Text>
                    </View>
                    <Text style={styles.navChevron}>›</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}

            <View style={styles.footer}>
              <Text style={styles.footerText}>
                {detail.loaded_at ? `Loaded ${formatLoadedAt(detail.loaded_at)}` : 'Loaded from Cala'}
              </Text>
            </View>
          </>
        ) : null}
      </View>
    </ScrollView>
  );
}

function makeStyles(c: Colors) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: c.bg,
    },
    scrollContent: {
      flexGrow: 1,
      paddingHorizontal: 20,
      paddingTop: 16,
      paddingBottom: 48,
    },
    container: {
      width: '100%',
      maxWidth,
      alignSelf: 'center',
    },
    pressed: {
      opacity: 0.65,
    },
    backButton: {
      alignSelf: 'flex-start',
      minHeight: 40,
      justifyContent: 'center',
      marginBottom: 16,
    },
    backText: {
      color: c.accent,
      fontSize: 15,
      fontWeight: '500',
    },

    // Header
    header: {
      paddingBottom: 8,
    },
    headerTopRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: 16,
    },
    headerIdentity: {
      flex: 1,
      minWidth: 0,
    },
    typeLabel: {
      color: c.textMuted,
      fontSize: 12,
      fontWeight: '600',
      letterSpacing: 0.8,
      textTransform: 'uppercase',
    },
    entityName: {
      color: c.text,
      fontSize: 28,
      fontWeight: '700',
      lineHeight: 34,
      letterSpacing: -0.4,
      marginTop: 4,
    },
    scoreBlock: {
      alignItems: 'flex-end',
      paddingTop: 2,
    },
    scoreLabel: {
      color: c.textMuted,
      fontSize: 11,
      fontWeight: '600',
      letterSpacing: 0.6,
      textTransform: 'uppercase',
    },
    scoreValue: {
      color: c.accent,
      fontSize: 28,
      fontWeight: '700',
      lineHeight: 32,
      fontVariant: ['tabular-nums'],
      marginTop: 2,
    },
    partialData: {
      color: c.textMuted,
      fontSize: 12,
      fontWeight: '500',
      marginTop: 2,
    },
    description: {
      color: c.textMuted,
      fontSize: 15,
      lineHeight: 22,
      marginTop: 12,
    },
    sampleNotice: {
      color: c.textFaint,
      fontSize: 12,
      marginTop: 12,
    },

    // Sections
    section: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      marginTop: 24,
      paddingTop: 24,
    },
    sectionTitle: {
      color: c.text,
      fontSize: 16,
      fontWeight: '600',
      marginBottom: 8,
    },
    rowBlock: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: 12,
    },
    firstRowBlock: {
      borderTopWidth: 0,
    },
    signalLabel: {
      color: c.textMuted,
      fontSize: 11,
      fontWeight: '600',
      letterSpacing: 0.5,
      textTransform: 'uppercase',
    },
    rowText: {
      color: c.text,
      fontSize: 15,
      lineHeight: 22,
      marginTop: 4,
    },

    // Key facts
    factTopRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: 16,
      flexWrap: 'wrap',
    },
    factLabel: {
      color: c.textMuted,
      fontSize: 14,
      lineHeight: 20,
      flexShrink: 1,
    },
    factValue: {
      color: c.text,
      fontSize: 15,
      fontWeight: '600',
      lineHeight: 22,
      fontVariant: ['tabular-nums'],
      textAlign: 'right',
      flexShrink: 1,
    },

    // Funding rounds
    roundTopRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: 16,
    },
    roundType: {
      color: c.text,
      fontSize: 15,
      fontWeight: '600',
      lineHeight: 22,
    },
    roundMeta: {
      color: c.text,
      fontSize: 14,
      fontWeight: '600',
      fontVariant: ['tabular-nums'],
    },
    roundInvestors: {
      color: c.text,
      fontSize: 14,
      lineHeight: 20,
      marginTop: 4,
    },
    roundLeadLabel: {
      fontWeight: '600',
      color: c.text,
    },
    roundCoInvestors: {
      color: c.textMuted,
      fontSize: 14,
      lineHeight: 20,
      marginTop: 2,
    },

    // Portfolio & People navigation rows
    navRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      minHeight: 44,
      paddingVertical: 12,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: 12,
    },
    navRowTitle: {
      color: c.text,
      fontSize: 15,
      fontWeight: '500',
      lineHeight: 20,
    },
    navChevron: {
      color: c.accent,
      fontSize: 18,
      fontWeight: '500',
    },
    personTextGroup: {
      flex: 1,
      minWidth: 0,
    },
    personMeta: {
      color: c.textMuted,
      fontSize: 13,
      lineHeight: 18,
      fontVariant: ['tabular-nums'],
      marginTop: 2,
    },

    // Sources
    sourcesRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      columnGap: 16,
      rowGap: 4,
      marginTop: 8,
    },
    sourceLinkPressable: {
      paddingVertical: 2,
    },
    sourceLinkText: {
      color: c.accent,
      fontSize: 13,
      lineHeight: 18,
    },
    sourceMeta: {
      color: c.textFaint,
    },
    sourcePlain: {
      color: c.textFaint,
      fontSize: 13,
      lineHeight: 18,
      paddingVertical: 2,
    },

    // Footer
    footer: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      marginTop: 24,
      paddingTop: 16,
    },
    footerText: {
      color: c.textFaint,
      fontSize: 12,
      fontVariant: ['tabular-nums'],
    },

    // States: Empty & Error
    stateBlock: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingTop: 24,
      marginTop: 8,
      gap: 8,
    },
    stateTitle: {
      color: c.text,
      fontSize: 18,
      fontWeight: '600',
    },
    stateBody: {
      color: c.textMuted,
      fontSize: 15,
      lineHeight: 22,
    },
    stateActions: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: 12,
      marginTop: 16,
    },
    primaryButton: {
      backgroundColor: c.accent,
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderRadius: 8,
      minHeight: 44,
      justifyContent: 'center',
      alignItems: 'center',
    },
    primaryButtonText: {
      color: c.accentText,
      fontSize: 15,
      fontWeight: '600',
    },
    secondaryButton: {
      borderWidth: 1,
      borderColor: c.border,
      paddingHorizontal: 16,
      paddingVertical: 10,
      borderRadius: 8,
      minHeight: 44,
      justifyContent: 'center',
      alignItems: 'center',
    },
    secondaryButtonText: {
      color: c.text,
      fontSize: 15,
      fontWeight: '500',
    },
    emptyInlineTitle: {
      color: c.text,
      fontSize: 16,
      fontWeight: '600',
    },
    emptyInlineBody: {
      color: c.textMuted,
      fontSize: 14,
      lineHeight: 20,
      marginTop: 4,
    },

    // Skeleton
    skeletonContainer: {
      paddingTop: 4,
    },
    skeletonBar: {
      backgroundColor: c.border,
      opacity: 0.75,
      borderRadius: 4,
    },
    skeletonRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: 14,
    },
  });
}
