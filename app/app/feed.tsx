import { useCallback, useEffect, useRef, useState } from 'react';
import {
  FlatList,
  Platform,
  Pressable,
  RefreshControl,
  Text,
  View,
  type PressableStateCallbackType,
} from 'react-native';
import { useFocusEffect, useRouter } from 'expo-router';
import { ApiError } from '../src/api';
import { getFeed, getMockFeed, type FeedCard, type FeedResponse } from '../src/api/feed';
import { useMode, type MatchMode } from '../src/mode';
import { getOrCreateSessionId, resetSessionId } from '../src/session';
import { font, maxWidth, pageMargin, radius, space, tabularNums, useTheme } from '../src/theme';

const SKELETON_ROWS = [0, 1, 2, 3, 4, 5];

function FeedSkeleton() {
  const { colors } = useTheme();
  return (
    <View accessibilityLabel="Loading matches" style={{ flex: 1 }}>
      <View
        style={{
          paddingHorizontal: pageMargin,
          paddingVertical: space.md,
          borderBottomWidth: 1,
          borderBottomColor: colors.border,
        }}
      >
        <View
          style={{
            width: 168,
            height: 12,
            borderRadius: 4,
            backgroundColor: colors.surfaceAlt,
          }}
        />
      </View>
      {SKELETON_ROWS.map((row) => (
        <View
          key={row}
          style={{
            paddingHorizontal: pageMargin,
            paddingVertical: space.lg,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
            flexDirection: 'row',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: space.lg,
          }}
        >
          <View style={{ flex: 1, gap: space.sm }}>
            <View
              style={{
                width: row % 2 === 0 ? '48%' : '56%',
                height: 16,
                borderRadius: 4,
                backgroundColor: colors.surfaceAlt,
              }}
            />
            <View
              style={{
                width: '86%',
                height: 12,
                borderRadius: 4,
                backgroundColor: colors.surfaceAlt,
              }}
            />
            <View
              style={{
                width: '38%',
                height: 10,
                borderRadius: 4,
                backgroundColor: colors.surfaceAlt,
              }}
            />
            <View
              style={{
                width: '70%',
                height: 12,
                borderRadius: 4,
                backgroundColor: colors.surfaceAlt,
              }}
            />
          </View>
          <View
            style={{
              width: 32,
              height: 22,
              borderRadius: 4,
              backgroundColor: colors.surfaceAlt,
            }}
          />
        </View>
      ))}
    </View>
  );
}

function FeedRow({ item, onPress }: { item: FeedCard; onPress: () => void }) {
  const { colors } = useTheme();
  const score = Math.max(0, Math.min(100, Math.round(item.score)));

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${item.name}, affinity score ${score}`}
      onPress={onPress}
      style={(state: PressableStateCallbackType & { hovered?: boolean }) => ({
        paddingHorizontal: pageMargin,
        paddingVertical: space.lg,
        backgroundColor: state.pressed || state.hovered ? colors.surfaceAlt : colors.surface,
        borderBottomWidth: 1,
        borderBottomColor: colors.border,
        ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
      })}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: space.lg,
        }}
      >
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text numberOfLines={1} style={{ fontSize: 16, fontWeight: '600', color: colors.text }}>
            {item.name}
          </Text>
          {item.one_liner ? (
            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={{
                fontSize: 14,
                color: colors.textMuted,
                marginTop: space.xs,
                lineHeight: 20,
              }}
            >
              {item.one_liner}
            </Text>
          ) : null}
          {item.tags.length > 0 ? (
            <Text
              numberOfLines={1}
              ellipsizeMode="tail"
              style={{
                fontSize: font.caption,
                color: colors.textFaint,
                marginTop: space.xs,
                lineHeight: 16,
              }}
            >
              {item.tags.join(' · ')}
            </Text>
          ) : null}
          {item.why_match[0] ? (
            <Text
              numberOfLines={2}
              style={{
                fontSize: font.small,
                color: colors.text,
                marginTop: space.sm,
                lineHeight: 18,
              }}
            >
              {item.why_match[0]}
            </Text>
          ) : null}
        </View>

        <View style={{ alignItems: 'flex-end', minWidth: 56, paddingTop: 2 }}>
          <Text
            style={[
              {
                fontSize: 20,
                fontWeight: '700',
                color: colors.accent,
                lineHeight: 24,
              },
              tabularNums,
            ]}
          >
            {score}
          </Text>
          {item.confidence < 0.5 ? (
            <Text style={{ fontSize: 11, color: colors.textFaint, marginTop: space.xs }}>
              Partial data
            </Text>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}

export default function FeedScreen() {
  const router = useRouter();
  const { mode } = useMode();
  const { colors } = useTheme();

  const [items, setItems] = useState<FeedCard[]>([]);
  const [nextCursor, setNextCursor] = useState<string | undefined>(undefined);
  const [confidenceNote, setConfidenceNote] = useState<string | undefined>(undefined);
  const [isSample, setIsSample] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [loadMoreError, setLoadMoreError] = useState('');

  const requestSeq = useRef(0);
  const sessionIdRef = useRef<string | null>(null);
  const needsFocusRefresh = useRef(false);
  const hasItemsRef = useRef(false);

  const fetchPage = useCallback(
    async (targetMode: MatchMode, cursor?: string): Promise<FeedResponse> => {
      let sid: string;
      try {
        sid = sessionIdRef.current ?? (await getOrCreateSessionId());
        sessionIdRef.current = sid;
      } catch (err) {
        if (err instanceof ApiError) throw err;
        if (!cursor) return getMockFeed(targetMode);
        throw new Error('Unable to reach the server. Check your connection.');
      }

      try {
        return await getFeed({
          sessionId: sid,
          mode: targetMode,
          limit: 20,
          cursor,
          fallbackOnNetworkError: !cursor,
        });
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          sid = await resetSessionId();
          sessionIdRef.current = sid;
          return await getFeed({
            sessionId: sid,
            mode: targetMode,
            limit: 20,
            cursor,
            fallbackOnNetworkError: !cursor,
          });
        }
        throw err;
      }
    },
    [],
  );

  const loadInitial = useCallback(
    async (targetMode: MatchMode, kind: 'initial' | 'refresh' | 'silent' = 'initial') => {
      needsFocusRefresh.current = false;
      const seq = ++requestSeq.current;
      if (kind === 'refresh') {
        setRefreshing(true);
      } else if (kind === 'initial') {
        setLoading(true);
        hasItemsRef.current = false;
        setItems([]);
      }
      if (kind !== 'silent' || !hasItemsRef.current) {
        setError('');
        setLoadMoreError('');
      }

      try {
        const res = await fetchPage(targetMode);
        if (seq !== requestSeq.current) return;
        hasItemsRef.current = res.items.length > 0;
        setItems(res.items);
        setNextCursor(res.next_cursor);
        setConfidenceNote(res.confidence_note);
        setIsSample(Boolean(res.is_sample));
        setError('');
      } catch (err) {
        if (seq !== requestSeq.current) return;
        if (kind !== 'silent' || !hasItemsRef.current) {
          hasItemsRef.current = false;
          setItems([]);
          setNextCursor(undefined);
          setConfidenceNote(undefined);
          setIsSample(false);
          setError(
            err instanceof Error
              ? err.message
              : 'Could not load your feed. Check your connection and try again.',
          );
        }
      } finally {
        if (seq === requestSeq.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [fetchPage],
  );

  useEffect(() => {
    void loadInitial(mode, 'initial');
  }, [mode, loadInitial]);

  useFocusEffect(
    useCallback(() => {
      if (needsFocusRefresh.current) {
        needsFocusRefresh.current = false;
        void loadInitial(mode, 'silent');
      }
      return () => {
        needsFocusRefresh.current = true;
      };
    }, [loadInitial, mode]),
  );

  const handleLoadMore = useCallback(async () => {
    if (!nextCursor || loadingMore || loading || isSample) return;
    const seq = requestSeq.current;
    setLoadingMore(true);
    setLoadMoreError('');

    try {
      const res = await fetchPage(mode, nextCursor);
      if (seq !== requestSeq.current) return;
      setItems((prev) => {
        const seen = new Set(prev.map((entry) => entry.id));
        return [...prev, ...res.items.filter((entry) => !seen.has(entry.id))];
      });
      setNextCursor(res.next_cursor);
      if (res.confidence_note !== undefined) {
        setConfidenceNote(res.confidence_note);
      }
    } catch (err) {
      if (seq !== requestSeq.current) return;
      setLoadMoreError(
        err instanceof Error ? err.message : 'Could not load additional matches.',
      );
    } finally {
      if (seq === requestSeq.current) {
        setLoadingMore(false);
      }
    }
  }, [fetchPage, isSample, loading, loadingMore, mode, nextCursor]);

  const headerSubtitle =
    mode === 'raising' ? 'Investors ranked by affinity' : 'Startups ranked by affinity';

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View
        style={{
          flex: 1,
          width: '100%',
          maxWidth,
          alignSelf: 'center',
          backgroundColor: colors.surface,
        }}
      >
        {loading && items.length === 0 ? (
          <FeedSkeleton />
        ) : error && items.length === 0 ? (
          <View
            style={{
              flex: 1,
              justifyContent: 'center',
              paddingHorizontal: pageMargin,
              paddingVertical: space.xxl,
            }}
          >
            <Text style={{ fontSize: font.lead, fontWeight: '600', color: colors.text }}>
              Could not load matches
            </Text>
            <Text
              style={{
                fontSize: font.body,
                color: colors.textMuted,
                marginTop: space.sm,
                lineHeight: 22,
              }}
            >
              {error}
            </Text>
            <View style={{ flexDirection: 'row', marginTop: space.lg }}>
              <Pressable
                accessibilityRole="button"
                onPress={() => void loadInitial(mode)}
                style={({ pressed }) => ({
                  backgroundColor: colors.accent,
                  minHeight: 44,
                  justifyContent: 'center',
                  paddingHorizontal: space.lg,
                  paddingVertical: 10,
                  borderRadius: radius.md,
                  opacity: pressed ? 0.85 : 1,
                  ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
                })}
              >
                <Text style={{ color: colors.accentText, fontSize: font.body, fontWeight: '600' }}>
                  Retry
                </Text>
              </Pressable>
            </View>
          </View>
        ) : !loading && items.length === 0 ? (
          <View
            style={{
              flex: 1,
              justifyContent: 'center',
              paddingHorizontal: pageMargin,
              paddingVertical: space.xxl,
            }}
          >
            <Text style={{ fontSize: font.lead, fontWeight: '600', color: colors.text }}>
              {mode === 'raising' ? 'No investor matches yet' : 'No startup matches yet'}
            </Text>
            <Text
              style={{
                fontSize: font.body,
                color: colors.textMuted,
                marginTop: space.sm,
                lineHeight: 22,
              }}
            >
              {confidenceNote ||
                'Add your pitch deck, voice note, or thesis details in Context to rank relevant matches.'}
            </Text>
            <View style={{ flexDirection: 'row', marginTop: space.lg }}>
              <Pressable
                accessibilityRole="button"
                onPress={() => router.push('/context')}
                style={({ pressed }) => ({
                  backgroundColor: colors.accent,
                  minHeight: 44,
                  justifyContent: 'center',
                  paddingHorizontal: space.lg,
                  paddingVertical: 10,
                  borderRadius: radius.md,
                  opacity: pressed ? 0.85 : 1,
                  ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
                })}
              >
                <Text style={{ color: colors.accentText, fontSize: font.body, fontWeight: '600' }}>
                  Go to Context
                </Text>
              </Pressable>
            </View>
          </View>
        ) : (
          <FlatList
            data={items}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => (
              <FeedRow
                item={item}
                onPress={() =>
                  router.push({ pathname: '/entity/[id]', params: { id: item.id, mode } })
                }
              />
            )}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => void loadInitial(mode, 'refresh')}
                tintColor={colors.accent}
              />
            }
            ListHeaderComponent={
              <View
                style={{
                  paddingHorizontal: pageMargin,
                  paddingVertical: space.md,
                  borderBottomWidth: 1,
                  borderBottomColor: colors.border,
                }}
              >
                <Text style={{ fontSize: font.small, fontWeight: '600', color: colors.textMuted }}>
                  {headerSubtitle}
                </Text>
                {confidenceNote ? (
                  <Text
                    style={{
                      fontSize: font.caption,
                      color: colors.textFaint,
                      marginTop: space.xs,
                      lineHeight: 16,
                    }}
                  >
                    {confidenceNote}
                  </Text>
                ) : null}
              </View>
            }
            ListFooterComponent={
              <View style={{ paddingHorizontal: pageMargin, paddingVertical: space.lg }}>
                {loadingMore ? (
                  <Text style={{ fontSize: font.small, color: colors.textFaint, textAlign: 'center' }}>
                    Loading more matches…
                  </Text>
                ) : loadMoreError ? (
                  <View style={{ alignItems: 'center', gap: space.sm }}>
                    <Text style={{ fontSize: font.small, color: colors.danger, textAlign: 'center' }}>
                      {loadMoreError}
                    </Text>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => void handleLoadMore()}
                      style={({ pressed }) => ({
                        minHeight: 44,
                        justifyContent: 'center',
                        paddingHorizontal: space.md,
                        paddingVertical: space.sm,
                        borderRadius: radius.md,
                        borderWidth: 1,
                        borderColor: colors.border,
                        opacity: pressed ? 0.75 : 1,
                        ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
                      })}
                    >
                      <Text style={{ fontSize: font.small, fontWeight: '600', color: colors.accent }}>
                        Retry
                      </Text>
                    </Pressable>
                  </View>
                ) : nextCursor ? (
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => void handleLoadMore()}
                    style={({ pressed }) => ({
                      alignSelf: 'center',
                      minHeight: 44,
                      justifyContent: 'center',
                      paddingHorizontal: space.lg,
                      paddingVertical: space.sm,
                      borderRadius: radius.md,
                      borderWidth: 1,
                      borderColor: colors.border,
                      opacity: pressed ? 0.75 : 1,
                      ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
                    })}
                  >
                    <Text style={{ fontSize: font.small, fontWeight: '600', color: colors.accent }}>
                      Load more
                    </Text>
                  </Pressable>
                ) : (
                  <Text style={{ fontSize: font.caption, color: colors.textFaint, textAlign: 'center' }}>
                    Grounded in Cala sources
                  </Text>
                )}
              </View>
            }
          />
        )}
      </View>
    </View>
  );
}
