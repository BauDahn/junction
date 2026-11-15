import { useEffect, useState } from 'react';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Feather, Ionicons } from '@expo/vector-icons';
import { getEntityDetail } from '../api/entities';
import { useMode } from '../mode';
import { font, radius, space, tabBarHeight, useTheme } from '../theme';
import { FavoritesReportButton } from './FavoritesReportButton';

const prettify = (id: string) => id.replace(/-/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

/** Floating heart bubble (bottom-left, mirror of the assistant): opens the list of favorites with un-like hearts and the PDF report. */
export default function FavoritesBubble() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const { favoriteInvestorIds, toggleFavoriteInvestor, mode, user } = useMode();
  const [open, setOpen] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const s = styles(colors);
  const title = mode === 'investing' ? 'Favorite startups' : 'Favorite investors';

  // Names are looked up only while the panel is open, once per favorite.
  useEffect(() => {
    if (!open) return;
    let active = true;
    const missing = favoriteInvestorIds.filter((id) => !names[id]);
    if (!missing.length) return;
    void Promise.all(missing.map(async (id) => {
      try {
        const detail = await getEntityDetail(id, mode, user?.session_id);
        return detail ? ([id, detail.name] as const) : null;
      } catch { return null; }
    })).then((entries) => {
      if (!active) return;
      const found = entries.filter((entry): entry is readonly [string, string] => entry !== null);
      if (found.length) setNames((current) => ({ ...current, ...Object.fromEntries(found) }));
    });
    return () => { active = false; };
  }, [open, favoriteInvestorIds, mode, user?.session_id, names]);

  const openEntity = (id: string) => {
    setOpen(false);
    router.push({ pathname: '/entity/[id]', params: { id, session_id: user?.session_id ?? '', mode } });
  };

  return (
    <View pointerEvents="box-none" style={[s.anchor, { marginBottom: insets.bottom }]}>
      {open ? (
        <View style={[s.panel, { width: Math.min(380, windowWidth - 32), maxHeight: Math.min(540, windowHeight - 100) }]}>
          <View style={s.header}>
            <Ionicons name="heart" size={20} color={colors.accent} />
            <Text style={s.title}>{title}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Close favorites" onPress={() => setOpen(false)} style={s.iconButton}>
              <Feather name="x" size={20} color={colors.text} />
            </Pressable>
          </View>
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={s.list}>
            {favoriteInvestorIds.length ? favoriteInvestorIds.map((id) => (
              <View key={id} style={s.row}>
                <Pressable accessibilityRole="link" accessibilityLabel={`Open ${names[id] ?? prettify(id)}`} onPress={() => openEntity(id)} style={s.rowMain}>
                  <Text numberOfLines={1} style={s.name}>{names[id] ?? prettify(id)}</Text>
                </Pressable>
                <Pressable accessibilityRole="button" accessibilityLabel={`Remove ${names[id] ?? prettify(id)} from favorites`} onPress={() => toggleFavoriteInvestor(id)} style={s.iconButton}>
                  <Ionicons name="heart" size={22} color={colors.accent} />
                </Pressable>
              </View>
            )) : <Text style={s.empty}>{mode === 'investing' ? 'No favorite startups yet. Tap Save on a match to add one.' : 'No favorite investors yet. Tap Save on a match to add one.'}</Text>}
          </ScrollView>
          {favoriteInvestorIds.length ? <View style={s.footer}><FavoritesReportButton /></View> : null}
        </View>
      ) : (
        <Pressable accessibilityRole="button" accessibilityLabel="Open favorites" onPress={() => setOpen(true)} style={s.trigger}>
          <Ionicons name="heart" size={28} color={colors.accentText} />
        </Pressable>
      )}
    </View>
  );
}

const styles = (c: ReturnType<typeof useTheme>['colors']) => StyleSheet.create({
  anchor: { position: 'absolute', left: 16, bottom: tabBarHeight + 16, zIndex: 100, alignItems: 'flex-start' },
  trigger: { width: 60, height: 60, borderRadius: radius.pill, backgroundColor: c.accent, borderWidth: 1, borderColor: c.border, alignItems: 'center', justifyContent: 'center' },
  panel: { backgroundColor: c.surface, borderWidth: 1, borderColor: c.border, borderRadius: 6, overflow: 'hidden' },
  header: { flexDirection: 'row', alignItems: 'center', gap: space.sm, paddingLeft: space.lg, paddingRight: space.xs, borderBottomWidth: 1, borderBottomColor: c.border },
  title: { flex: 1, fontSize: font.body, fontWeight: '700', color: c.text, paddingVertical: space.md },
  iconButton: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  list: { paddingHorizontal: space.lg, paddingVertical: space.xs },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.sm, borderBottomWidth: 1, borderBottomColor: c.border },
  rowMain: { flex: 1, minHeight: 52, justifyContent: 'center' },
  name: { fontSize: font.body, fontWeight: '600', color: c.text },
  empty: { color: c.textMuted, fontSize: font.small, lineHeight: 19, paddingVertical: space.lg },
  footer: { paddingHorizontal: space.lg, paddingBottom: space.lg, borderTopWidth: 1, borderTopColor: c.border },
});
