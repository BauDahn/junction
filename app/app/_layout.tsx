import { Tabs, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useRef } from 'react';
import { Animated, Platform, Pressable, Text, View } from 'react-native';
import { ModeProvider, useMode, type MatchMode } from '../src/mode';
import { font, radius, space, ThemeProvider, useTheme } from '../src/theme';

export default function RootLayout() {
  return (
    <ThemeProvider mode="light">
      <ModeProvider>
        <ThemedTabs />
      </ModeProvider>
    </ThemeProvider>
  );
}

const SEGMENT_WIDTH = 74;
const TRACK_PADDING = 2;

function ModeToggle() {
  const { mode, setMode } = useMode();
  const { colors } = useTheme();
  const slide = useRef(new Animated.Value(mode === 'raising' ? 0 : 1)).current;

  useEffect(() => {
    Animated.timing(slide, {
      toValue: mode === 'raising' ? 0 : 1,
      duration: 160,
      useNativeDriver: Platform.OS !== 'web',
    }).start();
  }, [mode, slide]);

  const options: { value: MatchMode; label: string }[] = [
    { value: 'raising', label: 'Raising' },
    { value: 'investing', label: 'Investing' },
  ];

  const translateX = slide.interpolate({
    inputRange: [0, 1],
    outputRange: [0, SEGMENT_WIDTH],
  });

  return (
    <View
      accessibilityRole="tablist"
      style={{
        position: 'relative',
        flexDirection: 'row',
        alignItems: 'center',
        width: SEGMENT_WIDTH * 2 + TRACK_PADDING * 2 + 2,
        backgroundColor: colors.surfaceAlt,
        borderWidth: 1,
        borderColor: colors.border,
        borderRadius: radius.pill,
        padding: TRACK_PADDING,
      }}
    >
      <Animated.View
        pointerEvents="none"
        style={{
          position: 'absolute',
          top: TRACK_PADDING,
          bottom: TRACK_PADDING,
          left: TRACK_PADDING,
          width: SEGMENT_WIDTH,
          borderRadius: radius.pill,
          backgroundColor: colors.surface,
          borderWidth: 1,
          borderColor: colors.border,
          transform: [{ translateX }],
        }}
      />
      {options.map((opt) => {
        const active = mode === opt.value;
        return (
          <Pressable
            key={opt.value}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            onPress={() => setMode(opt.value)}
            style={({ pressed }) => ({
              width: SEGMENT_WIDTH,
              paddingVertical: 4,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: radius.pill,
              opacity: pressed ? 0.75 : 1,
              ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
            })}
          >
            <Text
              numberOfLines={1}
              style={{
                fontSize: font.caption,
                fontWeight: active ? '600' : '500',
                color: active ? colors.accent : colors.textMuted,
              }}
            >
              {opt.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function ProfileAvatarButton() {
  const router = useRouter();
  const { colors } = useTheme();

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Open profile"
      hitSlop={6}
      onPress={() => router.push('/perfil')}
      style={({ pressed }) => ({
        width: 32,
        height: 32,
        borderRadius: radius.pill,
        backgroundColor: colors.surfaceAlt,
        borderWidth: 1,
        borderColor: colors.border,
        alignItems: 'center',
        justifyContent: 'center',
        opacity: pressed ? 0.75 : 1,
        ...(Platform.OS === 'web' ? { cursor: 'pointer' as const } : null),
      })}
    >
      <View style={{ alignItems: 'center', justifyContent: 'center' }}>
        <View
          style={{
            width: 9,
            height: 9,
            borderRadius: 5,
            borderWidth: 1.5,
            borderColor: colors.textMuted,
          }}
        />
        <View
          style={{
            width: 15,
            height: 6,
            borderTopLeftRadius: 7,
            borderTopRightRadius: 7,
            borderWidth: 1.5,
            borderBottomWidth: 0,
            borderColor: colors.textMuted,
            marginTop: 2,
          }}
        />
      </View>
    </Pressable>
  );
}

function HeaderControls() {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
      <ModeToggle />
      <ProfileAvatarButton />
    </View>
  );
}

function FeedIcon({ color }: { color: string }) {
  return (
    <View style={{ width: 20, height: 20, justifyContent: 'center', gap: 3.5, paddingHorizontal: 2 }}>
      <View style={{ height: 1.75, width: 16, borderRadius: 1, backgroundColor: color }} />
      <View style={{ height: 1.75, width: 11, borderRadius: 1, backgroundColor: color }} />
      <View style={{ height: 1.75, width: 16, borderRadius: 1, backgroundColor: color }} />
    </View>
  );
}

function AskIcon({ color }: { color: string }) {
  return (
    <View style={{ width: 20, height: 20, alignItems: 'center', justifyContent: 'center' }}>
      <View
        style={{
          width: 16,
          height: 13,
          borderRadius: 4,
          borderWidth: 1.6,
          borderColor: color,
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: 2.5,
        }}
      >
        <View style={{ width: 2, height: 2, borderRadius: 1, backgroundColor: color }} />
        <View style={{ width: 2, height: 2, borderRadius: 1, backgroundColor: color }} />
        <View style={{ width: 2, height: 2, borderRadius: 1, backgroundColor: color }} />
      </View>
    </View>
  );
}

function ContextIcon({ color }: { color: string }) {
  return (
    <View style={{ width: 20, height: 20, alignItems: 'center', justifyContent: 'center' }}>
      <View
        style={{
          width: 14,
          height: 17,
          borderRadius: 2.5,
          borderWidth: 1.6,
          borderColor: color,
          justifyContent: 'center',
          gap: 3,
          paddingHorizontal: 2.5,
        }}
      >
        <View style={{ height: 1.5, width: '100%', backgroundColor: color }} />
        <View style={{ height: 1.5, width: '70%', backgroundColor: color }} />
      </View>
    </View>
  );
}

function ThemedTabs() {
  const { mode, colors } = useTheme();
  return (
    <>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      <Tabs
        screenOptions={{
          headerStyle: {
            backgroundColor: colors.surface,
            borderBottomWidth: 1,
            borderBottomColor: colors.border,
            elevation: 0,
            shadowOpacity: 0,
          },
          headerShadowVisible: false,
          headerTintColor: colors.text,
          headerTitleAlign: 'left',
          headerTitleStyle: {
            fontSize: font.lead,
            fontWeight: '600',
            color: colors.text,
          },
          headerRightContainerStyle: {
            paddingRight: space.lg,
          },
          headerRight: () => <HeaderControls />,
          tabBarStyle: {
            backgroundColor: colors.surface,
            borderTopColor: colors.border,
            borderTopWidth: 1,
            elevation: 0,
            shadowOpacity: 0,
          },
          tabBarActiveTintColor: colors.accent,
          tabBarInactiveTintColor: colors.textFaint,
          tabBarLabelStyle: {
            fontSize: 11,
            fontWeight: '600',
          },
          sceneStyle: { backgroundColor: colors.bg },
        }}
      >
        <Tabs.Screen name="index" options={{ href: null }} />
        <Tabs.Screen
          name="feed"
          options={{
            title: 'Feed',
            tabBarIcon: ({ color }) => <FeedIcon color={color} />,
          }}
        />
        <Tabs.Screen
          name="chat"
          options={{
            title: 'Ask',
            tabBarIcon: ({ color }) => <AskIcon color={color} />,
          }}
        />
        <Tabs.Screen
          name="context"
          options={{
            title: 'Context',
            tabBarIcon: ({ color }) => <ContextIcon color={color} />,
          }}
        />
        <Tabs.Screen name="deck" options={{ href: null, headerShown: false }} />
        <Tabs.Screen name="journal" options={{ href: null }} />
        <Tabs.Screen name="estado" options={{ href: null }} />
        <Tabs.Screen name="perfil" options={{ href: null, title: 'Profile' }} />
        <Tabs.Screen name="entity/[id]" options={{ href: null, title: 'Details' }} />
      </Tabs>
    </>
  );
}
