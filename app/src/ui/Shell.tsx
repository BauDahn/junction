import { Children, isValidElement, useState, type ReactNode } from 'react';
import { Platform, Pressable, ScrollView, Text, TextInput, useWindowDimensions, View, type TextInputProps } from 'react-native';
import { usePathname, useRouter } from 'expo-router';
import { font, space, useTheme } from '../theme';
import Logo from './Logo';

/** Corner radius for bordered controls and cards. */
export const GRID_RADIUS = 6;
export const DESKTOP_MIN = 900;
export const TOP_BAR = 56;
const MAX_WIDTH = 1080;

export function useDesktop() {
  return useWindowDimensions().width >= DESKTOP_MIN;
}

const NAV: { path: string; label: string }[] = [
  { path: '/feed', label: 'My events' },
  { path: '/explore', label: 'Explore events' },
  { path: '/perfil', label: 'Profile' },
];

/** Application top bar (56px, hairline underneath): logo on the left, navigation on the right (desktop only; phones keep the bottom bar). */
export function TopBar() {
  const { colors } = useTheme();
  const desktop = useDesktop();
  const router = useRouter();
  const pathname = usePathname();
  return (
    <View style={{ height: TOP_BAR, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: desktop ? 40 : space.xl, borderBottomWidth: 1, borderColor: colors.border }}>
      <Logo size={22} />
      {desktop ? (
        <View accessibilityRole="tablist" style={{ flexDirection: 'row', alignItems: 'stretch', gap: space.xl, height: '100%' }}>
          {NAV.map((item) => {
            const active = pathname === item.path || (item.path === '/feed' && (pathname === '/' || pathname.startsWith('/event') || pathname.startsWith('/entity')));
            return (
              <Pressable key={item.path} accessibilityRole="tab" accessibilityState={{ selected: active }} onPress={() => router.push(item.path as never)} style={{ justifyContent: 'center', borderBottomWidth: 2, borderBottomColor: active ? colors.accent : 'transparent', marginBottom: -1 }}>
                <Text style={{ fontSize: font.small, fontWeight: '600', color: active ? colors.accent : colors.textMuted }}>{item.label}</Text>
              </Pressable>
            );
          })}
        </View>
      ) : null}
    </View>
  );
}

/** Screen: top bar, then an open centered container (max 1080px) straight on the canvas. */
export function Page({ children }: { children: ReactNode }) {
  const { colors } = useTheme();
  const desktop = useDesktop();
  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.surface }} contentContainerStyle={{ flexGrow: 1 }} keyboardShouldPersistTaps="handled">
      <View style={[{ flex: 1, backgroundColor: colors.surface }, Platform.OS === 'web' ? ({ minHeight: '100vh' } as object) : null]}>
        <TopBar />
        <View style={{ width: '100%', maxWidth: MAX_WIDTH, alignSelf: 'center', paddingHorizontal: desktop ? 40 : space.xl, paddingTop: desktop ? 56 : space.xxl, paddingBottom: desktop ? 72 : 112 }}>
          {children}
        </View>
      </View>
    </ScrollView>
  );
}

/** Page heading: display title with one accent word, optional one-line subtitle and actions. */
export function PageHeader({ title, accent, subtitle, children }: { title: string; accent?: string; subtitle?: string; children?: ReactNode }) {
  const { colors } = useTheme();
  const desktop = useDesktop();
  return (
    <View style={{ gap: space.md, marginBottom: desktop ? 40 : space.xxl }}>
      <Text accessibilityRole="header" style={{ fontSize: desktop ? 40 : 30, lineHeight: desktop ? 44 : 34, fontWeight: '800', letterSpacing: desktop ? -1.2 : -0.9, color: colors.text }}>
        {title}{accent ? <Text style={{ color: colors.accent }}> {accent}</Text> : null}
      </Text>
      {subtitle ? <Text style={{ fontSize: font.lead, lineHeight: 24, color: colors.textMuted }}>{subtitle}</Text> : null}
      {children}
    </View>
  );
}

/** Responsive card grid with even gutters (no divider lines). Children are laid out `columns` per row. */
export function CardGrid({ columns, children, gap = 20 }: { columns: number; children: ReactNode; gap?: number }) {
  const items = Children.toArray(children);
  const cols = Math.max(1, columns);
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginHorizontal: -gap / 2 }}>
      {items.map((item, index) => (
        <View key={isValidElement(item) && item.key != null ? String(item.key) : index} style={{ width: `${100 / cols}%`, minWidth: 0, padding: gap / 2 }}>
          {item}
        </View>
      ))}
    </View>
  );
}

/** Sections separated by a single hairline, optionally in two columns. Each child is one section. */
export function Stack({ columns = 1, children }: { columns?: number; children: ReactNode }) {
  const { colors } = useTheme();
  const items = Children.toArray(children);
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', columnGap: 64 }}>
      {items.map((item, index) => (
        <View key={isValidElement(item) && item.key != null ? String(item.key) : index} style={{ flexBasis: columns === 1 ? '100%' : '44%', flexGrow: 1, minWidth: 0, paddingVertical: space.xl, borderTopWidth: 1, borderColor: colors.border }}>
          {item}
        </View>
      ))}
    </View>
  );
}

/** Section heading used inside pages and cards. */
export function CellTitle({ children }: { children: ReactNode }) {
  const { colors } = useTheme();
  return <Text accessibilityRole="header" style={{ fontSize: font.h2, fontWeight: '800', letterSpacing: -0.3, color: colors.text, marginBottom: space.md }}>{children}</Text>;
}

/** Bordered card: 1px line, 6px radius, no shadow. */
export function Card({ children, style }: { children: ReactNode; style?: object }) {
  const { colors } = useTheme();
  return <View style={[{ borderWidth: 1, borderColor: colors.border, borderRadius: GRID_RADIUS, backgroundColor: colors.surface, overflow: 'hidden' }, style]}>{children}</View>;
}

/** Text input: 1px border that turns accent on focus, 6px radius, white background. */
export function Input(props: TextInputProps) {
  const { colors } = useTheme();
  const [focused, setFocused] = useState(false);
  return (
    <TextInput
      placeholderTextColor={colors.textFaint}
      {...props}
      onFocus={(event) => { setFocused(true); props.onFocus?.(event); }}
      onBlur={(event) => { setFocused(false); props.onBlur?.(event); }}
      style={[{ minHeight: 44, fontSize: 16, color: colors.text, backgroundColor: colors.surface, borderWidth: 1, borderRadius: GRID_RADIUS, paddingHorizontal: space.md, paddingVertical: space.sm, borderColor: focused ? colors.accent : colors.border }, Platform.OS === 'web' ? ({ outlineStyle: 'none' } as object) : null, props.style]}
    />
  );
}

/** Button: filled accent when `primary` or `selected`, otherwise a 1px outline. 6px radius. */
export function ActionButton({ label, onPress, primary, selected }: { label: string; onPress: () => void; primary?: boolean; selected?: boolean }) {
  const { colors } = useTheme();
  const filled = primary || selected;
  return (
    <Pressable accessibilityRole="button" accessibilityState={{ selected: !!selected }} onPress={onPress} style={({ pressed }) => ({ minHeight: 40, alignSelf: 'flex-start', justifyContent: 'center', paddingHorizontal: space.lg, borderRadius: GRID_RADIUS, borderWidth: 1, borderColor: filled ? colors.accent : colors.border, backgroundColor: filled ? colors.accent : 'transparent', opacity: pressed ? 0.85 : 1 })}>
      <Text style={{ fontSize: font.small, fontWeight: '700', color: filled ? colors.accentText : colors.text }}>{label}</Text>
    </Pressable>
  );
}
