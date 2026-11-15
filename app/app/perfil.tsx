import { useCallback, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import {
  ApiError,
  getProfile,
  getRecommendations,
  type Profile,
  type Recommendations,
} from '../src/api';
import CardView from '../src/components/CardView';
import { getSessionId } from '../src/session';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme, type Colors } from '../src/theme';
import { Button, StateView } from '../src/ui';

const mockEnabled = process.env.EXPO_PUBLIC_MOCK === '1';

const BACKEND_ERROR = 'Could not reach the backend. Check your connection and try again.';

const DEMO_PROFILE: Profile = {
  startup_name: 'Nordleaf',
  one_liner: 'Energy efficiency and telemetry software for commercial buildings',
  sector: 'ClimateTech',
  stage: 'Pre-seed',
  location: 'Helsinki',
  raising: { round: 'Pre-seed', amount: '€1.2M' },
  competitors: ['GreenBuild', 'Wattwise'],
  target_customers: 'Commercial real estate operators',
  role: 'founder',
  interests: {
    sectors: ['ClimateTech', 'PropTech', 'B2B SaaS'],
    regions: ['Nordics', 'Baltics'],
    stages: ['Pre-seed', 'Seed'],
    follows: {
      companies: ['Amenitiz'],
      investors: ['Eight Roads Ventures', 'Chalfen Ventures'],
    },
  },
  facts: [],
  updated_at: new Date().toISOString(),
};

const DEMO_RECOMMENDATIONS: Recommendations = {
  status: 'ready',
  updated_at: new Date().toISOString(),
  investors: [
    {
      type: 'investor',
      title: 'Northzone',
      subtitle: 'Pre-seed & Seed · Nordics',
      reason: 'Active lead investor in Nordic B2B software and climate infrastructure.',
      sources: [{ name: 'Cala', url: 'https://cala.ai' }],
    },
    {
      type: 'investor',
      title: 'Chalfen Ventures',
      subtitle: 'Seed · Europe',
      reason: 'Backs European enterprise software teams at initial institutional rounds.',
      sources: [{ name: 'Cala', url: 'https://cala.ai' }],
    },
  ],
  competitors: [
    {
      type: 'competitor',
      title: 'GreenBuild',
      subtitle: 'Building analytics · Sweden',
      reason: 'Comparable building efficiency platform targeting Nordic property portfolios.',
      sources: [{ name: 'Cala', url: 'https://cala.ai' }],
    },
  ],
  prospects: [
    {
      type: 'prospect',
      title: 'Nordic Estates',
      subtitle: 'Commercial real estate · Finland',
      reason: 'Multi-building portfolio matching your target customer profile.',
      sources: [{ name: 'Cala', url: 'https://cala.ai' }],
    },
  ],
};

function formatError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500) return 'The server could not load your profile. Try again.';
    return error.message || BACKEND_ERROR;
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
    return error.message || BACKEND_ERROR;
  }
  return BACKEND_ERROR;
}

function formatRole(role?: Profile['role']): string | undefined {
  if (role === 'founder') return 'Founder';
  if (role === 'investor') return 'Investor';
  if (role === 'other') return 'Other';
  return undefined;
}

function formatDate(iso?: string): string | undefined {
  if (!iso) return undefined;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function hasProfileContent(p: Profile, r: Recommendations | null): boolean {
  const hasFields = Boolean(
    p.startup_name ||
      p.one_liner ||
      p.sector ||
      p.stage ||
      p.location ||
      p.target_customers ||
      p.role ||
      p.raising?.amount != null ||
      p.raising?.round ||
      p.competitors?.length ||
      p.facts?.length ||
      p.interests?.sectors?.length ||
      p.interests?.regions?.length ||
      p.interests?.stages?.length ||
      p.interests?.follows?.companies?.length ||
      p.interests?.follows?.investors?.length,
  );
  const hasRecs = Boolean(
    r && (r.investors.length || r.competitors.length || r.prospects.length),
  );
  return hasFields || hasRecs;
}

export default function PerfilScreen() {
  const router = useRouter();
  const { colors } = useTheme();
  const s = useMemo(() => profileStyles(colors), [colors]);

  const [profile, setProfile] = useState<Profile | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null);
  const [loading, setLoading] = useState(true);
  const [empty, setEmpty] = useState(false);
  const [error, setError] = useState('');
  const hasLoadedOnce = useRef(false);

  const loadProfile = useCallback(async (background = false) => {
    if (!background) {
      setLoading(true);
      setError('');
    }
    try {
      const sessionId = await getSessionId();
      if (!sessionId) {
        if (mockEnabled) {
          setProfile(DEMO_PROFILE);
          setRecommendations(DEMO_RECOMMENDATIONS);
          setEmpty(false);
        } else {
          setProfile(null);
          setRecommendations(null);
          setEmpty(true);
        }
        return;
      }

      const [p, r] = await Promise.all([
        getProfile(sessionId),
        getRecommendations(sessionId).catch(() => null),
      ]);
      if (!hasProfileContent(p, r)) {
        if (mockEnabled) {
          setProfile(DEMO_PROFILE);
          setRecommendations(DEMO_RECOMMENDATIONS);
          setEmpty(false);
        } else {
          setProfile(null);
          setRecommendations(null);
          setEmpty(true);
        }
        return;
      }
      setProfile(p);
      setRecommendations(r);
      setEmpty(false);
      setError('');
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 404) {
        if (mockEnabled) {
          setProfile(DEMO_PROFILE);
          setRecommendations(DEMO_RECOMMENDATIONS);
          setEmpty(false);
        } else {
          setProfile(null);
          setRecommendations(null);
          setEmpty(true);
        }
      } else {
        setError(formatError(e));
      }
    } finally {
      hasLoadedOnce.current = true;
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadProfile(hasLoadedOnce.current);
    }, [loadProfile]),
  );

  const sections = [
    ['investors', 'Investors'],
    ['competitors', 'Competitors'],
    ['prospects', 'Potential customers'],
  ] as const;

  const raisingValue = profile?.raising
    ? [
        profile.raising.round,
        profile.raising.amount != null && profile.raising.amount !== ''
          ? String(profile.raising.amount)
          : undefined,
      ]
        .filter(Boolean)
        .join(' · ')
    : undefined;

  const hasFocus = Boolean(
    profile?.interests?.sectors?.length ||
      profile?.interests?.regions?.length ||
      profile?.interests?.stages?.length,
  );
  const hasFollows = Boolean(
    profile?.interests?.follows?.companies?.length ||
      profile?.interests?.follows?.investors?.length,
  );
  const updatedLabel = formatDate(profile?.updated_at);

  return (
    <ScrollView style={s.screen} contentContainerStyle={s.content}>
      <View style={s.topBar}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Back"
          onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))}
        >
          <Text style={s.navAction}>Back</Text>
        </Pressable>
        <Pressable
          accessibilityRole="link"
          accessibilityLabel="Edit context"
          onPress={() => router.push('/context')}
        >
          <Text style={s.navAction}>Edit context</Text>
        </Pressable>
      </View>

      <View style={s.header}>
        <Text style={s.subtitle}>
          Your startup context, followed entities, and Cala recommendations.
        </Text>
      </View>

      {loading ? (
        <View style={s.stateWrap}>
          <StateView kind="loading" title="Loading profile…" />
        </View>
      ) : null}

      {!loading && error ? (
        <View style={s.stateWrap}>
          <StateView
            kind="error"
            title="Could not load profile"
            message={error}
            action={
              <Button
                label="Try again"
                variant="secondary"
                onPress={() => void loadProfile(false)}
              />
            }
          />
        </View>
      ) : null}

      {!loading && !error && empty ? (
        <View style={s.stateWrap}>
          <StateView
            kind="empty"
            title="No profile yet"
            message="Add startup context or ask Cala a question to build your profile."
            action={
              <View style={s.emptyActions}>
                <Button label="Add context" onPress={() => router.push('/context')} />
                <Button
                  label="Ask Cala"
                  variant="secondary"
                  onPress={() => router.push('/chat')}
                />
              </View>
            }
          />
        </View>
      ) : null}

      {!loading && !error && profile ? (
        <>
          <View style={s.section}>
            <Text style={s.sectionLabel}>Startup</Text>
            <Text style={s.startupName}>{profile.startup_name || 'Your startup'}</Text>
            {profile.one_liner ? <Text style={s.oneLiner}>{profile.one_liner}</Text> : null}
            <View style={s.rows}>
              <InfoRow label="Role" value={formatRole(profile.role)} />
              <InfoRow label="Sector" value={profile.sector} />
              <InfoRow label="Stage" value={profile.stage} />
              <InfoRow label="Location" value={profile.location} />
              <InfoRow label="Target round" value={raisingValue} />
              <InfoRow label="Target customers" value={profile.target_customers} />
              <InfoRow
                label="Competitors"
                value={profile.competitors?.length ? profile.competitors.join(', ') : undefined}
              />
            </View>
          </View>

          {hasFocus ? (
            <View style={s.section}>
              <Text style={s.sectionLabel}>Focus</Text>
              <View style={s.rows}>
                <InfoRow
                  label="Sectors"
                  value={
                    profile.interests?.sectors?.length
                      ? profile.interests.sectors.join(', ')
                      : undefined
                  }
                />
                <InfoRow
                  label="Regions"
                  value={
                    profile.interests?.regions?.length
                      ? profile.interests.regions.join(', ')
                      : undefined
                  }
                />
                <InfoRow
                  label="Stages"
                  value={
                    profile.interests?.stages?.length
                      ? profile.interests.stages.join(', ')
                      : undefined
                  }
                />
              </View>
            </View>
          ) : null}

          {hasFollows ? (
            <View style={s.section}>
              <Text style={s.sectionLabel}>Follows</Text>
              <View style={s.rows}>
                <InfoRow
                  label="Companies"
                  value={
                    profile.interests?.follows?.companies?.length
                      ? profile.interests.follows.companies.join(', ')
                      : undefined
                  }
                />
                <InfoRow
                  label="Investors"
                  value={
                    profile.interests?.follows?.investors?.length
                      ? profile.interests.follows.investors.join(', ')
                      : undefined
                  }
                />
              </View>
            </View>
          ) : null}

          {profile.facts?.length ? (
            <View style={s.section}>
              <Text style={s.sectionLabel}>Captured signals</Text>
              <View style={s.rows}>
                {profile.facts.map((fact, idx) => (
                  <View key={`${fact.text}-${idx}`} style={s.factRow}>
                    <Text style={s.factText}>{fact.text}</Text>
                    <Text style={s.factOrigin}>
                      {fact.origin === 'deck' ? 'Deck' : 'User context'}
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          ) : null}

          {recommendations ? (
            <View style={s.recsSection}>
              <Text accessibilityRole="header" style={s.recsHeading}>
                Recommendations
              </Text>
              {recommendations.status === 'running' ? (
                <Text style={s.recsStatus}>Updating recommendations from Cala…</Text>
              ) : null}
              {sections.map(([key, label]) => (
                <View key={key} style={s.recGroup}>
                  <Text accessibilityRole="header" style={s.recGroupTitle}>
                    {label}
                  </Text>
                  {recommendations[key].length ? (
                    <View style={s.recList}>
                      {recommendations[key].map((card, i) => (
                        <CardView key={`${card.title}-${i}`} card={card} />
                      ))}
                    </View>
                  ) : (
                    <Text style={s.emptyRowText}>No recommendations yet.</Text>
                  )}
                </View>
              ))}
            </View>
          ) : null}

          {updatedLabel ? <Text style={s.updatedAt}>Updated {updatedLabel}</Text> : null}
        </>
      ) : null}
    </ScrollView>
  );
}

function InfoRow({ label, value }: { label: string; value?: string }) {
  const { colors } = useTheme();
  if (!value) return null;
  return (
    <View
      style={{
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: space.lg,
        borderTopWidth: 1,
        borderTopColor: colors.border,
        paddingVertical: space.md,
      }}
    >
      <Text style={{ color: colors.textMuted, fontSize: font.small }}>{label}</Text>
      <Text
        style={{
          color: colors.text,
          fontSize: font.body,
          fontWeight: '500',
          textAlign: 'right',
          flexShrink: 1,
        }}
      >
        {value}
      </Text>
    </View>
  );
}

function profileStyles(c: Colors) {
  return StyleSheet.create({
    screen: {
      flex: 1,
      backgroundColor: c.bg,
    },
    content: {
      paddingHorizontal: pageMargin,
      paddingTop: space.lg,
      paddingBottom: space.xxl,
      width: '100%',
      maxWidth,
      alignSelf: 'center',
      flexGrow: 1,
      backgroundColor: c.surface,
      borderLeftWidth: 1,
      borderRightWidth: 1,
      borderColor: c.border,
    },
    topBar: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingHorizontal: pageMargin,
      paddingVertical: space.md,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    navAction: {
      color: c.accent,
      fontSize: font.body,
      fontWeight: '600',
    },
    header: {
      paddingHorizontal: pageMargin,
      paddingVertical: space.md,
    },
    title: {
      color: c.text,
      fontSize: font.h1,
      fontWeight: '700',
    },
    subtitle: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 22,
    },
    stateWrap: {
      marginTop: space.xl,
    },
    emptyActions: {
      flexDirection: 'row',
      flexWrap: 'wrap',
      gap: space.sm,
    },
    section: {
      marginTop: space.xl,
    },
    sectionLabel: {
      color: c.text,
      fontSize: font.small,
      fontWeight: '600',
      letterSpacing: 0,
      marginBottom: space.sm,
    },
    startupName: {
      color: c.text,
      fontSize: font.h2,
      fontWeight: '700',
    },
    oneLiner: {
      color: c.textMuted,
      fontSize: font.body,
      lineHeight: 22,
      marginTop: space.xs,
      marginBottom: space.md,
    },
    rows: {
      marginTop: space.sm,
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    factRow: {
      borderTopWidth: 1,
      borderTopColor: c.border,
      paddingVertical: space.md,
      gap: space.xs,
    },
    factText: {
      color: c.text,
      fontSize: font.body,
      lineHeight: 20,
    },
    factOrigin: {
      color: c.textFaint,
      fontSize: font.caption,
    },
    recsSection: {
      marginTop: space.xxl,
    },
    recsHeading: {
      color: c.text,
      fontSize: font.h2,
      fontWeight: '700',
    },
    recsStatus: {
      color: c.textMuted,
      fontSize: font.small,
      marginTop: space.xs,
    },
    recGroup: {
      marginTop: space.xl,
    },
    recGroupTitle: {
      color: c.text,
      fontSize: font.body,
      fontWeight: '600',
      marginBottom: space.sm,
    },
    recList: {
      borderBottomWidth: 1,
      borderBottomColor: c.border,
    },
    emptyRowText: {
      color: c.textMuted,
      fontSize: font.body,
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderColor: c.border,
      paddingVertical: space.md,
    },
    updatedAt: {
      color: c.textFaint,
      fontSize: font.caption,
      marginTop: space.xl,
    },
  });
}
