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
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme, type Colors } from '../../src/theme';

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
      <View style={[styles.skeletonBar, { width: '64%', height: 28, marginTop: space.sm }]} />
      <View style={[styles.skeletonBar, { width: '92%', height: 14, marginTop: space.lg }]} />
      <View style={[styles.skeletonBar, { width: '74%', height: 14, marginTop: space.sm }]} />

      <View style={styles.section}>
        <View style={[styles.skeletonBar, { width: 128, height: 16, marginBottom: space.lg }]} />
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: 88, height: 12 }]} />
          <View style={[styles.skeletonBar, { width: '88%', height: 14, marginTop: space.sm }]} />
        </View>
        <View style={styles.skeletonRow}>
          <View style={[styles.skeletonBar, { width: 76, height: 12 }]} />
          <View style={[styles.skeletonBar, { width: '76%', height: 14, marginTop: space.sm }]} />
        </View>
      </View>

      <View style={styles.section}>
        <View style={[styles.skeletonBar, { width: 96, height: 16, marginBottom: space.lg }]} />
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
      paddingHorizontal: pageMargin,
      paddingTop: space.lg,
      paddingBottom: space.xxl,
    },
    container: {
      width: '100%',
      maxWidth,
      alignSelf: 'center',
      backgroundColor: c.surface,
      borderLeftWidth: 1,
      borderRightWidth: 1,
      borderColor: c.border,
    },
    pressed: {
      opacity: 0.65,
    },
    backButton: {
      alignSelf: 'flex-start',
      minHeight: 40,
      justifyContent: 'center',
      marginBottom: space.lg,
    },
    backText: {
      color: c.accent,
      fontSize: font.body,
      fontWeight: '500',
    },

    // Header
    header: {
      paddingBottom: space.sm,
    },
    headerTopRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'flex-start',
      gap: space.lg,
    },
    headerIdentity: {
      flex: 1,
      minWidth: 0,
    },
    typeLabel: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    entityName: {
      color: c.text,
      fontSize: font.h1,
      fontWeight: '700',
      lineHeight: 34,
      letterSpacing: 0,
      marginTop: space.xs,
    },
    scoreBlock: {
      alignItems: 'flex-end',
      paddingTop: space.xs,
    },
    scoreLabel: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    scoreValue: {
      color: c.accent,
      fontSize: font.h1,
      fontWeight: '700',
      lineHeight: 32,
      fontVariant: ['tabular-nums'],
      marginTop: space.xs,
    },
    partialData: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '500',
      marginTop: space.xs,
    },
    description: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 22,
      marginTop: space.md,
    },
    sampleNotice: {
      color: c.textFaint,
      fontSize: font.caption,
      marginTop: space.md,
    },

    // Sections
    section: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      marginTop: space.xl,
      paddingTop: space.xl,
    },
    sectionTitle: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
      marginBottom: space.sm,
    },
    rowBlock: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: space.md,
    },
    firstRowBlock: {
      borderTopWidth: 0,
    },
    signalLabel: {
      color: c.textMuted,
      fontSize: font.caption,
      fontWeight: '600',
      letterSpacing: 0,
    },
    rowText: {
      color: c.text,
      fontSize: font.body,
      lineHeight: 22,
      marginTop: space.xs,
    },

    // Key facts
    factTopRow: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'baseline',
      gap: space.lg,
      flexWrap: 'wrap',
    },
    factLabel: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 20,
      flexShrink: 1,
    },
    factValue: {
      color: c.text,
      fontSize: font.body,
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
      gap: space.lg,
    },
    roundType: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
      lineHeight: 22,
    },
    roundMeta: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
      fontVariant: ['tabular-nums'],
    },
    roundInvestors: {
      color: c.text,
      fontSize: font.body,
      lineHeight: 20,
      marginTop: space.xs,
    },
    roundLeadLabel: {
      fontWeight: '600',
      color: c.text,
    },
    roundCoInvestors: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 20,
      marginTop: space.xs,
    },

    // Portfolio & People navigation rows
    navRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      minHeight: 44,
      paddingVertical: space.md,
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: space.md,
    },
    navRowTitle: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '500',
      lineHeight: 20,
    },
    navChevron: {
      color: c.accent,
      fontSize: font.lead,
      fontWeight: '500',
    },
    personTextGroup: {
      flex: 1,
      minWidth: 0,
    },
    personMeta: {
      color: c.textMuted,
      fontSize: font.small,
      lineHeight: 18,
      fontVariant: ['tabular-nums'],
      marginTop: space.xs,
    },

    // Sources
    sourcesRow: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      columnGap: space.sm,
      rowGap: space.xs,
      marginTop: space.sm,
    },
    sourceLinkPressable: {
      borderWidth: 1,
      borderColor: c.border,
      backgroundColor: c.surfaceAlt,
      borderRadius: radius.sm,
      paddingHorizontal: space.sm,
      paddingVertical: space.xs,
    },
    sourceLinkText: {
      color: c.accent,
      fontSize: font.caption,
      fontWeight: '500',
    },
    sourceMeta: {
      color: c.textMuted,
      fontSize: font.caption,
    },
    sourcePlain: {
      color: c.textFaint,
      fontSize: font.small,
      lineHeight: 18,
      paddingVertical: space.xs,
    },

    // Footer
    footer: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      marginTop: space.xl,
      paddingTop: space.lg,
    },
    footerText: {
      color: c.textFaint,
      fontSize: font.caption,
      fontVariant: ['tabular-nums'],
    },

    // States: Empty & Error
    stateBlock: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingTop: space.xl,
      marginTop: space.sm,
      gap: space.sm,
    },
    stateTitle: {
      color: c.text,
      fontSize: font.lead,
      fontWeight: '600',
    },
    stateBody: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 22,
    },
    stateActions: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: space.md,
      marginTop: space.lg,
    },
    primaryButton: {
      backgroundColor: c.accent,
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.md,
      minHeight: 44,
      justifyContent: 'center',
      alignItems: 'center',
    },
    primaryButtonText: {
      color: c.accentText,
      fontSize: font.body,
      fontWeight: '600',
    },
    secondaryButton: {
      borderWidth: 1,
      borderColor: c.border,
      paddingHorizontal: space.lg,
      paddingVertical: space.sm,
      borderRadius: radius.md,
      minHeight: 44,
      justifyContent: 'center',
      alignItems: 'center',
    },
    secondaryButtonText: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '500',
    },
    emptyInlineTitle: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
    },
    emptyInlineBody: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 20,
      marginTop: space.xs,
    },

    // Skeleton
    skeletonContainer: {
      paddingTop: space.xs,
    },
    skeletonBar: {
      backgroundColor: c.border,
      opacity: 0.75,
      borderRadius: radius.sm,
    },
    skeletonRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: space.sm,
    },
  });
}
